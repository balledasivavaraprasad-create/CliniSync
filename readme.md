# ClinSync

<div align="center">

# **ClinSync**

### **Know the patient before you meet the patient.**

**AI-assisted pre-consultation intelligence and longitudinal clinical memory**

<br />

`Voice Intake` · `Medical Documents` · `Clinical Memory` · `Evidence` · `Specialty Routing` · `Doctor Brief`

<br />

> **Less time collecting information. More time caring for the patient.**

</div>

---

# 1. Product Vision

ClinSync is an AI-assisted healthcare workflow platform designed to reduce the amount of consultation time doctors spend on:

* collecting patient history
* repeatedly asking basic questions
* manually reviewing medical documents
* searching through previous records
* organizing fragmented information
* writing repetitive consultation documentation

ClinSync moves this work **before the consultation**.

The patient provides information through:

* secure identification
* voice
* document scanning
* PDF uploads
* existing medical records

ClinSync processes this information into a structured **Patient Clinical Memory**.

Before the appointment, the system creates an **evidence-backed Doctor Brief** containing the information most relevant to the upcoming consultation.

The doctor reviews the information, verifies it, interacts with the patient, makes the clinical decision, and can use ClinSync to generate documentation afterward.

---

# 2. The Core Philosophy

ClinSync is **not an AI doctor**.

It is an **AI preparation and information organization layer around the doctor**.

The fundamental architecture is:

```text
                    PATIENT
                       │
                       ▼
              INFORMATION INTAKE
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
        Voice       Documents     History
          │            │            │
          ▼            ▼            ▼
         STT          OCR         Records
          │            │            │
          └────────────┼────────────┘
                       ▼
              INFORMATION EXTRACTION
                       │
                       ▼
             CLINICAL MEMORY LAYER
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       Timeline      Trends      Medications
                       │
                       ▼
              MISSING INFO CHECK
                       │
                       ▼
               SPECIALTY ROUTING
                       │
                       ▼
             EVIDENCE-BACKED BRIEF
                       │
                       ▼
                 DOCTOR REVIEW
                       │
                       ▼
             HUMAN CLINICAL DECISION
                       │
                       ▼
             CONSULTATION DOCUMENT
                       │
                       ▼
             PATIENT MEMORY UPDATE
```

The doctor remains the final authority.

---

# 3. MVP Definition

The MVP MUST contain the following complete workflow.

## Patient Side

1. Authentication
2. Patient profile
3. Secure patient identification
4. Existing-record retrieval
5. Face-based identification capability
6. Document upload
7. PDF upload
8. Camera document scanning
9. OCR/document processing
10. Document classification
11. Voice recording
12. Speech-to-text
13. AI conversational intake
14. Missing-information detection
15. Targeted follow-up questions
16. Structured symptom extraction
17. Patient clinical timeline
18. Medication history
19. Basic medical trend detection
20. Specialty routing
21. Appointment booking
22. Appointment status

## AI Layer

23. LangGraph orchestration
24. Document extraction
25. Voice processing
26. Clinical information extraction
27. Evidence linking
28. Missing-information detection
29. Dynamic questioning
30. Clinical timeline generation
31. Medication reconciliation
32. Basic trend detection
33. Specialty routing
34. Doctor brief generation
35. AI output validation
36. Hallucination/evidence checks

## Doctor Side

37. Doctor authentication
38. Doctor dashboard
39. Upcoming appointments
40. Patient brief
41. Patient timeline
42. Document viewer
43. Evidence viewer
44. Medication history
45. Trend visualization
46. Missing-information section
47. Doctor correction/editing
48. Consultation notes
49. AI-assisted note generation
50. Doctor approval

## Platform

51. Role-based access control
52. Consent management
53. Audit logs
54. Secure document storage
55. Structured database
56. API documentation
57. Error handling
58. Logging
59. AI observability
60. Evaluation framework

Everything else is **Phase 2+**.

---

# 4. Primary User Journey

## Step 1 — Patient Opens ClinSync

The patient sees a premium, minimal onboarding experience.

The UI should immediately communicate:

> **Your doctor should spend more time listening to you, not searching through paperwork.**

The patient authenticates.

---

# 5. Patient Identification

ClinSync should support a secure identity flow.

Possible MVP mechanism:

```text
Patient
   ↓
Authentication
   ↓
Patient ID / Mobile Verification
   ↓
Optional Face Scan
   ↓
Identity Match
   ↓
Existing Patient Profile
```

Face recognition is an **identity mechanism**, not a medical diagnostic mechanism.

The system must never infer health conditions from facial appearance.

### Face Scan Requirements

The backend should support:

```text
POST /api/v1/identity/face/enroll
POST /api/v1/identity/face/verify
POST /api/v1/identity/face/match
```

The implementation should separate:

* identity
* biometric representation
* medical records

Biometric data must not be mixed into ordinary clinical records.

---

# 6. Patient Profile

A patient profile should contain structured information such as:

```json
{
  "patient_id": "pat_xxxxx",
  "name": "Patient Name",
  "date_of_birth": "2000-01-01",
  "gender": "optional",
  "contact": {
    "phone": "encrypted",
    "email": "encrypted"
  },
  "emergency_contact": {},
  "created_at": "...",
  "updated_at": "..."
}
```

Do not store unnecessary information.

Follow the principle:

> **Collect what the workflow actually needs.**

---

# 7. Existing Patient Records

After identification:

```text
Patient Identification
        ↓
Patient ID
        ↓
Retrieve Authorized Records
        ↓
Clinical Memory
```

The patient should immediately see a high-level representation such as:

```text
Your Medical Memory

Previous consultations: 7
Documents: 18
Prescriptions: 11
Reports: 14
Last consultation: 12 Aug 2026
```

