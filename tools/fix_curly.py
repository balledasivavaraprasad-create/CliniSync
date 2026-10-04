"""Braces single-statement `if` bodies that `dart format` wrapped onto two lines.

Run after `dart format` when `flutter analyze` reports
`curly_braces_in_flow_control_structures`.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

LINT = re.compile(
    r'^\s*info • Statements in an if should be enclosed in a block.*'
    r' • (lib[^\s]+):(\d+):\d+ • curly_braces_in_flow_control_structures$',
    re.M,
)


def lint_hits() -> dict[str, set[int]]:
    out = subprocess.run(['flutter', 'analyze'], capture_output=True, text=True).stdout
    hits: dict[str, set[int]] = {}
    for m in LINT.finditer(out):
        hits.setdefault(m.group(1), set()).add(int(m.group(2)))
    return hits


def main() -> int:
    fixed = 0
    for _ in range(8):  # line numbers shift after each edit, so re-query
        hits = lint_hits()
        if not hits:
            break
        for path, lines in hits.items():
            p = pathlib.Path(path)
            src = p.read_text().splitlines(keepends=True)
            for n in sorted(lines, reverse=True):
                # The analyzer reports the *body* line, so walk back to the `if`.
                i = n - 1
                head_idx = None
                for j in range(i, max(i - 3, -1), -1):
                    if j < 0 or j >= len(src):
                        continue
                    if re.match(r'^\s*if \(', src[j].rstrip('\n')):
                        head_idx = j
                        break
                if head_idx is None:
                    continue
                head = src[head_idx].rstrip('\n')
                body = src[head_idx + 1].rstrip('\n') if head_idx + 1 < len(src) else ''
                m = re.match(r'^(\s*)if \((.+)\)$', head)
                if not m or not body.strip().endswith(';'):
                    continue
                indent, cond = m.groups()
                src[head_idx] = f'{indent}if ({cond}) {{\n{body}\n{indent}}}\n'
                del src[head_idx + 1]
                fixed += 1
            p.write_text(''.join(src))
    print(f'braced {fixed} if-statements')
    return 0 if not lint_hits() else 1


if __name__ == '__main__':
    sys.exit(main())
