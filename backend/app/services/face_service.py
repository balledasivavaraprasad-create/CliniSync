"""
ClinSync Patient Face Biometrics & Recognition Service
Powers hospital tablet kiosk check-in:
- Detects face in image stream using OpenCV Haar Cascade
- Extracts normalized facial biometric embeddings
- Matches against registered patient faces in MongoDB Atlas
- Enrolls new patient face biometrics into MongoDB Atlas
"""

import base64
import re
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
import numpy as np
import cv2
import structlog

from app.db.mongodb import mongo_mgr, _MONGO_CACHE

logger = structlog.get_logger(__name__)

# Load OpenCV frontal face Haar Cascade
CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
_face_cascade = cv2.CascadeClassifier(CASCADE_PATH)


def decode_image_base64(image_data: str) -> Optional[np.ndarray]:
    """Decode base64 string or data URL to OpenCV BGR image."""
    try:
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]
        raw_bytes = base64.b64decode(image_data)
        np_arr = np.frombuffer(raw_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        logger.warning("face_image_decode_failed", error=str(e))
        return None


def encode_image_base64(cv_img: np.ndarray, format_ext: str = ".jpg") -> str:
    """Encode OpenCV image to JPEG base64 data URL."""
    try:
        success, buf = cv2.imencode(format_ext, cv_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if success:
            b64_str = base64.b64encode(buf).decode("utf-8")
            return f"data:image/jpeg;base64,{b64_str}"
    except Exception as e:
        logger.warning("face_image_encode_failed", error=str(e))
    return ""


def detect_face_roi(cv_img: np.ndarray, strict_face: bool = False) -> Tuple[Optional[np.ndarray], Optional[Dict[str, int]], bool]:
    """
    Detect frontal face in image and return cropped grayscale ROI (128x128),
    bounding box coordinates, and whether a face was detected by the Haar cascade.
    """
    if cv_img is None or cv_img.size == 0:
        return None, None, False

    h, w = cv_img.shape[:2]
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    faces = _face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=4,
        minSize=(45, 45),
        flags=cv2.CASCADE_SCALE_IMAGE
    )

    if len(faces) > 0:
        # Largest detected face
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, fw, fh = faces[0]
        margin_x = int(fw * 0.1)
        margin_y = int(fh * 0.1)
        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(w, x + fw + margin_x)
        y2 = min(h, y + fh + margin_y)
        face_roi = gray[y1:y2, x1:x2]
        bbox = {"x": int(x), "y": int(y), "w": int(fw), "h": int(fh)}
        face_detected = True
    else:
        if strict_face:
            return None, None, False
        # Centered crop fallback
        size = min(h, w)
        y1 = (h - size) // 2
        x1 = (w - size) // 2
        face_roi = gray[y1:y1+size, x1:x1+size]
        bbox = {"x": int(x1), "y": int(y1), "w": int(size), "h": int(size), "inferred": True}
        face_detected = False

    if face_roi is None or face_roi.size == 0:
        return None, None, False

    resized_roi = cv2.resize(face_roi, (128, 128), interpolation=cv2.INTER_AREA)
    return resized_roi, bbox, face_detected


def extract_face_embedding(face_roi: np.ndarray) -> List[float]:
    """
    Extract a normalized biometric feature vector from the face ROI using
    zero-centered intensity patterns and Sobel edge gradients.
    """
    if face_roi is None or face_roi.size == 0:
        return []

    # 1. Downsampled intensity pattern (32x32 = 1024 features)
    small = cv2.resize(face_roi, (32, 32), interpolation=cv2.INTER_AREA)
    intensities = small.flatten().astype(np.float32)
    std_int = np.std(intensities)
    if std_int > 1e-5:
        intensities = (intensities - np.mean(intensities)) / std_int

    # 2. Horizontal and vertical Sobel gradients (16x16 = 256 features)
    sobelx = cv2.Sobel(face_roi, cv2.CV_32F, 1, 0, ksize=3)
    sobely = cv2.Sobel(face_roi, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(sobelx, sobely)
    mag_small = cv2.resize(mag, (16, 16), interpolation=cv2.INTER_AREA).flatten().astype(np.float32)
    std_mag = np.std(mag_small)
    if std_mag > 1e-5:
        mag_small = (mag_small - np.mean(mag_small)) / std_mag

    combined = np.concatenate([intensities, mag_small])
    norm = np.linalg.norm(combined)
    if norm > 0:
        combined /= norm

    return combined.tolist()


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two zero-centered feature vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def recognize_patient_face(
    image_data: str,
    hospital_name: str = "St. Jude Memorial Hospital",
    similarity_threshold: float = 0.68
) -> Dict[str, Any]:
    """
    Process probe image from hospital tablet, detect face,
    and find best matching registered patient in MongoDB Atlas.
    """
    img = decode_image_base64(image_data)
    if img is None:
        return {
            "matched": False,
            "error": "Invalid or unreadable image data.",
            "message": "Please ensure camera is active and well lit."
        }

    face_roi, bbox, face_detected = detect_face_roi(img)
    if face_roi is None or not face_detected:
        return {
            "matched": False,
            "face_detected": False,
            "requires_signup": False,
            "error": "No clear face detected in viewport.",
            "message": "Please position your face directly inside the camera guide frame."
        }

    probe_vector = extract_face_embedding(face_roi)
    if not probe_vector:
        return {
            "matched": False,
            "error": "Could not extract face biometrics.",
            "message": "Face image was not clear enough to extract features."
        }

    # Retrieve all enrolled patient face records from MongoDB Atlas
    enrolled_patients = []
    db = mongo_mgr.get_db()
    if db is not None:
        try:
            cursor = db.patient_faces.find({}, {"_id": 0})
            enrolled_patients = list(cursor)
        except Exception as e:
            logger.warning("mongo_fetch_patient_faces_failed", error=str(e))

    # Also check memory cache if MongoDB has none or is offline
    if not enrolled_patients:
        enrolled_patients = list(_MONGO_CACHE.get("patient_faces", {}).values())

    if not enrolled_patients:
        # No patients registered in database yet
        return {
            "matched": False,
            "best_similarity": 0.0,
            "threshold": similarity_threshold,
            "requires_signup": True,
            "message": "No registered patient faces found in hospital database. Please sign up to register your face.",
            "bbox": bbox
        }

    best_match = None
    best_sim = -1.0

    for patient in enrolled_patients:
        saved_vec = patient.get("face_vector")
        if not saved_vec:
            continue
        sim = cosine_similarity(probe_vector, saved_vec)
        if sim > best_sim:
            best_sim = sim
            best_match = patient

    is_match = best_sim >= similarity_threshold and best_match is not None

    if is_match:
        logger.info(
            "patient_face_recognized",
            patient_id=best_match.get("patient_id"),
            patient_name=best_match.get("full_name"),
            similarity=round(best_sim, 4)
        )
        return {
            "matched": True,
            "confidence": round(best_sim * 100, 1),
            "similarity": round(best_sim, 4),
            "threshold": similarity_threshold,
            "patient": {
                "patient_id": best_match.get("patient_id"),
                "full_name": best_match.get("full_name"),
                "email": best_match.get("email"),
                "role": "patient",
                "face_thumbnail": best_match.get("face_thumbnail"),
                "last_checkin": datetime.now(timezone.utc).isoformat(),
                "hospital_name": hospital_name
            },
            "bbox": bbox,
            "message": f"Welcome back, {best_match.get('full_name')}! Face verified with {round(best_sim * 100, 1)}% match."
        }
    else:
        return {
            "matched": False,
            "best_similarity": round(best_sim, 4) if best_sim > 0 else 0.0,
            "threshold": similarity_threshold,
            "requires_signup": True,
            "bbox": bbox,
            "message": "Face not recognized in hospital registry. Please register your face to create your patient account."
        }


def register_new_patient_face(
    patient_id: str,
    full_name: str,
    email: str,
    image_data: str,
    hospital_name: str = "St. Jude Memorial Hospital",
    phone: Optional[str] = None,
    dob: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Enroll a new patient face biometric record into MongoDB Atlas.
    """
    img = decode_image_base64(image_data)
    face_roi, bbox = (None, None)
    face_vector = []
    face_thumbnail = ""

    if img is not None:
        face_roi, bbox, _ = detect_face_roi(img)
        if face_roi is not None:
            face_vector = extract_face_embedding(face_roi)
            # Create a 96x96 clean thumbnail for quick avatar rendering
            thumb_roi = cv2.resize(face_roi, (96, 96), interpolation=cv2.INTER_AREA)
            face_thumbnail = encode_image_base64(thumb_roi)

    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "patient_id": patient_id,
        "full_name": full_name.strip(),
        "email": email.strip().lower(),
        "phone": phone or "",
        "dob": dob or "",
        "hospital_name": hospital_name,
        "face_vector": face_vector,
        "face_thumbnail": face_thumbnail or image_data[:200],  # Fallback preview
        "has_biometric": bool(face_vector),
        "bbox": bbox or {},
        "created_at": now_iso,
        "last_checkin": now_iso,
        "status": "enrolled",
        "metadata": extra_metadata or {}
    }

    # 1. Save to MongoDB Atlas
    db = mongo_mgr.get_db()
    if db is not None:
        try:
            db.patient_faces.update_one(
                {"patient_id": patient_id},
                {"$set": dict(record)},
                upsert=True
            )
            logger.info("patient_face_enrolled_in_mongodb", patient_id=patient_id, name=full_name)
        except Exception as e:
            logger.warning("mongo_patient_face_enroll_failed", error=str(e))

    # 2. Save in memory cache
    if "patient_faces" not in _MONGO_CACHE:
        _MONGO_CACHE["patient_faces"] = {}
    _MONGO_CACHE["patient_faces"][patient_id] = record

    return record