Do not overwhelm the patient.

---

# 8. Document Upload

The patient can:

### Upload PDF

```text
Select PDF
   ↓
Upload
   ↓
Validate
   ↓
Store
   ↓
Process asynchronously
```

### Capture Document

```text
Open Camera
   ↓
Detect Document
   ↓
Capture
   ↓
Crop / Correct Perspective
   ↓
Upload
   ↓
OCR
```

### Supported Initial Documents

* prescriptions
* blood reports
* laboratory reports
* discharge summaries
* consultation notes
* imaging reports
* medical certificates
* other medical documents

The system should not assume every document is a particular type.

---

# 9. Document Processing Pipeline

Every document follows:

```text
UPLOAD
   ↓
FILE VALIDATION
   ↓
SECURE STORAGE
   ↓
DOCUMENT CLASSIFICATION
   ↓
OCR / VISION
   ↓
TEXT EXTRACTION
   ↓
MEDICAL ENTITY EXTRACTION
   ↓
STRUCTURED DATA
   ↓
EVIDENCE LINKS
   ↓
VALIDATION
   ↓
CLINICAL MEMORY
```

---

# 10. Document Classification

The classifier should determine:

```text
PRESCRIPTION
LAB_REPORT
IMAGING_REPORT
DISCHARGE_SUMMARY
CONSULTATION_NOTE
MEDICAL_CERTIFICATE
OTHER
```

The classification result must include confidence.

Example:

```json
{
  "document_type": "LAB_REPORT",
  "confidence": 0.96
}
```

If confidence is low:

```text
⚠ Document type uncertain
```

and allow manual correction.

---

# 11. Medical Information Extraction

The system should extract structured information.

Example:

```json
{
  "conditions": [],
  "symptoms": [],
  "medications": [],
  "procedures": [],
  "lab_results": [],
  "allergies": [],
  "dates": [],
  "doctors": [],
  "facilities": []
}
```

Every extracted item should have:

```json
{
  "value": "...",
  "source_document_id": "...",
  "page": 2,
  "confidence": 0.94
}
```

This is critical.

**Never create a medical fact without knowing where it came from.**

---

# 12. Voice Intake

The patient should be able to press:

> **Tell us what is bothering you**

and simply speak.

Example:

> "I've been having headaches for the past four days. They become worse in the evening and I've also been feeling dizzy."

Pipeline:

```text
Voice
 ↓
Audio Storage
 ↓
Speech-to-Text
 ↓
Transcript
 ↓
Clinical Information Extraction
 ↓
Structured Symptoms
 ↓
Evidence Links
```

The original transcript MUST be preserved.

---

# 13. Structured Symptom Model

The AI should attempt to extract:

```text
Chief complaint
Duration
Onset
Location
Severity
Frequency
Pattern
Triggers
Relieving factors
Associated symptoms
Patient concerns
Patient-reported history
```

The system should distinguish:

### Patient stated

> "My headache is severe."

from:

### AI interpretation

> "High-severity headache."

The original statement should always remain available.

---

# 14. Dynamic Conversational Intake

This is one of the most important MVP features.

ClinSync should NOT ask a fixed 30-question questionnaire.

Instead:

```text
Patient Answer
      ↓
Extract Known Information
      ↓
Determine Missing Information
      ↓
Select Next Question
      ↓
Ask Patient
      ↓
Repeat
```

Example:

```text
Patient:
"I have stomach pain."

AI:
"When did the pain begin?"

Patient:
"About a week ago."

AI:
"Where do you feel the pain most strongly?"

Patient:
"Upper abdomen."

AI:
"Does anything make it worse?"

Patient:
"After eating."

AI:
"Have you experienced nausea or vomiting?"

...
```

The graph should terminate when sufficient information has been collected.

---

# 15. LangGraph State

The AI workflow should use a typed state object.

Example conceptual state:

```python
class ClinicalIntakeState:
    patient_id: str

    session_id: str

    raw_transcripts: list

    extracted_symptoms: list

    extracted_history: list

    extracted_medications: list

    processed_documents: list

    evidence_items: list

    missing_information: list

    questions_asked: list

    patient_answers: list

    specialty_candidates: list

    timeline_events: list

    doctor_brief: dict | None

    validation_results: dict | None

    status: str
```

The exact implementation can evolve, but the state must remain explicit and traceable.

---

# 16. Missing Information Engine

After each patient response:

```text
Known Information
        +
Existing Medical History
        +
Current Complaint
        ↓
Missing Information Detector
```

The system determines whether additional questions are useful.

Example:

```json
{
  "missing": [
    {
      "field": "duration",
      "priority": "high"
    },
    {
      "field": "current_medications",
      "priority": "medium"
    }
  ]
}
```

The questioning agent then chooses the next question.

---

# 17. Question Safety

The AI must NOT ask unnecessary or repetitive questions.

The system should maintain:

```text
questions_asked
answers_received
known_information
```

Before asking:

> **Have we already obtained this information?**

If yes, do not ask again.

---

# 18. Patient Clinical Memory

The clinical memory layer is the heart of ClinSync.

It should connect:

```text
Patient
 ├── Consultations
 ├── Symptoms
 ├── Conditions
 ├── Medications
 ├── Documents
 ├── Lab Results
 ├── Procedures
 ├── Voice Transcripts
 └── Timeline Events
```

The system should not simply store documents.

It should understand relationships between them.

---

# 19. Clinical Timeline

Example:

```text
2024
│
├── Condition recorded
│
2025
│
├── Consultation
├── Prescription
└── Lab Report
│
2026
│
├── New Prescription
├── New Report
└── Current Complaint
```

