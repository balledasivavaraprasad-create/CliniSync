"""
ClinSync MongoDB Integration Layer
Manages cloud MongoDB persistence for:
1. Patient hospital intakes (Audio voice, Camera OCR scan, PDF upload)
2. Generated Clinical Briefs
3. Patient Clinical Timelines & Medication Reconciliation
4. Comprehensive Doctor Profiles & Hospital Specialization
"""

import os
from datetime import datetime
from typing import Optional, Dict, Any, List
import structlog
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

logger = structlog.get_logger(__name__)

# Default Doctor Profiles seeded for MongoDB
DEFAULT_DOCTOR_PROFILES = {
    "usr_doctor_001": {
        "doctor_id": "usr_doctor_001",
        "full_name": "Dr. Willie Carter, MD",
        "email": "doctor@clinsync.health",
        "specialty": "General Medicine",
        "sub_specialty": "Preventive Medicine & Chronic Disease Management",
        "medical_license": "NMC-2024-88491",
        "hospital_affiliation": "St. Jude Memorial Hospital",
        "department": "Department of Internal & General Medicine",
        "qualifications": "MBBS, MD (General Medicine), Fellow of the American College of Physicians (FACP)",
        "experience_years": 16,
        "consultation_hours": "Mon - Fri: 09:00 AM - 04:30 PM",
        "office_room": "Suite 402, Block B, Clinical Wing",
        "phone": "+1 (555) 234-8901",
        "cert_verified": True,
        "cert_name": "National Medical Council Verified License 2026",
        "consultation_stats": {
            "active_patients": 48,
            "briefs_generated": 142,
            "safety_interventions": 19,
            "accuracy_score": "99.4%"
        },
        "bio": "Senior Consultant in General Medicine with over 16 years of expertise in longitudinal chronic disease management, diabetes protocols, and AI-assisted clinical medication safety."
    },
    "usr_doctor_002": {
        "doctor_id": "usr_doctor_002",
        "full_name": "Dr. Sarah Jenkins, MD, FACC",
        "email": "sarah.jenkins@clinsync.health",
        "specialty": "Cardiology",
        "sub_specialty": "Interventional Cardiology & Electrophysiology",
        "medical_license": "GMC-749210",
        "hospital_affiliation": "Metropolitan Heart & Vascular Institute",
        "department": "Cardiovascular Sciences & Intensive Care",
        "qualifications": "MBBS, MD, DM (Cardiology), FACC",
        "experience_years": 14,
        "consultation_hours": "Tue - Sat: 10:00 AM - 05:00 PM",
        "office_room": "Heart Pavilion 3A, Room 12",
        "phone": "+1 (555) 345-9872",
        "cert_verified": True,
        "cert_name": "Royal Medical Society Cardiology Board Certification",
        "consultation_stats": {
            "active_patients": 62,
            "briefs_generated": 210,
            "safety_interventions": 34,
            "accuracy_score": "99.8%"
        },
        "bio": "Cardiologist specializing in post-PCI stent surveillance, coronary artery management, and antiplatelet reconciliation."
    },
    "usr_doctor_003": {
        "doctor_id": "usr_doctor_003",
        "full_name": "Dr. Alex Mercer, MD",
        "email": "demo@clinsync.health",
        "specialty": "Internal Medicine",
        "sub_specialty": "Nephrology & Metabolic Syndromes",
        "medical_license": "NMC-2023-55102",
        "hospital_affiliation": "University Medical Center",
        "department": "Nephrology & Renal Medicine",
        "qualifications": "MBBS, MD (Internal Medicine), DNB (Nephrology)",
        "experience_years": 11,
        "consultation_hours": "Mon - Thu: 08:30 AM - 03:30 PM",
        "office_room": "Renal Diagnostic Center, 2nd Floor",
        "phone": "+1 (555) 456-1123",
        "cert_verified": True,
        "cert_name": "Internal Medicine Board Certificate",
        "consultation_stats": {
            "active_patients": 37,
            "briefs_generated": 98,
            "safety_interventions": 12,
            "accuracy_score": "99.1%"
        },
        "bio": "Attending Internist focusing on chronic kidney disease staging, anemia management, and multi-system medication reviews."
    }
}

