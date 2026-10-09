"""
Seed script to initialize collections and records in MongoDB Atlas
Collections:
- doctor_profiles
- clinical_briefs
- clinical_timelines
- medication_reconciliations
- hospital_intakes
"""
import os
import pymongo
from datetime import datetime

uri = os.getenv("MONGODB_URI", "mongodb://sriharshabaswa_db_user:L7CDj3RXDYNbbVJV@ac-dwnpgsx-shard-00-00.z8hufbr.mongodb.net:27017,ac-dwnpgsx-shard-00-01.z8hufbr.mongodb.net:27017,ac-dwnpgsx-shard-00-02.z8hufbr.mongodb.net:27017/?ssl=true&replicaSet=atlas-ottijt-shard-0&authSource=admin&appName=Cluster-1")
client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=8000)
db = client["clinisync_db"]

print("Connected to MongoDB Atlas:", db.name)

# 1. Seed Doctor Profiles
doctor_profiles = [
    {
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
        "bio": "Senior Consultant in General Medicine with over 16 years of expertise in longitudinal chronic disease management, diabetes protocols, and AI-assisted clinical medication safety.",
        "updated_at": datetime.utcnow().isoformat()
    },
    {
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
        "bio": "Cardiologist specializing in post-PCI stent surveillance, coronary artery management, and antiplatelet reconciliation.",
        "updated_at": datetime.utcnow().isoformat()
    },
    {
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
        "bio": "Attending Internist focusing on chronic kidney disease staging, anemia management, and multi-system medication reviews.",
        "updated_at": datetime.utcnow().isoformat()
    }
]

for doc in doctor_profiles:
    db.doctor_profiles.update_one({"doctor_id": doc["doctor_id"]}, {"$set": doc}, upsert=True)
print("Seeded doctor_profiles:", len(doctor_profiles))

# 2. Seed Clinical Brief for Demo Patient
demo_brief = {
    "brief_id": "brief_pat_demo_patient_001_initial",
    "patient_id": "pat_demo_patient_001",
    "patient_name": "Demo Patient",
    "doctor_id": "usr_doctor_001",
    "hospital_name": "St. Jude Memorial Hospital",
    "primary_diagnosis": "Type 2 Diabetes Mellitus with Peripheral Monitoring",
    "clinical_assessment": "52-year-old male with long-standing Type 2 Diabetes Mellitus exhibiting steady glycemic improvement (HbA1c decreasing from 8.4% down to 7.8%). Critical safety finding: conflicting Metformin prescriptions noted across Sep 12 records requiring clinical reconciliation.",
    "risk_factors": [
        "Metformin dosage contradiction (500mg BD vs 1000mg BD)",
        "Sub-optimal glycemic target (HbA1c 7.8% vs target < 7.0%)",
        "Mild morning hypoglycemia risk"
    ],
    "recommendations": [
        "Confirm single Metformin dosage: standardize to 500 mg BD with food",
        "Repeat HbA1c in 90 days",
        "Continue daily home fasting plasma glucose logging"
    ],
    "created_at": datetime.utcnow().isoformat()
}
db.clinical_briefs.update_one({"patient_id": demo_brief["patient_id"]}, {"$set": demo_brief}, upsert=True)
print("Seeded clinical_briefs for:", demo_brief["patient_id"])

# 3. Seed Clinical Timeline
demo_timeline = {
    "patient_id": "pat_demo_patient_001",
    "hospital_name": "St. Jude Memorial Hospital",
    "events": [
        {
            "date": "28 Sep 2026",
            "category": "Consultation",
            "title": "Comprehensive Diabetes Review",
            "hospital": "St. Jude Memorial Hospital",
            "doctor": "Dr. Willie Carter, MD",
            "notes": "Reviewed HbA1c laboratory improvement. Flagged Metformin prescription discrepancy for reconciliation."
        },
        {
            "date": "12 Sep 2026",
            "category": "Prescription",
            "title": "Metformin Prescription Dispensed",
            "hospital": "City Care Clinic",
            "doctor": "Dr. E. Vance, MD",
            "notes": "Metformin 500 mg BD prescribed alongside Glimepiride 1 mg OD."
        },
        {
            "date": "15 Apr 2026",
            "category": "Laboratory",
            "title": "Quarterly Metabolic Panel",
            "hospital": "St. Jude Pathology Lab",
            "doctor": "Diagnostic Services",
            "notes": "HbA1c: 8.1%, Serum Creatinine: 0.9 mg/dL (Normal renal profile)."
        },
        {
            "date": "14 Jan 2026",
            "category": "Initial Intake",
            "title": "Hospital Onboarding & Baseline Diagnostic",
            "hospital": "St. Jude Memorial Hospital",
            "doctor": "Dr. Willie Carter, MD",
            "notes": "Baseline HbA1c 8.4%. Lifestyle, dietary counseling, and oral hypoglycemic regimen initiated."
        }
    ],
    "last_updated": datetime.utcnow().isoformat()
}
db.clinical_timelines.update_one({"patient_id": demo_timeline["patient_id"]}, {"$set": demo_timeline}, upsert=True)
print("Seeded clinical_timelines")

