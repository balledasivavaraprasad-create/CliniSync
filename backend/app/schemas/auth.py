from typing import Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class CheckEmailRequest(BaseModel):
    email: str


class SendOtpRequest(BaseModel):
    email: str
    role: Optional[str] = "patient"
    action: Optional[str] = "register"


class VerifyOtpRequest(BaseModel):
    email: str
    otp: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    role: Optional[str] = "doctor"
    specialty: Optional[str] = "General Medicine"


class AdminCreateUserRequest(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "doctor"
    specialty: str = "General Medicine"


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    specialty: str
    is_active: bool = True
    avatar_url: Optional[str] = None
    patient_id: Optional[str] = None


class LoginResponse(BaseModel):
    token: str
    user: UserResponse