DEFAULT_PATIENT_BRIEFS = [
    {
        "brief_id": "BRF-2026-0112",
        "patient_id": "usr_patient_001",
        "doctor_name": "Dr. Sarah Jenkins, MD",
        "doctor_id": "usr_doctor_002",
        "hospital_name": "St. Jude Memorial Hospital",
        "visit_date": "12 Jan 2026",
        "primary_diagnosis": "Type 2 Diabetes Mellitus with improved glycemic control",
        "clinical_assessment": "Patient demonstrates consistent glycemic improvement. HbA1c declined from 8.4% to 7.8%. Renal function normal (eGFR > 90 mL/min, creatinine 0.88 mg/dL). Blood pressure well controlled at 122/80 mmHg without orthostasis.",
        "medication_reconciliation": {
            "active_meds": ["Glimepiride 1 mg QAM", "Metformin 500 mg BID with meals"],
            "stopped_meds": [],
            "alerts": ["No drug-drug interactions detected"]
        },
        "recommendations": [
            "Continue lifestyle modifications and low-glycemic Mediterranean diet",
            "Maintain Glimepiride 1mg and Metformin 500mg BID",
            "Repeat HbA1c and microalbumin in 3 months",
            "Annual podiatric foot exam scheduled"
        ],
        "created_at": "2026-01-12T10:30:00Z"
    },
    {
        "brief_id": "BRF-2025-1114",
        "patient_id": "usr_patient_001",
        "doctor_name": "Dr. Alex Mercer, MD",
        "doctor_id": "usr_doctor_003",
        "hospital_name": "St. Jude Memorial Hospital",
        "visit_date": "14 Nov 2025",
        "primary_diagnosis": "Mild Lower Extremity Dysesthesia & Essential Hypertension Surveillance",
        "clinical_assessment": "Evaluated for reported tingling sensation in bilateral feet. Monofilament 10g sensory test normal. Vibration perception intact. Peripheral pulses 2+ bilaterally. Diabetic neuropathy ruled out. BP 130/84 mmHg.",
        "medication_reconciliation": {
            "active_meds": ["Metformin 500 mg BID"],
            "stopped_meds": [],
            "alerts": []
        },
        "recommendations": [
            "Initiated Glimepiride 1 mg morning dose to lower postprandial glucose surges",
            "Hydration goal 2.5L daily",
            "Follow-up with Endocrinology in 8 weeks"
        ],
        "created_at": "2025-11-14T14:15:00Z"
    }
]

DEFAULT_PATIENT_CLAIMS = [
    {
        "claim_id": "CLM-2026-8891",
        "patient_id": "usr_patient_001",
        "service_date": "2026-01-12",
        "provider": "BlueCross BlueShield Comprehensive PPO",
        "hospital_name": "St. Jude Memorial Hospital",
        "category": "Endocrinology Consultation & Metabolic Diagnostic Panel",
        "diagnosis_code": "ICD-10 E11.9 (Type 2 Diabetes Mellitus)",
        "total_billed": 840.00,
        "amount_covered": 790.00,
        "copay_patient": 50.00,
        "status": "Approved & Settled",
        "status_color": "green",
        "adjudication_notes": "Claim processed in-network. All diagnostic laboratory charges covered at 95% Tier-1 benefits."
    },
    {
        "claim_id": "CLM-2025-4120",
        "patient_id": "usr_patient_001",
        "service_date": "2025-11-14",
        "provider": "BlueCross BlueShield Comprehensive PPO",
        "hospital_name": "St. Jude Memorial Hospital",
        "category": "Renal Panel, Serum Creatinine & Glycated Hemoglobin (HbA1c)",
        "diagnosis_code": "ICD-10 Z13.1 (Diabetes Screening & Routine Assessment)",
        "total_billed": 340.00,
        "amount_covered": 340.00,
        "copay_patient": 0.00,
        "status": "Approved & Settled",
        "status_color": "green",
        "adjudication_notes": "Preventive screening covered at 100% under ACA wellness provisions."
    },
    {
        "claim_id": "CLM-2025-1044",
        "patient_id": "usr_patient_001",
        "service_date": "2025-08-22",
        "provider": "BlueCross BlueShield Comprehensive PPO",
        "hospital_name": "St. Jude Memorial Hospital",
        "category": "Dilated Retinal Eye Examination & Fundus Photography",
        "diagnosis_code": "ICD-10 E11.319 (Diabetic Retinopathy Surveillance)",
        "total_billed": 460.00,
        "amount_covered": 420.00,
        "copay_patient": 40.00,
        "status": "Approved & Settled",
        "status_color": "green",
        "adjudication_notes": "Specialist referral approved. Copay satisfied at clinic check-in."
    }
]

