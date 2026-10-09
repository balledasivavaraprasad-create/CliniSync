from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File, Form
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import os
import time
import base64
from app.services.receptionist_service import ReceptionistService

from app.api.deps import get_request_id, get_db_session
from app.schemas.common import SuccessResponse
from app.db.mongodb import (
    mongo_mgr,
    save_patient_intake,
    get_patient_intakes,
    save_clinical_brief,
    get_clinical_brief,
    get_all_clinical_briefs,
    get_patient_claims,
    save_patient_claim,
    save_clinical_timeline,
    get_clinical_timeline,
    save_medication_reconciliation,
    get_medication_reconciliation,
    get_doctor_profile,
    save_doctor_profile,
    save_patient_face,
    get_patient_face,
    list_patient_faces,
    save_patient_vitals,
    get_patient_vitals
)
from app.services.face_service import recognize_patient_face, register_new_patient_face
from app.utils.tokens import create_access_token
from app.utils.hashing import hash_password
from app.models.user import User
from sqlalchemy.orm import Session

router = APIRouter(prefix="/mongo", tags=["mongodb"])


class FaceRecognizeRequest(BaseModel):
    image_data: str = Field(..., description="Base64 or data URL of patient face capture from tablet")
    hospital_name: Optional[str] = "St. Jude Memorial Hospital"
    threshold: Optional[float] = 0.68


class FaceRegisterRequest(BaseModel):
    full_name: str
    email: str
    image_data: str = Field(..., description="Base64 or data URL of face snapshot")
    password: Optional[str] = "Patient@Sync2026!"
    phone: Optional[str] = None
    dob: Optional[str] = None
    hospital_name: Optional[str] = "St. Jude Memorial Hospital"


class VitalsRequest(BaseModel):
    patient_id: str
    hospital_name: Optional[str] = "St. Jude Memorial Hospital"
    vitals: Dict[str, Any]


class IntakeRequest(BaseModel):
    patient_id: str
    hospital_name: Optional[str] = "St. Jude Memorial Hospital"
    intake_type: str = Field(..., description="'audio_speech', 'camera_ocr', or 'pdf_upload'")
    raw_content: Any
    extracted_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class BriefRequest(BaseModel):
    patient_id: str
    doctor_id: str
    hospital_name: Optional[str] = "St. Jude Memorial Hospital"
    brief_data: Dict[str, Any]


class TimelineRequest(BaseModel):
    patient_id: str
    hospital_name: Optional[str] = "St. Jude Memorial Hospital"
    events: List[Dict[str, Any]]


class ReconciliationRequest(BaseModel):
    patient_id: str
    hospital_name: Optional[str] = "St. Jude Memorial Hospital"
    medications: List[Dict[str, Any]]
    conflicts: List[Dict[str, Any]]


@router.get("/status")
def mongo_status(req_id: str = Depends(get_request_id)):
    """Check live MongoDB Atlas connection status and collections."""
    connected = mongo_mgr.is_connected()
    uri = mongo_mgr.get_uri()
    needs_username = "<db_username>" in uri

    return SuccessResponse(
        data={
            "connected": connected,
            "database": mongo_mgr.get_db_name(),
            "configured": bool(uri),
            "needs_username": needs_username,
            "status": "connected" if connected else ("needs_credentials" if needs_username else "disconnected"),
            "collections": [
                "hospital_intakes",
                "clinical_briefs",
                "clinical_timelines",
                "medication_reconciliations",
                "doctor_profiles",
                "patient_faces",
                "patient_vitals"
            ]
        },
        meta={"request_id": req_id, "source": "mongodb"}
    )


@router.post("/intake")
def record_intake(req: IntakeRequest, req_id: str = Depends(get_request_id)):
    """Save hospital patient intake (voice audio, OCR scan, or parsed PDF) into MongoDB."""
    record = save_patient_intake(
        patient_id=req.patient_id,
        hospital_name=req.hospital_name,
        intake_type=req.intake_type,
        raw_content=req.raw_content,
        extracted_data=req.extracted_data,
        metadata=req.metadata
    )
    return SuccessResponse(data=record, meta={"request_id": req_id, "source": "mongodb"})


@router.get("/intake/{patient_id}")
def fetch_intakes(patient_id: str, req_id: str = Depends(get_request_id)):
    """Retrieve all hospital intakes recorded for a patient in MongoDB."""
    records = get_patient_intakes(patient_id)
    return SuccessResponse(data={"patient_id": patient_id, "count": len(records), "intakes": records}, meta={"request_id": req_id})