Timeline events should include:

```json
{
  "event_id": "evt_x",
  "patient_id": "pat_x",
  "event_type": "LAB_RESULT",
  "date": "...",
  "title": "...",
  "summary": "...",
  "source_ids": [],
  "confidence": 0.94
}
```

---

# 20. Medication Reconciliation

The system should compare medications across records.

Example:

```text
Previous
---------
Drug A — 500mg — twice daily

Current
-------
Drug A — 500mg — once daily
Drug B — 10mg — once daily
```

ClinSync should identify:

```text
DOSAGE_CHANGED
NEW_MEDICATION
DISCONTINUED_MEDICATION
POTENTIAL_DUPLICATE
```

These are **flags for review**, not autonomous clinical judgments.

---

# 21. Medical Trend Detection

The MVP should support basic longitudinal comparison for structured numerical medical values.

Example:

```text
Test: HbA1c

2024 → 6.1
2025 → 6.7
2026 → 7.2
```

The system can state:

> "The value increased across the available reports."

It should not automatically state:

> "The patient has deteriorating diabetes."

unless that conclusion is explicitly supported and appropriately handled by the clinical workflow.

The safe MVP behavior is:

**detect → visualize → cite → let doctor interpret.**

---

# 22. Specialty Routing

The system receives:

```text
Current complaint
+
Symptoms
+
Relevant history
+
Documents
```

and produces candidate specialties.

Example:

```json
{
  "specialties": [
    {
      "name": "Cardiology",
      "confidence": 0.82
    }
  ]
}
```

The system must not present this as a definitive diagnosis.

The hospital configuration can map:

```text
specialty
→ department
→ doctors
→ appointment slots
```

---

# 23. Appointment System

Entities:

```text
Doctor
Department
Specialty
Availability
Appointment
Patient
```

Example:

```text
GET /api/v1/doctors
GET /api/v1/specialties
GET /api/v1/appointments/slots
POST /api/v1/appointments
GET /api/v1/appointments/{id}
PATCH /api/v1/appointments/{id}
```

Appointment states:

```text
REQUESTED
CONFIRMED
RESCHEDULED
CANCELLED
COMPLETED
NO_SHOW
```

---

# 24. Doctor Notification

After appointment confirmation, the system prepares the doctor brief.

The doctor can receive:

```text
New patient consultation tomorrow

Patient: XXXXX
Specialty: Cardiology
Appointment: 10:30 AM

Pre-consultation brief available.

[Open ClinSync]
```

For the MVP, support:

* email
* SMS where configured

Do not put sensitive medical information into ordinary notification messages.

Notifications should direct the doctor to the secure dashboard.

---

# 25. Doctor Dashboard

The dashboard is the central professional interface.

The visual design should feel:

> **Clinical + premium + calm + extremely information-dense without looking cluttered.**

Avoid the appearance of:

* generic admin panels
* old hospital software
* excessive cards
* colorful AI dashboards
* unnecessary gradients
* childish medical illustrations

The interface should feel closer to a modern professional clinical workstation.

---

# 26. Doctor Home Screen

The doctor should see:

```text
GOOD MORNING, DR. [NAME]

Today's consultations
────────────────────────────────

10:00   Patient A
        Cardiology
        Pre-consultation ready

10:30   Patient B
        Cardiology
        New patient

11:00   Patient C
        Follow-up
        3 new documents

────────────────────────────────

Preparation
12 patients
9 briefs ready
2 awaiting patient information
1 requires review
```

---

# 27. 60-Second Patient Brief

The most important doctor screen.

Layout:

```text
┌───────────────────────────────────────────────┐
│ PATIENT                                       │
│ Age · Sex · Appointment                       │
├───────────────────────────────────────────────┤
│                                               │
│ WHY THEY ARE HERE                             │
│ Short current complaint                       │
│                                               │
├───────────────────────────────────────────────┤
│ RELEVANT HISTORY                              │
│ Important previous information                │
│                                               │
├──────────────────────┬────────────────────────┤
│ MEDICATIONS          │ RECENT REPORTS          │
│ ...                  │ ...                    │
├──────────────────────┴────────────────────────┤
│ TIMELINE                                      │
│ ─────●────────●────────●────────●────────     │
│                                               │
├───────────────────────────────────────────────┤
│ INFORMATION NEEDING REVIEW                    │
│ ⚠ ...                                         │
├───────────────────────────────────────────────┤
│ PATIENT'S OWN WORDS                           │
│ "..."                                         │
├───────────────────────────────────────────────┤
│ EVIDENCE                                     │
│ [View sources]                                │
└───────────────────────────────────────────────┘
```

---

# 28. Evidence System

Every major AI-generated statement should be connected to evidence.

Data model:

```json
{
  "claim_id": "claim_x",
  "claim": "Patient reports symptoms for 4 days",
  "source_type": "VOICE_TRANSCRIPT",
  "source_id": "transcript_x",
  "source_location": "00:42",
  "confidence": 0.97
}
```

For documents:

```json
{
  "source_type": "DOCUMENT",
  "document_id": "doc_x",
  "page": 2,
  "text_span": "..."
}
```

Doctor interaction:

```text
AI Statement
      ↓
[Evidence]
      ↓
Original Source
```

---

# 29. Evidence Graph

The backend should conceptually support:

```text
Patient
   │
   ├── Claim
   │     │
   │     └── Source
   │
   ├── Medication
   │     │
   │     └── Prescription
   │
   ├── Lab Result
   │     │
   │     └── Lab Report
   │
   └── Symptom
         │
         └── Voice Transcript
```

This gives ClinSync a major differentiator:

