# ClinSync Open Questions & Defaults

Per `audit.md` Section 23:

1. **Exact Model IDs**:
   - Gemini: `gemini-2.5-flash`, `gemini-2.5-pro` (verified available via API)
   - Groq: `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `whisper-large-v3` (verified available via API)
   - Status: Resolved in `.env`.

2. **Date Format Default**:
   - Assumed day-first (India standard: DD/MM/YYYY) with fallback to ISO (YYYY-MM-DD).
   - Ambiguous dates like 03/04/2026 flagged if context does not disambiguate.

3. **Multi-language Support**:
   - English primary, best-effort Hindi/Tamil for voice notes and transcripts with explicit doctor-review requirement.

4. **Single-Doctor Prototype**:
   - Single-doctor prototype with `current_user` dependency returning default doctor `doc_001` (Dr. Willie Carter). Schema carries `actor` strings for future RBAC swap.

5. **LLM Gateway Topology**:
   - In-process `LiteLLM Router` wrapper in `app/ai/gateway.py`.