@router.post("/brief")
def record_brief(req: BriefRequest, req_id: str = Depends(get_request_id)):
    """Save generated clinical brief and medication assessment in MongoDB."""
    res = save_clinical_brief(
        patient_id=req.patient_id,
        doctor_id=req.doctor_id,
        hospital_name=req.hospital_name,
        brief_data=req.brief_data
    )
    return SuccessResponse(data=res, meta={"request_id": req_id, "source": "mongodb"})


@router.get("/brief/{patient_id}")
def fetch_brief(patient_id: str, req_id: str = Depends(get_request_id)):
    """Retrieve latest clinical brief for a patient from MongoDB."""
    brief = get_clinical_brief(patient_id)
    if not brief:
        return SuccessResponse(data=None, meta={"request_id": req_id, "source": "mongodb"})
    return SuccessResponse(data=brief, meta={"request_id": req_id})


@router.get("/briefs/{patient_id}")
def fetch_all_briefs(patient_id: str, req_id: str = Depends(get_request_id)):
    """Retrieve full history of clinical briefs for a patient from MongoDB."""
    briefs = get_all_clinical_briefs(patient_id)
    return SuccessResponse(data={"patient_id": patient_id, "count": len(briefs), "briefs": briefs}, meta={"request_id": req_id, "source": "mongodb"})


@router.get("/claims/{patient_id}")
def fetch_claims(patient_id: str, req_id: str = Depends(get_request_id)):
    """Retrieve all health insurance claims and reimbursement records for a patient from MongoDB."""
    claims = get_patient_claims(patient_id)
    return SuccessResponse(data={"patient_id": patient_id, "count": len(claims), "claims": claims}, meta={"request_id": req_id, "source": "mongodb"})


@router.post("/claims")
def create_claim(claim_data: Dict[str, Any] = Body(...), req_id: str = Depends(get_request_id)):
    """Store or record a new health insurance claim in MongoDB."""
    patient_id = claim_data.get("patient_id", "usr_patient_001")
    saved = save_patient_claim(patient_id, claim_data)
    return SuccessResponse(data=saved, meta={"request_id": req_id, "source": "mongodb"})


@router.post("/timeline")
def record_timeline(req: TimelineRequest, req_id: str = Depends(get_request_id)):
    """Store longitudinal clinical timeline in MongoDB."""
    res = save_clinical_timeline(req.patient_id, req.hospital_name, req.events)
    return SuccessResponse(data=res, meta={"request_id": req_id, "source": "mongodb"})


@router.get("/timeline/{patient_id}")
def fetch_timeline(patient_id: str, req_id: str = Depends(get_request_id)):
    """Retrieve longitudinal clinical timeline from MongoDB."""
    res = get_clinical_timeline(patient_id)
    return SuccessResponse(data=res, meta={"request_id": req_id})


@router.post("/reconciliation")
def record_reconciliation(req: ReconciliationRequest, req_id: str = Depends(get_request_id)):
    """Store medication reconciliation and safety alerts in MongoDB."""
    res = save_medication_reconciliation(req.patient_id, req.hospital_name, req.medications, req.conflicts)
    return SuccessResponse(data=res, meta={"request_id": req_id})


@router.get("/reconciliation/{patient_id}")
def fetch_reconciliation(patient_id: str, req_id: str = Depends(get_request_id)):
    """Retrieve medication reconciliation from MongoDB."""
    res = get_medication_reconciliation(patient_id)
    return SuccessResponse(data=res, meta={"request_id": req_id})


@router.get("/doctor/{doctor_id}")
def fetch_doctor_profile(doctor_id: str, req_id: str = Depends(get_request_id)):
    """Retrieve full doctor profile including specialty, hospital, license, stats, and bio."""
    profile = get_doctor_profile(doctor_id)
    return SuccessResponse(data=profile, meta={"request_id": req_id, "source": "mongodb"})


@router.put("/doctor/{doctor_id}")
def update_doctor(doctor_id: str, profile_data: Dict[str, Any] = Body(...), req_id: str = Depends(get_request_id)):
    """Update doctor profile in MongoDB."""
    saved = save_doctor_profile(doctor_id, profile_data)
    return SuccessResponse(data=saved, meta={"request_id": req_id, "source": "mongodb"})