> **The AI doesn't merely generate information. It maintains a relationship between information and evidence.**

---

# 30. AI Summary Generation

The doctor brief should contain:

### 1. Current complaint

### 2. Symptom summary

### 3. Relevant history

### 4. Medication information

### 5. Recent documents

### 6. Relevant trends

### 7. Missing information

### 8. Patient's own words

### 9. Specialty routing

### 10. Evidence

The summary should be concise.

The doctor should not have to read a 1,500-word AI essay.

---

# 31. Summary Generation Rules

The AI must:

* never invent patient information
* never fabricate lab values
* never invent medications
* never silently modify patient statements
* distinguish reported information from inferred information
* attach evidence wherever possible
* preserve uncertainty
* avoid unnecessary medical speculation
* avoid autonomous diagnosis
* avoid autonomous treatment recommendations
* clearly flag missing information

---

# 32. AI Validation Layer

Before the doctor brief is published:

```text
Generated Summary
       ↓
Claim Extraction
       ↓
Evidence Matching
       ↓
Consistency Check
       ↓
Unsupported Claim Detection
       ↓
Final Validation
```

Example:

```json
{
  "status": "REVIEW_REQUIRED",
  "unsupported_claims": 1,
  "conflicting_claims": 0
}
```

If validation fails, the doctor should see:

> **Some AI-generated information requires verification.**

---

# 33. Doctor Correction

Every major AI section should be editable.

Example:

```text
Medication
────────────────────
AI: Medicine X — 10mg

[Edit]

Doctor:
Medicine X — 5mg
```

The backend should record:

```text
original_value
corrected_value
corrected_by
corrected_at
reason (optional)
```

Never overwrite the original AI output silently.

---

# 34. Consultation Session

When the appointment starts:

```text
Appointment
     ↓
Doctor opens patient
     ↓
Brief available
     ↓
Doctor reviews
     ↓
Consultation begins
```

The system should track the consultation state:

```text
SCHEDULED
CHECKED_IN
IN_PROGRESS
COMPLETED
CANCELLED
```

---

# 35. AI-Assisted Consultation Notes

After/during the consultation, the doctor can dictate:

> "Patient reports abdominal pain for one week..."

The AI generates a draft.

Example:

```text
CHIEF COMPLAINT

Abdominal pain for approximately one week.

HISTORY

...

RELEVANT INFORMATION

...

PLAN

...

FOLLOW-UP

...
```

The doctor must explicitly approve the final note.

---

# 36. Patient Memory Update

After doctor approval:

```text
Consultation
      ↓
Final Doctor Note
      ↓
Structured Information
      ↓
Patient Clinical Memory
      ↓
Timeline Updated
```

This closes the loop.

The next appointment therefore starts with more information than the previous appointment.

---

# 37. Database Design

The backend should use a relational database for authoritative structured data.

Recommended conceptual entities:

```text
users
patients
doctors
departments
specialties
patient_consents
patient_biometrics
documents
document_pages
document_extractions
voice_sessions
transcripts
clinical_entities
symptoms
conditions
medications
lab_results
timeline_events
evidence
ai_claims
ai_runs
intake_sessions
intake_questions
intake_answers
appointments
doctor_briefs
consultations
consultation_notes
doctor_corrections
audit_logs
notifications
```

---

# 38. Patient Table

```text
patients

id
user_id
external_patient_id
date_of_birth
gender
created_at
updated_at
```

---

# 39. Documents Table

```text
documents

id
patient_id
file_name
mime_type
storage_key
document_type
classification_confidence
processing_status
uploaded_at
processed_at
```

Processing status:

```text
UPLOADED
PROCESSING
PROCESSED
FAILED
REVIEW_REQUIRED
```

---

# 40. Clinical Entities

Generic structure:

```text
clinical_entities

id
patient_id
entity_type
value
normalized_value
confidence
source_id
source_type
created_at
```

Entity types:

```text
SYMPTOM
CONDITION
MEDICATION
LAB_RESULT
PROCEDURE
ALLERGY
VITAL
OTHER
```

---

# 41. Evidence Table

```text
evidence

id
patient_id
source_type
source_id
location
text_excerpt
confidence
created_at
```

This table is fundamental to the evidence architecture.

---

# 42. AI Runs

Every AI workflow should be traceable.

```text
ai_runs

id
patient_id
workflow_type
model
model_version
input_reference
output_reference
latency_ms
token_usage
status
created_at
```

This enables:

* debugging
* evaluation
* cost tracking
* observability
* model comparison

---

# 43. Audit Logs

```text
audit_logs

id
actor_id
actor_role
action
resource_type
resource_id
timestamp
ip_hash
metadata
```

Examples:

```text
PATIENT_VIEWED_RECORD
DOCUMENT_UPLOADED
DOCTOR_VIEWED_BRIEF
DOCTOR_EDITED_CLAIM
CONSENT_GRANTED
CONSENT_REVOKED
SUMMARY_GENERATED
```

Never store unnecessary sensitive data in audit metadata.

---

# 44. API Architecture

All APIs should be versioned.

Base:

```text
/api/v1
```

---

## Authentication

```http
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
GET  /auth/me
```

---

## Patients

```http
GET    /patients/me
PATCH  /patients/me
GET    /patients/me/timeline
GET    /patients/me/documents
GET    /patients/me/medications
GET    /patients/me/appointments
```

---

## Identity

```http
POST /identity/face/enroll
POST /identity/face/verify
POST /identity/face/match
```

---

## Documents

```http
POST   /documents
GET    /documents
GET    /documents/{id}
DELETE /documents/{id}
POST   /documents/{id}/process
GET    /documents/{id}/status
GET    /documents/{id}/evidence
```