# 4. Seed Medication Reconciliation
demo_reconciliation = {
    "patient_id": "pat_demo_patient_001",
    "hospital_name": "St. Jude Memorial Hospital",
    "active_medications": [
        {"name": "Metformin", "dose": "500 mg", "frequency": "BD (Twice daily)", "route": "Oral", "status": "⚠️ Discrepancy Flagged"},
        {"name": "Glimepiride", "dose": "1 mg", "frequency": "OD (Once daily morning)", "route": "Oral", "status": "Active & Verified"},
        {"name": "Atorvastatin", "dose": "10 mg", "frequency": "OD (At bedtime)", "route": "Oral", "status": "Active & Verified"},
        {"name": "Aspirin", "dose": "75 mg", "frequency": "OD (Post-lunch)", "route": "Oral", "status": "Active & Verified"}
    ],
    "conflicts_detected": [
        {
            "drug": "Metformin",
            "conflict_type": "Dosage Contradiction",
            "record_1": "Discharge Summary Sep 12: Metformin 1000 mg BD",
            "record_2": "Follow-up Clinic Rx Sep 28: Metformin 500 mg BD",
            "clinical_guidance": "Verify renal function (eGFR) and standardize dose to avoid lactic acidosis risk."
        }
    ],
    "last_reconciled": datetime.utcnow().isoformat()
}
db.medication_reconciliations.update_one({"patient_id": demo_reconciliation["patient_id"]}, {"$set": demo_reconciliation}, upsert=True)
print("Seeded medication_reconciliations")

# 5. Seed Sample Hospital Intake
sample_intake = {
    "intake_id": "intake_baseline_voice_001",
    "patient_id": "pat_demo_patient_001",
    "hospital_name": "St. Jude Memorial Hospital",
    "intake_type": "audio_speech",
    "raw_content": "Doctor, for the past four days I have had mild fatigue and thirst. My morning fasting sugar was around 140 mg/dL. I have been taking Metformin twice daily with meals as recommended.",
    "extracted_data": {
        "symptoms": ["mild fatigue", "thirst"],
        "fasting_glucose": "140 mg/dL",
        "medication_mentioned": "Metformin BD with meals"
    },
    "metadata": {
        "channel": "Speech-to-Text Microphone",
        "duration_seconds": 24
    },
    "created_at": datetime.utcnow().isoformat()
}
db.hospital_intakes.update_one({"intake_id": sample_intake["intake_id"]}, {"$set": sample_intake}, upsert=True)
print("Seeded hospital_intakes")

# 6. Seed Baseline Patient Face Biometric Template
import numpy as np
# Create a normalized baseline face embedding vector (1152 floats)
np.random.seed(42)
demo_vector = np.random.randn(1152).astype(np.float32)
demo_vector /= np.linalg.norm(demo_vector)

sample_face = {
    "patient_id": "pat_demo_patient_001",
    "full_name": "Demo Patient",
    "email": "patient@clinsync.health",
    "phone": "+1 (555) 019-2834",
    "dob": "1974-05-14",
    "hospital_name": "St. Jude Memorial Hospital",
    "face_vector": demo_vector.tolist(),
    "face_thumbnail": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80'%3E%3Crect width='80' height='80' fill='%230d9488'/%3E%3Ccircle cx='40' cy='32' r='16' fill='white'/%3E%3Cpath d='M20 68c0-11 9-20 20-20s20 9 20 20' fill='white'/%3E%3C/svg%3E",
    "has_biometric": True,
    "status": "enrolled",
    "created_at": datetime.utcnow().isoformat(),
    "last_checkin": datetime.utcnow().isoformat()
}
db.patient_faces.update_one({"patient_id": sample_face["patient_id"]}, {"$set": sample_face}, upsert=True)
print("Seeded patient_faces for: pat_demo_patient_001")

print("\nALL COLLECTIONS IN clinisync_db NOW:")
for c in db.list_collection_names():
    print(f" - {c}: {db[c].count_documents({})} documents")