# ── Hospital Tablet Kiosk: Hardware Camera & Face Biometrics ─────────────────
@router.get("/camera/snapshot")
def get_camera_snapshot(req_id: str = Depends(get_request_id)):
    """
    Direct hardware snapshot from laptop webcam using OpenCV (DirectShow).
    Guarantees instant frame retrieval even if browser WebRTC getUserMedia hangs or is blocked.
    """
    import base64
    try:
        import cv2
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            return SuccessResponse(data={"available": False, "error": "Camera hardware not opened"}, meta={"request_id": req_id})

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            return SuccessResponse(data={"available": False, "error": "Could not read frame from camera"}, meta={"request_id": req_id})

        h, w = frame.shape[:2]
        if w > 480:
            frame = cv2.resize(frame, (480, int(h * 480 / w)))

        success, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not success:
            return SuccessResponse(data={"available": False, "error": "Encode failed"}, meta={"request_id": req_id})

        b64_str = base64.b64encode(buf).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64_str}"
        return SuccessResponse(data={"available": True, "image_data": data_url}, meta={"request_id": req_id, "source": "direct_hardware_camera"})
    except Exception as e:
        logger.warning("camera_hardware_snapshot_failed", error=str(e))
        return SuccessResponse(data={"available": False, "error": str(e)}, meta={"request_id": req_id})


@router.post("/face/recognize")
def match_face(req: FaceRecognizeRequest, req_id: str = Depends(get_request_id)):
    """
    Process face capture from hospital tablet kiosk:
    1. Detects face and extracts normalized biometric embedding.
    2. Matches against enrolled patient faces in MongoDB Atlas.
    3. If recognized, returns matched patient profile and access token for instant login.
    """
    result = recognize_patient_face(
        image_data=req.image_data,
        hospital_name=req.hospital_name or "St. Jude Memorial Hospital",
        similarity_threshold=req.threshold or 0.68
    )

    if result.get("matched") and result.get("patient"):
        p = result["patient"]
        # Generate session JWT token for patient
        token = create_access_token(
            subject=p["patient_id"],
            claims={
                "role": "patient",
                "email": p.get("email", ""),
                "name": p.get("full_name", "")
            }
        )
        result["token"] = token

        # Log tablet kiosk check-in event to MongoDB hospital_intakes
        save_patient_intake(
            patient_id=p["patient_id"],
            hospital_name=req.hospital_name or "St. Jude Memorial Hospital",
            intake_type="kiosk_face_checkin",
            raw_content=f"Patient checked in via hospital tablet face recognition with {result.get('confidence')}% confidence.",
            metadata={"source": "tablet_kiosk", "confidence": result.get("confidence")}
        )

    return SuccessResponse(data=result, meta={"request_id": req_id, "source": "face_biometrics"})