---

## Voice

```http
POST /voice/sessions
POST /voice/sessions/{id}/audio
POST /voice/sessions/{id}/transcribe
GET  /voice/sessions/{id}
GET  /voice/sessions/{id}/transcript
```

---

## Intake

```http
POST /intake/sessions
GET  /intake/sessions/{id}
POST /intake/sessions/{id}/answer
GET  /intake/sessions/{id}/next-question
POST /intake/sessions/{id}/complete
```

---

## Clinical Memory

```http
GET /clinical-memory/{patient_id}
GET /clinical-memory/{patient_id}/timeline
GET /clinical-memory/{patient_id}/medications
GET /clinical-memory/{patient_id}/labs
GET /clinical-memory/{patient_id}/symptoms
```

---

## Specialty

```http
POST /routing/analyze
GET  /specialties
GET  /specialties/{id}/doctors
```

---

## Appointments

```http
GET  /appointments/slots
POST /appointments
GET  /appointments/{id}
PATCH /appointments/{id}
DELETE /appointments/{id}
```

---

## Doctor

```http
GET /doctor/dashboard
GET /doctor/appointments
GET /doctor/patients/{id}/brief
GET /doctor/patients/{id}/timeline
GET /doctor/patients/{id}/documents
GET /doctor/patients/{id}/evidence
POST /doctor/claims/{id}/correction
```

---

## Consultation

```http
POST /consultations
GET  /consultations/{id}
POST /consultations/{id}/notes/draft
PATCH /consultations/{id}/notes
POST /consultations/{id}/complete
```

---

# 45. API Response Format

Use a consistent response format.

Success:

```json
{
  "success": true,
  "data": {},
  "meta": {}
}
```

Error:

```json
{
  "success": false,
  "error": {
    "code": "DOCUMENT_PROCESSING_FAILED",
    "message": "The document could not be processed."
  }
}
```

Never expose raw internal exceptions to users.

---

# 46. Backend Architecture

Recommended structure:

```text
backend/
│
├── app/
│   │
│   ├── main.py
│   │
│   ├── config/
│   │   ├── settings.py
│   │   └── logging.py
│   │
│   ├── api/
│   │   ├── auth.py
│   │   ├── patients.py
│   │   ├── identity.py
│   │   ├── documents.py
│   │   ├── voice.py
│   │   ├── intake.py
│   │   ├── clinical_memory.py
│   │   ├── routing.py
│   │   ├── appointments.py
│   │   ├── doctor.py
│   │   └── consultations.py
│   │
│   ├── models/
│   │
│   ├── schemas/
│   │
│   ├── repositories/
│   │
│   ├── services/
│   │   ├── patient_service.py
│   │   ├── document_service.py
│   │   ├── voice_service.py
│   │   ├── appointment_service.py
│   │   └── clinical_memory_service.py
│   │
│   ├── ai/
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── nodes/
│   │   ├── prompts/
│   │   ├── extractors/
│   │   ├── validators/
│   │   └── summarizers/
│   │
│   ├── storage/
│   │
│   ├── security/
│   │
│   ├── workers/
│   │
│   └── utils/
│
├── tests/
│
├── migrations/
│
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

# 47. Service Separation

The backend should not become one enormous `main.py`.

Use:

```text
API Layer
   ↓
Service Layer
   ↓
Repository Layer
   ↓
Database
```

For AI:

```text
Service Layer
   ↓
AI Orchestrator
   ↓
LangGraph
   ↓
Specialized Nodes
```

---

# 48. Background Processing

Document processing and AI workloads should not block normal API requests.

Example:

```text
POST /documents
       ↓
Return immediately
       ↓
Background Job
       ↓
OCR
       ↓
Extraction
       ↓
Validation
       ↓
Clinical Memory
```

The frontend polls or receives status updates.

Example:

```text
PROCESSING
     ↓
EXTRACTING
     ↓
VALIDATING
     ↓
COMPLETED
```

---

# 49. Caching

Caching should be used carefully.

Potential cache candidates:

* doctor availability
* specialty configuration
* non-sensitive metadata
* temporary workflow state

Do **not** casually cache sensitive medical information.

Every cache entry containing sensitive information must have:

* explicit TTL
* secure storage
* access control
* invalidation strategy

---

# 50. Observability

Every AI workflow should be observable.

Track:

```text
Request ID
Patient-safe workflow ID
AI workflow
Model
Latency
Token usage
Status
Validation result
Error
```

Do not log raw medical information.

The system should make debugging possible without creating another privacy risk.

---

# 51. AI Model Abstraction

Do not hard-code the application to one model provider.

Use an abstraction:

```text
LLMProvider
 ├── Gemini
 ├── OtherProvider
 └── LocalModel
