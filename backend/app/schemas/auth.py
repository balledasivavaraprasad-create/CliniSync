from typing import Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "doctor"
    specialty: str = "Cardiology"


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    specialty: str
    is_active: bool = True
    avatar_url: Optional[str] = None


class LoginResponse(BaseModel):
    token: str
    user: UserResponse