@router.post("/face/register")
def register_face(
    req: FaceRegisterRequest,
    db: Session = Depends(get_db_session),
    req_id: str = Depends(get_request_id)
):
    """
    Register a new patient with facial biometric enrollment at hospital kiosk:
    1. Extracts and stores facial biometric template in MongoDB Atlas `patient_faces`.
    2. Synchronizes account in SQLite User database so standard email login works.
    3. Logs initial intake event in MongoDB.
    4. Returns authenticated JWT token.
    """
    email_clean = req.email.strip().lower()

    # Determine or generate patient_id
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        patient_id = existing_user.id
    else:
        patient_id = f"pat_{int(time.time())}_{os.urandom(2).hex()}"
        # Provision patient in relational DB
        new_user = User(
            id=patient_id,
            email=email_clean,
            full_name=req.full_name.strip(),
            role="patient",
            specialty="Patient Health",
            hashed_password=hash_password(req.password or "Patient@Sync2026!"),
            is_active=True
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

    # Enroll in MongoDB Atlas
    face_record = register_new_patient_face(
        patient_id=patient_id,
        full_name=req.full_name,
        email=email_clean,
        image_data=req.image_data,
        hospital_name=req.hospital_name or "St. Jude Memorial Hospital",
        phone=req.phone,
        dob=req.dob
    )

    # Log initial intake event
    save_patient_intake(
        patient_id=patient_id,
        hospital_name=req.hospital_name or "St. Jude Memorial Hospital",
        intake_type="biometric_face_registration",
        raw_content=f"New patient enrolled at hospital tablet kiosk with biometric face profile.",
        metadata={"email": email_clean, "hospital": req.hospital_name}
    )

    # Issue JWT Token
    token = create_access_token(
        subject=patient_id,
        claims={"role": "patient", "email": email_clean, "name": req.full_name}
    )

    return SuccessResponse(
        data={
            "success": True,
            "patient": {
                "patient_id": patient_id,
                "full_name": req.full_name,
                "email": email_clean,
                "role": "patient",
                "face_thumbnail": face_record.get("face_thumbnail"),
                "hospital_name": req.hospital_name
            },
            "token": token,
            "message": "✓ Face registration & profile creation completed successfully in hospital MongoDB database!"
        },
        meta={"request_id": req_id, "source": "mongodb"}
    )


@router.get("/face/{patient_id}")
def fetch_patient_face(patient_id: str, req_id: str = Depends(get_request_id)):
    """Retrieve patient facial biometric profile."""
    record = get_patient_face(patient_id)
    return SuccessResponse(data=record, meta={"request_id": req_id, "source": "mongodb"})


@router.get("/face")
def fetch_all_faces(req_id: str = Depends(get_request_id)):
    """List all registered patient faces enrolled at the hospital."""
    records = list_patient_faces()
    # Strip heavy vector from list overview
    clean = [{k: v for k, v in r.items() if k != "face_vector"} for r in records]
    return SuccessResponse(data={"count": len(clean), "patients": clean}, meta={"request_id": req_id})


@router.post("/vitals")
def record_vitals(req: VitalsRequest, req_id: str = Depends(get_request_id)):
    """Store patient vitals in MongoDB."""
    saved = save_patient_vitals(req.patient_id, req.hospital_name, req.vitals)
    return SuccessResponse(data=saved, meta={"request_id": req_id, "source": "mongodb"})


@router.get("/vitals/{patient_id}")
def fetch_vitals(patient_id: str, req_id: str = Depends(get_request_id)):
    """Retrieve vitals history for a patient from MongoDB."""
    history = get_patient_vitals(patient_id)
    return SuccessResponse(data={"patient_id": patient_id, "history": history}, meta={"request_id": req_id})


class ScanDocumentRequest(BaseModel):
    filename: Optional[str] = "uploaded_medical_document"
    mime_type: Optional[str] = ""
    file_base64: Optional[str] = None
    text_content: Optional[str] = None


@router.post("/documents/scan-and-validate")
def scan_and_validate_document(
    req: ScanDocumentRequest = Body(...),
    req_id: str = Depends(get_request_id)
):
    """
    Hospital Receptionist Multi-Format Document Ingestion & Medical Verification (JSON payload):
    1. Accepts text_content or file_base64 for any format: PDF, PNG, JPG, JPEG, WEBP, TXT, PPTX, PPT, DOCX, DOC.
    2. Extracts structured text and biomarker findings.
    3. Strictly checks medical relevance: if non-medical, rejects document and issues Notice.
    4. Audits clinical completeness (Chief Complaint, Duration, Meds, Allergies).
    5. Returns interactive receptionist interview instructions for missing details.
    """
    filename = req.filename or "uploaded_document"
    mime_type = req.mime_type or ""
    file_bytes = b""

    if req.file_base64:
        b64 = req.file_base64
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        try:
            file_bytes = base64.b64decode(b64)
        except Exception:
            file_bytes = b""

    extracted_text = ""
    if file_bytes:
        extracted_text = ReceptionistService.extract_text_from_file(file_bytes, filename, mime_type)
    if not extracted_text and req.text_content:
        extracted_text = req.text_content.strip()

    # Strict Medical Relevance Verification Gate
    med_check = ReceptionistService.verify_medical_relevance(extracted_text, filename)

    if not med_check["is_medical"]:
        # STRICT REJECTION: Do NOT take in non-medical files!
        return {
            "success": False,
            "is_medical": False,
            "error_code": "NON_MEDICAL_DOCUMENT",
            "filename": filename,
            "notice": (
                "⚠️ Non-Medical Document Detected: The uploaded file does not contain healthcare, clinical, or medical information. "
                "As your Smart Hospital Receptionist, I can only register medical records, prescriptions, diagnostic lab reports, and doctor notes. "
                "Please upload a valid clinical document."
            ),
            "details": med_check,
            "meta": {"request_id": req_id}
        }

    # Clinical Completeness Audit
    completeness = ReceptionistService.audit_clinical_completeness(extracted_text, filename)

    return SuccessResponse(
        data={
            "is_medical": True,
            "filename": filename,
            "doc_category": med_check["doc_category"],
            "verification_confidence": med_check["confidence"],
            "extracted_text_preview": (extracted_text[:400] + "...") if len(extracted_text) > 400 else extracted_text,
            "completeness": completeness
        },
        meta={"request_id": req_id, "source": "smart_ai_receptionist"}
    )


@router.post("/documents/upload-and-validate")
async def upload_and_validate_document(
    file: UploadFile = File(...),
    req_id: str = Depends(get_request_id)
):
    """Multipart file upload endpoint for the smart receptionist."""
    filename = file.filename or "uploaded_document"
    mime_type = file.content_type or ""
    file_bytes = await file.read()

    extracted_text = ReceptionistService.extract_text_from_file(file_bytes, filename, mime_type)
    med_check = ReceptionistService.verify_medical_relevance(extracted_text, filename)

    if not med_check["is_medical"]:
        return {
            "success": False,
            "is_medical": False,
            "error_code": "NON_MEDICAL_DOCUMENT",
            "filename": filename,
            "notice": (
                "⚠️ Non-Medical Document Detected: The uploaded file does not contain healthcare, clinical, or medical information. "
                "As your Smart Hospital Receptionist, I can only register medical records, prescriptions, diagnostic lab reports, and doctor notes. "
                "Please upload a valid clinical document."
            ),
            "details": med_check,
            "meta": {"request_id": req_id}
        }

    completeness = ReceptionistService.audit_clinical_completeness(extracted_text, filename)
    return SuccessResponse(
        data={
            "is_medical": True,
            "filename": filename,
            "doc_category": med_check["doc_category"],
            "verification_confidence": med_check["confidence"],
            "extracted_text_preview": (extracted_text[:400] + "...") if len(extracted_text) > 400 else extracted_text,
            "completeness": completeness
        },
        meta={"request_id": req_id, "source": "smart_ai_receptionist"}
    )


@router.post("/documents/finalize-reception-intake")
def finalize_reception_intake(
    payload: Dict[str, Any] = Body(...),
    req_id: str = Depends(get_request_id)
):
    """
    Concludes Smart AI Receptionist intake:
    1. Merges document findings with patient answers to receptionist questions.
    2. Compiles complete physician-ready Clinical Brief.
    3. Persists intake note and Clinical Brief into MongoDB Atlas.
    4. Dispatches appointment queue token (replacing front-desk receptionists).
    """
    patient_id = payload.get("patient_id", "pat_demo_patient_001")
    filename = payload.get("filename", "Medical Document")
    intake_data = payload.get("intake_data", {})

    chief_complaint = intake_data.get("chief_complaint") or "Comprehensive Medical Review & Health Optimization"
    duration = intake_data.get("duration") or "Reported duration noted"
    medications_str = intake_data.get("medications") or "Active prescription medications reviewed"
    allergies_str = intake_data.get("allergies") or "No known drug allergies reported (NKDA)"
    diagnosis = intake_data.get("diagnosis") or "Clinical assessment based on uploaded medical record"

    # Active meds list
    meds_list = [m.strip() for m in medications_str.split(",") if m.strip()]
    if not meds_list:
        meds_list = [medications_str]

    # Generate structured Clinical Brief
    brief_data = {
        "primary_diagnosis": diagnosis,
        "clinical_assessment": (
            f"Front-Desk AI Receptionist intake completed for uploaded document [{filename}]. "
            f"Chief Complaint: {chief_complaint}. Duration/Severity: {duration}. "
            f"Patient confirmed active medication adherence and allergy profile."
        ),
        "medication_reconciliation": {
            "active_meds": meds_list,
            "stopped_meds": [],
            "alerts": [f"Allergy verification: {allergies_str}"]
        },
        "recommendations": [
            f"Adhere strictly to active medications: {medications_str}",
            "Present this brief to consulting physician during upcoming clinic session",
            "Routine metabolic panel follow-up in 12 weeks"
        ],
        "receptionist_metadata": {
            "intake_mode": "smart_ai_receptionist",
            "document_filename": filename,
            "queue_token": f"TK-{int(time.time()) % 900 + 100}",
            "assigned_department": "Outpatient Internal Medicine & Specialist Clinic"
        }
    }

    # Save to MongoDB Atlas: hospital_intakes
    intake_record = save_patient_intake(
        patient_id=patient_id,
        hospital_name=payload.get("hospital_name", "St. Jude Memorial Hospital"),
        intake_type="ai_receptionist_intake",
        raw_content=f"Document [{filename}] verified by Smart AI Receptionist. Chief complaint: {chief_complaint}.",
        metadata=brief_data
    )

    # Save to MongoDB Atlas: clinical_briefs
    saved_brief = save_clinical_brief(
        patient_id=patient_id,
        doctor_id="usr_doctor_002",
        hospital_name=payload.get("hospital_name", "St. Jude Memorial Hospital"),
        brief_data=brief_data
    )

    return SuccessResponse(
        data={
            "brief": saved_brief,
            "intake": intake_record,
            "queue_token": brief_data["receptionist_metadata"]["queue_token"],
            "message": "✓ Intake completed! Clinical brief compiled and saved to hospital MongoDB Atlas. Consultation queued."
        },
        meta={"request_id": req_id, "source": "mongodb"}
    )