```

Similarly:

```text
SpeechProvider
OCRProvider
EmbeddingProvider
```

This allows models to be changed without rewriting the application.

---

# 52. Prompt Architecture

Prompts should NOT be scattered throughout Python files.

Use:

```text
ai/prompts/
├── intake/
├── extraction/
├── summary/
├── routing/
├── validation/
└── consultation/
```

Each prompt should have:

* purpose
* input schema
* output schema
* safety rules
* version
* test cases

---

# 53. Structured AI Output

AI should return structured output whenever possible.

Example:

```json
{
  "symptoms": [
    {
      "name": "headache",
      "duration": "4 days",
      "severity": null,
      "source": "transcript_123"
    }
  ]
}
```

Avoid parsing unpredictable free-form AI text whenever structured output can be used.

---

# 54. Hallucination Prevention

Use multiple safeguards:

### 1. Evidence-first extraction

Extract from source material.

### 2. Structured output

Constrain model responses.

### 3. Source linking

Every important entity receives a source.

### 4. Validation

Check generated claims against evidence.

### 5. Doctor review

Clinical information remains human-reviewed.

---

# 55. Security Model

Roles:

```text
PATIENT
DOCTOR
ADMIN
```

Example permissions:

| Resource          | Patient |        Doctor |      Admin |
| ----------------- | ------: | ------------: | ---------: |
| Own profile       |       ✓ |             — |          — |
| Own documents     |       ✓ | Assigned only | Controlled |
| Patient brief     |       — |             ✓ | Controlled |
| Clinical timeline |     Own |      Assigned | Controlled |
| Appointments      |     Own |      Assigned |          ✓ |
| Audit logs        | Limited |       Limited |          ✓ |
| User management   |       — |             — |          ✓ |

Authorization must happen at the backend.

Never trust frontend role checks.

---

# 56. Consent Model

Consent should be explicit.

Example:

```json
{
  "patient_id": "...",
  "scope": "DOCTOR_CONSULTATION",
  "granted_to": "...",
  "granted_at": "...",
  "expires_at": "...",
  "revoked_at": null
}
```

Every sensitive access should be checked against authorization rules.

---

# 57. Error Handling

Every major workflow needs graceful failure.

Examples:

### OCR failure

```text
We couldn't read this document.

[Try Again]
[Upload Another Version]
```

### Speech failure

```text
We couldn't process the recording.

[Record Again]
[Type Instead]
```

### AI failure

```text
We couldn't generate the summary right now.

Your original information is safe.
A doctor can still access the submitted records.
```

Never lose patient data because an AI model failed.

---

# 58. AI Failure Principle

The system must degrade gracefully.

```text
AI AVAILABLE
     ↓
Full intelligent workflow

AI UNAVAILABLE
     ↓
Documents + transcript + structured records
     ↓
Doctor can still access raw information
```

**The doctor should never be blocked from seeing the patient's original information because the AI failed.**

This is a critical architectural principle.

---

# 59. Testing Strategy

## Unit Tests

Test:

* authentication
* authorization
* document validation
* entity extraction
* timeline generation
* medication reconciliation
* appointment logic
* evidence linking

## Integration Tests

Test:

```text
Upload document
→ process
→ extract
→ store
→ retrieve
→ show evidence
```

## AI Evaluation

Create a fixed evaluation dataset containing:

* sample reports
* prescriptions
* transcripts
* known clinical entities
* expected extraction results

Measure:

```text
Extraction Accuracy
Evidence Accuracy
Summary Accuracy
Unsupported Claim Rate
Question Repetition Rate
Doctor Correction Rate
```

---

# 60. Demo Dataset

For development and hackathon demonstration, create synthetic patients.

Example:

```text
Patient A
├── 3 previous consultations
├── 4 reports
├── 2 prescriptions
├── 1 voice intake
└── current appointment
```

Use **synthetic/fake medical data only** for development and demonstrations.

Never use real patient information in the repository.

---

# 61. Seed Data

Provide a development seed script:

```bash
python scripts/seed.py
```

It should create:

```text
Demo Patients
Demo Doctors
Demo Specialties
Demo Documents
Demo Appointments
Demo Clinical Timelines
Demo AI Briefs
```

This allows the complete application to run immediately after setup.

---

# 62. Environment Configuration

Provide:

```text
.env.example
```

Example:

```env
APP_ENV=development

DATABASE_URL=
REDIS_URL=

JWT_SECRET=

STORAGE_BUCKET=

LLM_API_KEY=
LLM_MODEL=

STT_API_KEY=
STT_MODEL=

OCR_API_KEY=

EMAIL_PROVIDER=
SMS_PROVIDER=

VECTOR_DATABASE_URL=

OBSERVABILITY_PUBLIC_KEY=
OBSERVABILITY_SECRET_KEY=
```

Never commit actual secrets.

---

# 63. Docker Development

The project should support:

```bash
docker compose up
```

Services can include:

```text
backend
database
redis
object-storage
```

AI providers remain externally configurable.

---

# 64. API Documentation

FastAPI should expose:

```text
/api/docs
/api/redoc
```

Every endpoint should include:

* description
* authentication requirements
* request schema
* response schema
* possible errors
* example request
* example response

---

# 65. Frontend-Backend Contract

The backend must provide stable contracts.

The frontend should never directly access the database.

```text
Mobile App
     ↓
REST API
     ↓
Backend
     ↓
Services
     ↓
Database / AI / Storage
```

---

# 66. Backend Build Order

Antigravity should implement the backend in this order.

## Phase 1 — Foundation

```text
Project setup
FastAPI
Configuration
Database
Migrations
Authentication
RBAC
Logging
Error handling
```

## Phase 2 — Patient

```text
Patient profile
Identity
Consent
Patient records
```

## Phase 3 — Documents

```text
Upload
Storage
OCR
Classification
Extraction
Evidence
```

## Phase 4 — Voice

```text
Voice session
Audio upload
STT
Transcript
Clinical extraction
```

## Phase 5 — AI Intake

```text
LangGraph
State
Question generation
Missing information
Conversation loop
```

## Phase 6 — Clinical Memory

```text
Entities
Timeline
Medication history
Lab values
Trend detection
```

## Phase 7 — Routing

```text
Specialty classification
Doctor mapping
Availability
Appointments
```

## Phase 8 — Doctor

```text
Doctor dashboard APIs
Patient brief
Evidence
Timeline
Corrections
```

## Phase 9 — Consultation

```text
Consultation
AI notes
Doctor approval
Memory update
```

## Phase 10 — Safety & Evaluation

```text
Validation
AI evaluations
Audit logs
Observability
Performance tests
```

---

# 67. Backend Definition of Done

The backend is NOT considered complete merely because the API starts.

The MVP is complete when this entire flow works:

```text
NEW PATIENT
    ↓
