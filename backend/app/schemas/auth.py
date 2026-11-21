from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class UserRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)


class UserLoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=1)
    remember_me: bool = False


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., max_length=255)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)


class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., min_length=10)


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_verified: bool
    is_active: bool
    role: str
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    expires_in: int  # Seconds until expiration


class MessageResponse(BaseModel):
    status: str
    message: str
    email_sent: bool = False
    dev_token: Optional[str] = None


class AuthStatusResponse(BaseModel):
    google_oauth_enabled: bool
    email_delivery_enabled: bool
    demo_mode: bool