class MongoDBManager:
    _instance: Optional["MongoDBManager"] = None
    _client: Optional[MongoClient] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_uri(self) -> str:
        from app.config import settings
        uri = os.getenv("MONGODB_URI") or getattr(settings, "MONGODB_URI", "") or ""
        return uri.strip()

    def get_db_name(self) -> str:
        from app.config import settings
        name = os.getenv("MONGODB_DB_NAME") or getattr(settings, "MONGODB_DB_NAME", "clinisync_db") or "clinisync_db"
        return name.strip()

    def get_client(self) -> Optional[MongoClient]:
        uri = self.get_uri()
        if not uri or "<db_username>" in uri:
            return None

        if self._client is None:
            try:
                self._client = MongoClient(uri, serverSelectionTimeoutMS=4000)
                # Verify ping
                self._client.admin.command("ping")
                logger.info("mongodb_connected_successfully", db_name=self.get_db_name())
            except Exception as e:
                logger.warning("mongodb_connection_failed", error=str(e))
                self._client = None
        return self._client

    def get_db(self):
        client = self.get_client()
        if client:
            return client[self.get_db_name()]
        return None

    def is_connected(self) -> bool:
        client = self.get_client()
        if not client:
            return False
        try:
            client.admin.command("ping")
            return True
        except Exception:
            return False


mongo_mgr = MongoDBManager()


# ── In-Memory Fallback Cache (Ensures complete functionality before Atlas credentials) ─
_MONGO_CACHE = {
    "intakes": [],
    "briefs": {},
    "timelines": {},
    "medications": {},
    "doctors": dict(DEFAULT_DOCTOR_PROFILES),
    "patient_faces": {},
    "patient_vitals": {},
    "patient_profiles": {}
}


