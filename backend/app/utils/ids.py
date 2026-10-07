import uuid

def generate_id(prefix: str) -> str:
    """Generate a prefixed short UUID string (e.g., pat_1a2b3c4d...)"""
    clean_uuid = uuid.uuid4().hex[:16]
    return f"{prefix}_{clean_uuid}"

def patient_id() -> str: return generate_id("pat")
def document_id() -> str: return generate_id("doc")
def page_id() -> str: return generate_id("pag")
def fact_id() -> str: return generate_id("fact")
def medication_id() -> str: return generate_id("med")
def investigation_id() -> str: return generate_id("inv")
def timeline_event_id() -> str: return generate_id("evt")
def contradiction_id() -> str: return generate_id("iss")
def brief_id() -> str: return generate_id("brf")
def consultation_id() -> str: return generate_id("cns")
def version_id() -> str: return generate_id("ver")
def memory_id() -> str: return generate_id("mem")
def voice_note_id() -> str: return generate_id("vce")
def job_id() -> str: return generate_id("job")
def report_id() -> str: return generate_id("val")
def audit_id() -> str: return generate_id("aud")
def llm_log_id() -> str: return generate_id("llm")
def request_id() -> str: return generate_id("req")
def user_id() -> str: return generate_id("usr")

consultation_version_id = version_id
clinical_memory_id = memory_id
validation_report_id = report_id