REGISTER
    ↓
IDENTIFY
    ↓
CREATE PROFILE
    ↓
UPLOAD DOCUMENT
    ↓
DOCUMENT PROCESSED
    ↓
PATIENT SPEAKS
    ↓
TRANSCRIPT CREATED
    ↓
AI EXTRACTS INFORMATION
    ↓
AI DETECTS MISSING INFORMATION
    ↓
PATIENT ANSWERS FOLLOW-UP
    ↓
CLINICAL TIMELINE CREATED
    ↓
SPECIALTY DETERMINED
    ↓
APPOINTMENT BOOKED
    ↓
DOCTOR BRIEF GENERATED
    ↓
EVIDENCE VALIDATED
    ↓
DOCTOR OPENS BRIEF
    ↓
DOCTOR REVIEWS/EDITs
    ↓
CONSULTATION
    ↓
AI DRAFTS NOTES
    ↓
DOCTOR APPROVES
    ↓
PATIENT MEMORY UPDATED
```

If any stage is disconnected, the MVP is incomplete.

---

# 68. Product Design Direction

ClinSync should **feel like a premium healthcare technology product**, not a student CRUD application.

## Visual personality

### Primary

* White
* Near-black
* Cool blue accents
* Neutral grays

### Typography

Use a sophisticated modern sans-serif.

Strong hierarchy:

```text
Large editorial headings
     ↓
Clear section headings
     ↓
Compact metadata
     ↓
Readable clinical information
```

---

# 69. Design Principles

## Calm

Healthcare interfaces should not feel noisy.

## Precise

Every element should have a reason.

## Human

The patient should feel that the system is helping them communicate with their doctor.

## Trustworthy

Avoid exaggerated AI visuals.

## Premium

Use:

* subtle borders
* generous whitespace
* smooth transitions
* restrained shadows
* elegant typography
* carefully designed states

Avoid:

* excessive gradients
* random glassmorphism
* giant floating AI brains
* unnecessary 3D objects
* childish medical icons
* generic dashboard templates

---

# 70. Patient App Visual Experience

The patient experience should feel like:

```text
Welcome
   ↓
Identify
   ↓
Your Medical Memory
   ↓
What's new?
   ↓
Speak naturally
   ↓
Review information
   ↓
Appointment
   ↓
You're ready
```

The application should use progressive disclosure.

Do not show 30 fields at once.

---

# 71. Doctor Dashboard Visual Experience

The doctor interface should prioritize:

```text
WHO
WHY
WHAT CHANGED
WHAT MATTERS
WHERE DID THIS COME FROM?
WHAT NEEDS REVIEW?
```

Every screen should answer one of these questions.

---

# 72. Motion Design

Animations should be subtle and purposeful.

Examples:

### Document processing

```text
Uploading
   ↓
Scanning
   ↓
Reading
   ↓
Structuring
   ↓
Ready
```

### Clinical timeline

Events should appear smoothly as the timeline loads.

### Evidence

When a doctor clicks a claim:

```text
Claim
 ↓
Source highlight
 ↓
Original document
```

### AI intake

Use a calm conversation transition rather than a typical chatbot loading spinner.

---

# 73. Empty States

Every empty state should explain what to do.

Bad:

> No data.

Good:

> **Your clinical memory is ready to grow.**

> Upload a previous report or tell us about your current concern.

---

# 74. Loading States

Never show a blank screen.

Examples:

```text
Reading your document...
Extracting information...
Building your timeline...
Preparing your doctor brief...
```

These states should reflect the actual backend workflow.

---

# 75. MVP Scope Boundary

The following features are intentionally **NOT part of the MVP**.

They can be added later:

* advanced hospital EHR integrations
* FHIR production interoperability
* insurance processing
* billing
* pharmacy integration
* wearable integration
* remote patient monitoring
* advanced predictive analytics
* autonomous clinical recommendations
* automated diagnosis
* treatment recommendation engine
* large-scale multi-hospital deployment
* advanced biometric infrastructure
* fully autonomous emergency triage
* population-level analytics

The MVP must remain focused on:

> **Pre-consultation → Clinical Memory → Doctor Brief → Consultation → Memory Update**

---

# 76. Future Architecture

The architecture should leave room for:

```text
                  CLINSYNC
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    PATIENT       DOCTOR       HOSPITAL
        │            │            │
        ▼            ▼            ▼
     MOBILE       DASHBOARD      EHR
        │            │            │
        └────────────┼────────────┘
                     ▼
              CLINICAL MEMORY
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
      Voice       Documents     Records
        │            │            │
        └────────────┼────────────┘
                     ▼
                AI ENGINE
```

The MVP should establish this foundation without attempting to implement every future capability.

---

# 77. The Most Important Product Metric

ClinSync should ultimately optimize for:

> ## **Time saved without losing clinically relevant information.**

Not:

* number of AI calls
* number of agents
* number of features
* number of tokens
* amount of generated text

The product succeeds when:

```text
Traditional Workflow
        ↓
More time spent collecting information

ClinSync
        ↓
Information prepared beforehand
        ↓
Doctor spends more time on the patient
```

---

# 78. North Star Experience

Imagine a doctor opening the app at 10:25 AM.

Their 10:30 patient is coming in.

Instead of opening six PDFs, asking twenty questions, and searching old records, the doctor sees:

```text
────────────────────────────────────────────

             PATIENT BRIEF

            [Patient Name]

Appointment
10:30 AM · Cardiology

────────────────────────────────────────────