def save_patient_intake(
    patient_id: str,
    hospital_name: str,
    intake_type: str,
    raw_content: Any,
    extracted_data: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Store patient hospital intake from audio, PDF upload, or camera scan."""
    record = {
        "intake_id": f"intake_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{os.urandom(3).hex()}",
        "patient_id": patient_id,
        "hospital_name": hospital_name or "St. Jude Memorial Hospital",
        "intake_type": intake_type,  # 'audio_speech', 'camera_ocr', 'pdf_upload'
        "raw_content": raw_content,
        "extracted_data": extracted_data or {},
        "metadata": metadata or {},
        "created_at": datetime.utcnow().isoformat()
    }

    db = mongo_mgr.get_db()
    if db is not None:
        try:
            db.hospital_intakes.insert_one(dict(record))
            logger.info("mongo_intake_saved", intake_id=record["intake_id"], intake_type=intake_type)
        except Exception as e:
            logger.warning("mongo_intake_save_failed", error=str(e))

    # Always update cache
    _MONGO_CACHE["intakes"].append(record)
    return record


def get_patient_intakes(patient_id: str) -> List[Dict[str, Any]]:
    """Retrieve all hospital intakes for a patient."""
    db = mongo_mgr.get_db()
    if db is not None:
        try:
            records = list(db.hospital_intakes.find({"patient_id": patient_id}, {"_id": 0}))
            if records:
                return records
        except Exception as e:
            logger.warning("mongo_intake_read_failed", error=str(e))

    return [i for i in _MONGO_CACHE["intakes"] if i["patient_id"] == patient_id]


def save_clinical_brief(
    patient_id: str,
    doctor_id: str,
    hospital_name: str,
    brief_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Store generated clinical brief in MongoDB."""
    record = {
        "brief_id": f"brief_{patient_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "hospital_name": hospital_name or "St. Jude Memorial Hospital",
        "primary_diagnosis": brief_data.get("primary_diagnosis", ""),
        "clinical_assessment": brief_data.get("clinical_assessment", ""),
        "medication_reconciliation": brief_data.get("medication_reconciliation", {}),
        "risk_factors": brief_data.get("risk_factors", []),
        "recommendations": brief_data.get("recommendations", []),
        "full_brief_text": brief_data.get("brief_text", ""),
        "created_at": datetime.utcnow().isoformat()
    }

    db = mongo_mgr.get_db()
    if db is not None:
        try:
            db.clinical_briefs.update_one(
                {"patient_id": patient_id},
                {"$set": dict(record)},
                upsert=True
            )
            logger.info("mongo_brief_saved", patient_id=patient_id)
        except Exception as e:
            logger.warning("mongo_brief_save_failed", error=str(e))

    _MONGO_CACHE["briefs"][patient_id] = record
    return record


def get_clinical_brief(patient_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve clinical brief for a patient."""
    db = mongo_mgr.get_db()
    if db is not None:
        try:
            res = db.clinical_briefs.find_one({"patient_id": patient_id}, {"_id": 0})
            if res:
                return res
        except Exception as e:
            logger.warning("mongo_brief_read_failed", error=str(e))

    return _MONGO_CACHE["briefs"].get(patient_id)


def get_all_clinical_briefs(patient_id: str) -> List[Dict[str, Any]]:
    """Retrieve all clinical briefs for a patient, ordered by newest first."""
    briefs = []
    db = mongo_mgr.get_db()
    if db is not None:
        try:
            records = list(db.clinical_briefs.find({"patient_id": patient_id}, {"_id": 0}).sort("created_at", -1))
            if records:
                briefs.extend(records)
        except Exception as e:
            logger.warning("mongo_briefs_list_failed", error=str(e))

    # Also check cache
    cached = _MONGO_CACHE["briefs"].get(patient_id)
    if cached and not any(b.get("brief_id") == cached.get("brief_id") for b in briefs):
        briefs.insert(0, cached)

    # If no briefs exist yet, include default historical briefs for standard review
    if not briefs:
        for b in DEFAULT_PATIENT_BRIEFS:
            b_copy = dict(b)
            b_copy["patient_id"] = patient_id
            briefs.append(b_copy)
            if db is not None:
                try:
                    db.clinical_briefs.update_one({"brief_id": b["brief_id"]}, {"$set": b_copy}, upsert=True)
                except Exception:
                    pass

    return briefs


def get_patient_claims(patient_id: str) -> List[Dict[str, Any]]:
    """Retrieve health insurance claims and reimbursement records for a patient."""
    claims = []
    db = mongo_mgr.get_db()
    if db is not None:
        try:
            records = list(db.insurance_claims.find({"patient_id": patient_id}, {"_id": 0}).sort("service_date", -1))
            if records:
                claims.extend(records)
        except Exception as e:
            logger.warning("mongo_claims_list_failed", error=str(e))

    if not claims:
        # Seed default claims for patient
        for c in DEFAULT_PATIENT_CLAIMS:
            c_copy = dict(c)
            c_copy["patient_id"] = patient_id
            claims.append(c_copy)
            if db is not None:
                try:
                    db.insurance_claims.update_one({"claim_id": c["claim_id"]}, {"$set": c_copy}, upsert=True)
                except Exception:
                    pass
        _MONGO_CACHE["claims"] = claims

    return claims


def save_patient_claim(patient_id: str, claim_data: Dict[str, Any]) -> Dict[str, Any]:
    """Store or update an insurance claim in MongoDB."""
    record = {
        "claim_id": claim_data.get("claim_id") or f"CLM-{datetime.utcnow().strftime('%Y')}-{os.urandom(2).hex().upper()}",
        "patient_id": patient_id,
        "service_date": claim_data.get("service_date", datetime.utcnow().strftime('%Y-%m-%d')),
        "provider": claim_data.get("provider", "BlueCross BlueShield Comprehensive PPO"),
        "hospital_name": claim_data.get("hospital_name", "St. Jude Memorial Hospital"),
        "category": claim_data.get("category", "General Medical Consultation"),
        "diagnosis_code": claim_data.get("diagnosis_code", "ICD-10 Z00.00"),
        "total_billed": float(claim_data.get("total_billed", 500.0)),
        "amount_covered": float(claim_data.get("amount_covered", 450.0)),
        "copay_patient": float(claim_data.get("copay_patient", 50.0)),
        "status": claim_data.get("status", "Approved & Settled"),
        "status_color": claim_data.get("status_color", "green"),
        "adjudication_notes": claim_data.get("adjudication_notes", "Processed successfully."),
        "created_at": datetime.utcnow().isoformat()
    }
    db = mongo_mgr.get_db()
    if db is not None:
        try:
            db.insurance_claims.update_one({"claim_id": record["claim_id"]}, {"$set": record}, upsert=True)
        except Exception as e:
            logger.warning("mongo_claim_save_failed", error=str(e))
    return record


def save_clinical_timeline(
    patient_id: str,
    hospital_name: str,
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Store longitudinal clinical timeline in MongoDB."""
    record = {
        "patient_id": patient_id,
        "hospital_name": hospital_name or "St. Jude Memorial Hospital",
        "events": events,
        "last_updated": datetime.utcnow().isoformat()
    }

    db = mongo_mgr.get_db()
    if db is not None:
        try:
            db.clinical_timelines.update_one(
                {"patient_id": patient_id},
                {"$set": dict(record)},
                upsert=True
            )
        except Exception as e:
            logger.warning("mongo_timeline_save_failed", error=str(e))

    _MONGO_CACHE["timelines"][patient_id] = record
    return record


def get_clinical_timeline(patient_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve clinical timeline for a patient."""
    db = mongo_mgr.get_db()
    if db is not None:
        try:
            res = db.clinical_timelines.find_one({"patient_id": patient_id}, {"_id": 0})
            if res:
                return res
        except Exception as e:
            logger.warning("mongo_timeline_read_failed", error=str(e))

    return _MONGO_CACHE["timelines"].get(patient_id)


def save_medication_reconciliation(
    patient_id: str,
    hospital_name: str,
    medications: List[Dict[str, Any]],
    conflicts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Store medication reconciliation in MongoDB."""
    record = {
        "patient_id": patient_id,
        "hospital_name": hospital_name or "St. Jude Memorial Hospital",
        "active_medications": medications,
        "conflicts_detected": conflicts,
        "conflict_count": len(conflicts),
        "last_reconciled": datetime.utcnow().isoformat()
    }

    db = mongo_mgr.get_db()
    if db is not None:
        try:
            db.medication_reconciliations.update_one(
                {"patient_id": patient_id},
                {"$set": dict(record)},
                upsert=True
            )
        except Exception as e:
            logger.warning("mongo_reconciliation_save_failed", error=str(e))

    _MONGO_CACHE["medications"][patient_id] = record
    return record


def get_medication_reconciliation(patient_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve medication reconciliation for a patient."""
    db = mongo_mgr.get_db()
    if db is not None:
        try:
            res = db.medication_reconciliations.find_one({"patient_id": patient_id}, {"_id": 0})
            if res:
                return res
        except Exception as e:
            logger.warning("mongo_reconciliation_read_failed", error=str(e))

    return _MONGO_CACHE["medications"].get(patient_id)


def get_doctor_profile(doctor_id: str) -> Dict[str, Any]:
    """Retrieve comprehensive doctor profile from MongoDB."""
    db = mongo_mgr.get_db()
    if db is not None:
        try:
            res = db.doctor_profiles.find_one({"doctor_id": doctor_id}, {"_id": 0})
            if res:
                return res
        except Exception as e:
            logger.warning("mongo_doctor_read_failed", error=str(e))

    # Fallback to cache or generic profile
    if doctor_id in _MONGO_CACHE["doctors"]:
        return _MONGO_CACHE["doctors"][doctor_id]

    # Generate a comprehensive profile based on known defaults
    default_p = DEFAULT_DOCTOR_PROFILES.get("usr_doctor_001", {})
    gen_p = dict(default_p)
    gen_p["doctor_id"] = doctor_id
    return gen_p


def save_doctor_profile(doctor_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """Save or update comprehensive doctor profile in MongoDB."""
    profile_data["doctor_id"] = doctor_id
    profile_data["updated_at"] = datetime.utcnow().isoformat()

    db = mongo_mgr.get_db()
    if db is not None:
        try:
            db.doctor_profiles.update_one(
                {"doctor_id": doctor_id},
                {"$set": dict(profile_data)},
                upsert=True
            )
            logger.info("mongo_doctor_profile_saved", doctor_id=doctor_id)
        except Exception as e:
            logger.warning("mongo_doctor_profile_save_failed", error=str(e))

    _MONGO_CACHE["doctors"][doctor_id] = profile_data
    return profile_data


# ── Patient Face Biometrics & Kiosk Profiles ──────────────────────────────────
def save_patient_face(record: Dict[str, Any]) -> Dict[str, Any]:
    """Store patient facial biometric enrollment in MongoDB."""
    patient_id = record.get("patient_id")
    if not patient_id:
        return record

    db = mongo_mgr.get_db()
    if db is not None:
        try:
            db.patient_faces.update_one(
                {"patient_id": patient_id},
                {"$set": dict(record)},
                upsert=True
            )
            logger.info("mongo_patient_face_saved", patient_id=patient_id)
        except Exception as e:
            logger.warning("mongo_patient_face_save_failed", error=str(e))

    if "patient_faces" not in _MONGO_CACHE:
        _MONGO_CACHE["patient_faces"] = {}
    _MONGO_CACHE["patient_faces"][patient_id] = record
    return record


def get_patient_face(patient_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve patient facial biometric profile."""
    db = mongo_mgr.get_db()
    if db is not None:
        try:
            res = db.patient_faces.find_one({"patient_id": patient_id}, {"_id": 0})
            if res:
                return res
        except Exception as e:
            logger.warning("mongo_patient_face_read_failed", error=str(e))

    return _MONGO_CACHE.get("patient_faces", {}).get(patient_id)


def list_patient_faces() -> List[Dict[str, Any]]:
    """List all registered patient faces for biometric recognition."""
    db = mongo_mgr.get_db()
    if db is not None:
        try:
            cursor = db.patient_faces.find({}, {"_id": 0})
            return list(cursor)
        except Exception as e:
            logger.warning("mongo_list_patient_faces_failed", error=str(e))

    return list(_MONGO_CACHE.get("patient_faces", {}).values())


def save_patient_vitals(patient_id: str, hospital_name: str, vitals_data: Dict[str, Any]) -> Dict[str, Any]:
    """Store patient vitals captured from tablet or kiosk."""
    record = {
        "patient_id": patient_id,
        "hospital_name": hospital_name or "St. Jude Memorial Hospital",
        "vitals": vitals_data,
        "recorded_at": datetime.utcnow().isoformat()
    }
    db = mongo_mgr.get_db()
    if db is not None:
        try:
            db.patient_vitals.insert_one(dict(record))
        except Exception as e:
            logger.warning("mongo_vitals_save_failed", error=str(e))

    if "patient_vitals" not in _MONGO_CACHE:
        _MONGO_CACHE["patient_vitals"] = {}
    if patient_id not in _MONGO_CACHE["patient_vitals"]:
        _MONGO_CACHE["patient_vitals"][patient_id] = []
    _MONGO_CACHE["patient_vitals"][patient_id].append(record)
    return record


def get_patient_vitals(patient_id: str) -> List[Dict[str, Any]]:
    """Retrieve historical vitals for a patient."""
    db = mongo_mgr.get_db()
    if db is not None:
        try:
            cursor = db.patient_vitals.find({"patient_id": patient_id}, {"_id": 0}).sort("recorded_at", -1)
            return list(cursor)
        except Exception as e:
            logger.warning("mongo_vitals_read_failed", error=str(e))

    return _MONGO_CACHE.get("patient_vitals", {}).get(patient_id, [])

