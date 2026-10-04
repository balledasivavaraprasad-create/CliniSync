from typing import List
from fastapi import APIRouter
from pydantic import BaseModel
from app.schemas.common import SuccessResponse

router = APIRouter(tags=["Specialties"])


class SpecialtyItem(BaseModel):
    id: str
    name: str
    description: str


SPECIALTIES = [
    SpecialtyItem(id="general_medicine", name="General Medicine", description="Comprehensive primary and internal care overview"),
    SpecialtyItem(id="diabetology", name="Diabetology & Endocrinology", description="Glycemic control, metabolic profiles, renal protection"),
    SpecialtyItem(id="cardiology", name="Cardiology", description="Cardiovascular risks, blood pressure, lipid panels, antiplatelets"),
    SpecialtyItem(id="orthopedics", name="Orthopedics", description="Musculoskeletal assessments, surgical history, mobility"),
    SpecialtyItem(id="neurology", name="Neurology", description="Neurological evaluations, cognitive and motor tracking"),
    SpecialtyItem(id="pediatrics", name="Pediatrics", description="Developmental, pediatric dosing and immunization tracking"),
    SpecialtyItem(id="other", name="Other Specialty", description="General clinical synthesis"),
]


@router.get("/specialties", response_model=SuccessResponse[List[SpecialtyItem]])
def list_specialties():
    return SuccessResponse(data=SPECIALTIES)
