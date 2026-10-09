"""Keep the test suite out of the developer's database.

The suite used to run against whatever `DATABASE_URL` the environment had — in
practice the repo-root `clinsync.db` the dev server also uses. Every test module
creates patients ("Voice Test Patient", "Gate 1 Conflict Patient", …) and never
removes them, so a handful of runs filled the database with ~50 junk records and
pushed the demo patient off the first page of `GET /patients`. The app's Home
screen then showed test fixtures instead of real data, which is exactly the kind
of failure that looks like a frontend bug.

So the environment is redirected **before** anything imports `app.config` —
pytest imports the root `conftest.py` ahead of any test module, and the engine is
built at import time. Both the database and the storage root go to a temp
directory that is removed when the session ends.

A developer can still point the suite at a real database deliberately by setting
`CLINSYNC_TEST_DATABASE_URL` (or `DATABASE_URL` with
`CLINSYNC_TESTS_USE_REAL_DB=1`), which is how the fresh-clone check in
`docs/frontend/PROGRESS.md` is run.
"""
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent / 'backend'
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

_TEST_ROOT = Path(tempfile.mkdtemp(prefix='clinsync-tests-'))
_REAL_DB = os.environ.get('CLINSYNC_TEST_DATABASE_URL')

if _REAL_DB or os.environ.get('CLINSYNC_TESTS_USE_REAL_DB') == '1':
    # Opt-in escape hatch: run against a real database on purpose.
    os.environ.setdefault('STORAGE_ROOT', str(_TEST_ROOT / 'storage'))
else:
    os.environ['DATABASE_URL'] = f'sqlite:///{_TEST_ROOT / "test.db"}'
    os.environ['STORAGE_ROOT'] = str(_TEST_ROOT / 'storage')

# Never let a test write to the developer's real storage, even in opt-in mode.
os.environ.setdefault('LOG_LEVEL', 'WARNING')

atexit.register(lambda: shutil.rmtree(_TEST_ROOT, ignore_errors=True))


def pytest_report_header(config):
    """Say plainly which database is in use, so a failure is diagnosable."""
    return f'ClinSync tests: {os.environ.get("DATABASE_URL")}'


def pytest_sessionstart(session):
    """Create the schema.

    The suite previously inherited a database that already had tables. Now that
    it owns a fresh one, they have to be built — and several test modules build
    a `TestClient` at import time without entering its context manager, so the
    app lifespan (which also creates the schema) never runs for them.
    """
    from app.db.database import ensure_schema, schema_is_complete

    if not ensure_schema():
        raise RuntimeError(
            'the test schema could not be created — check DATABASE_URL '
            f'({os.environ.get("DATABASE_URL")})'
        )
    assert schema_is_complete()