WHY TODAY?

Patient reports intermittent chest discomfort
for approximately three days.

────────────────────────────────────────────

RELEVANT HISTORY

• Previous hypertension record
• Previous cardiology consultation
• Current medication history available

────────────────────────────────────────────

WHAT CHANGED?

Recent report contains measurements that differ
from the previous available report.

[View Trend]

────────────────────────────────────────────

PATIENT'S OWN WORDS

"I've been experiencing..."

[Listen] [View Transcript]

────────────────────────────────────────────

INFORMATION TO VERIFY

⚠ Medication adherence unclear

────────────────────────────────────────────

EVIDENCE

6 claims · 6 sources

[Review Evidence]

────────────────────────────────────────────

             [START CONSULTATION]

────────────────────────────────────────────
```

That is the product.

Not a chatbot.

Not an AI doctor.

Not a document scanner.

**A clinical preparation system.**

---

# 79. Product Positioning

### One-line description

> **ClinSync prepares a patient's clinical picture before the doctor walks into the consultation.**

### Short description

> ClinSync is an AI-assisted pre-consultation platform that combines patient voice, medical documents, previous records and longitudinal clinical memory into an evidence-backed doctor brief.

### Pitch

> **Doctors shouldn't spend valuable consultation time searching through paperwork and repeating questions. ClinSync collects and organizes the patient's information before the consultation, then gives the doctor a concise, evidence-backed clinical brief — allowing the consultation to focus on the patient rather than the paperwork.**

---

# 80. The ClinSync Promise

> ### **The patient tells the story once.**
>
> ### **ClinSync remembers it.**
>
> ### **The doctor gets the relevant picture.**
>
> ### **The doctor makes the decision.**

---

# 81. Engineering Principles

Antigravity must follow these principles while implementing the project.

### Principle 1 — Backend First, But Contract Driven

Every frontend feature must have a defined backend contract.

### Principle 2 — No Giant Files

Keep modules focused.

### Principle 3 — Typed Everything

Use Pydantic schemas and explicit types.

### Principle 4 — Evidence First

AI-generated clinical information must remain traceable.

### Principle 5 — Human in the Loop

AI assists; doctors approve.

### Principle 6 — Fail Gracefully

AI failure must never destroy or hide original patient information.

### Principle 7 — Privacy by Design

Do not treat healthcare data like ordinary application data.

### Principle 8 — Observable AI

Every AI workflow should be measurable and debuggable.

### Principle 9 — Async Where Necessary

Document processing and long AI workflows should not block API requests.

### Principle 10 — Build for the Demo, Architect for the Future

The MVP should be achievable, but the architecture should not make future expansion painful.

---

# 82. Final Implementation Directive

**Antigravity should treat this README as the source of truth for the ClinSync MVP backend.**

Do not:

* invent unrelated features
* build autonomous diagnosis
* build autonomous treatment
* turn the application into a generic chatbot
* create an overcomplicated microservice architecture prematurely
* hard-code one AI provider into every module
* store AI output without evidence
* allow frontend-only authorization
* expose medical data in logs
* create fake production integrations without clearly separating them

Do:

* build the complete patient-to-doctor workflow
* create clean API contracts
* implement the database properly
* implement LangGraph orchestration
* preserve raw source data
* link AI claims to evidence
* implement doctor correction
* implement audit logging
* implement background processing
* provide seed/demo data
* provide tests
* provide `.env.example`
* provide Docker development setup
* expose complete FastAPI documentation
* keep the architecture modular
* make the backend ready for the mobile application and doctor dashboard

---

# 83. Final MVP Architecture

```text
                         ┌──────────────────────┐
                         │      CLINSYNC        │
                         │                      │
                         │ "Know the patient    │
                         │  before you meet     │
                         │  the patient."       │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
               PATIENT APP                    DOCTOR APP
                    │                               │
          ┌─────────┼─────────┐             ┌──────┼──────┐
          │         │         │             │      │      │
        Voice    Documents  Identity      Brief Timeline Evidence
          │         │         │             │      │      │
          └─────────┼─────────┘             └──────┼──────┘
                    │                               │
                    ▼                               │
             FASTAPI BACKEND                        │
                    │                               │
          ┌─────────┼─────────┐                     │
          │         │         │                     │
       Storage   Database   Workers                 │
          │         │         │                     │
          └─────────┼─────────┘                     │
                    │                               │
                    ▼                               │
              LANGGRAPH AI ENGINE                  │
                    │                               │
        ┌───────────┼───────────┐                   │
        ▼           ▼           ▼                   │
     Voice       Documents   Clinical               │
    Pipeline     Pipeline    Memory                 │
        │           │           │                   │
        └───────────┼───────────┘                   │
                    ▼                               │
             Evidence Layer                         │
                    │                               │
                    ▼                               │
             Validation Layer                       │
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
                              DOCTOR REVIEW
                                    │
                                    ▼
                            CLINICAL DECISION
                                    │
                                    ▼
                           PATIENT MEMORY
```

---

# 84. Final Statement

ClinSync exists to solve one simple problem:

> **A doctor's most valuable resource is time with the patient.**

The system therefore moves information gathering, document organization, history preparation and administrative work **before the consultation**.

The patient speaks naturally.

Documents become structured information.

Past consultations become a timeline.

Important changes become visible.

Missing information is identified.

Evidence remains traceable.

The doctor receives a concise brief.

The doctor reviews it.

The doctor makes the decision.

And after the consultation, the patient's clinical memory becomes richer for the next visit.

---

<div align="center">

# **ClinSync**

### **Know the patient before you meet the patient.**

**Patient → Memory → Intelligence → Doctor → Care**

</div>
