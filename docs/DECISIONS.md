# ClinSync Architectural Decision Records (ADR)

## ADR-001: Architecture & Invariant Enforcement
- **Context:** ClinSync transforms fragmented medical records into unified clinical context.
- **Decision:** Strict adherence to 10 invariants (INV-1 through INV-10):
  1. AI output can never write directly to `clinical_memory` without Gate 1 approval.
  2. Every fact must link to verbatim source evidence.
  3. No resolution of conflicting prescriptions by AI.
  4. Missing info is framed as prompts, never guessed.
  5. Trends described non-causally.
  6. Zero treatment directives in AI text.
  7. Clear origin tracking (ai_generated vs doctor_edited vs approved).
  8. Append-only clinical memory with `supersedes_id`.

## ADR-002: Dual-Gate Validation Layer
- **Gate 1 (Pre-Clinical Memory):** Evaluates consultation or fact before persisting to `clinical_memory`. Fail-closed.
- **Gate 2 (Post-Generation):** Evaluates generated doctor briefs and drafts. Fail to deterministic template on repeated failure.

## ADR-003: LLM Gateway with Provider Fallbacks
- LiteLLM Router encapsulates Gemini (Primary) and Groq (Secondary / Fallback).
- Judge models should differ from the generator provider whenever possible.
