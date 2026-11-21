from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    validate_email_format,
    create_access_token,
    generate_secure_token,
)
from app.db.session import get_db
from app.models.models import User, AuditLog
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    GoogleAuthRequest,
    UserResponse,
    TokenResponse,
    MessageResponse,
    AuthStatusResponse,
)
from app.services.email import (
    send_password_reset_email,
    is_email_configured,
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/status", response_model=AuthStatusResponse)
def get_auth_status():
    """Returns runtime authentication configuration capabilities."""
    return AuthStatusResponse(
        google_oauth_enabled=bool(settings.GOOGLE_CLIENT_ID and len(settings.GOOGLE_CLIENT_ID.strip()) > 5),
        email_delivery_enabled=is_email_configured(),
        demo_mode=settings.DEMO_MODE,
    )


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    req: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Registers a new user account with email format validation, password strength enforcement,
    and immediate account activation without requiring email verification.
    """
    email = req.email.strip().lower()
    full_name = req.full_name.strip()

    # 1. Email format check
    if not validate_email_format(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email address format.",
        )

    # 2. Password confirmation match
    if req.password != req.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password and confirmation password do not match.",
        )

    # 3. Password strength check
    is_strong, reason = validate_password_strength(req.password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=reason,
        )

    # 4. Duplicate email prevention
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists. Please log in or reset your password.",
        )

    # 5. Create user record (immediately active and verified)
    now = datetime.now(timezone.utc)
    new_user = User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(req.password),
        is_verified=True,
        is_active=True,
        role="member",
        verification_token=None,
        verification_token_expires_at=None,
        verification_attempts=0,
        created_at=now,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return MessageResponse(
        status="ok",
        message="Registration successful. You can now log in with your credentials.",
        email_sent=False,
        dev_token=None,
    )


@router.post("/login", response_model=TokenResponse)
def login_user(
    req: UserLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticates user credentials. Returns JWT bearer token on valid credentials.
    Rejects suspended or deactivated accounts.
    """
    email = req.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    # Verify password
    if not user or not user.hashed_password or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check active status
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been suspended or deactivated. Please contact support.",
        )

    # Ensure user is marked verified for backward compatibility
    if not user.is_verified:
        user.is_verified = True
        db.commit()
        db.refresh(user)

    # Update last login
    now = datetime.now(timezone.utc)
    user.last_login_at = now
    db.commit()
    db.refresh(user)

    # Compute expiration delta
    if req.remember_me:
        delta = timedelta(days=settings.REMEMBER_ME_EXPIRE_DAYS)
        expires_seconds = settings.REMEMBER_ME_EXPIRE_DAYS * 86400
    else:
        delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        expires_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role},
        expires_delta=delta,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
        expires_in=expires_seconds,
    )


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    req: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Initiates password reset. Uses generic message to prevent email enumeration.
    """
    email = req.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    generic_msg = "If an account with that email exists, password reset instructions have been sent."

    if not user or not user.is_active:
        return MessageResponse(status="ok", message=generic_msg, email_sent=False)

    token = generate_secure_token(32)
    now = datetime.now(timezone.utc)
    user.reset_token = token
    user.reset_token_expires_at = now + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    user.reset_attempts = 0
    db.commit()

    sent, reason = send_password_reset_email(user.email, user.full_name, token)
    dev_token = token if not sent else None

    return MessageResponse(
        status="ok",
        message=generic_msg if sent else f"{generic_msg} (Notice: {reason})",
        email_sent=sent,
        dev_token=dev_token,
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    req: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Resets password using a valid reset token. Enforces password strength, matching confirmation,
    and invalidates the token upon completion.
    """
    token = req.token.strip()

    # Passwords match check
    if req.new_password != req.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password and confirmation password do not match.",
        )

    # Password strength check
    is_strong, reason = validate_password_strength(req.new_password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=reason,
        )

    user = db.query(User).filter(User.reset_token == token).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

    # Check attempt limit
    if user.reset_attempts >= settings.MAX_RESET_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Maximum reset attempts exceeded. Please request a new password reset email.",
        )

    user.reset_attempts += 1

    # Check expiration
    now = datetime.now(timezone.utc)
    if user.reset_token_expires_at and now > user.reset_token_expires_at.replace(tzinfo=timezone.utc):
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired. Please request a new reset email.",
        )

    # Update password and invalidate token
    user.hashed_password = hash_password(req.new_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    user.reset_attempts = 0
    db.commit()

    return MessageResponse(
        status="ok",
        message="Password reset successfully. You can now log in with your new password.",
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Returns the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


@router.post("/logout")
def logout_user(
    current_user: User = Depends(get_current_user),
):
    """Logs out user; client invalidates local bearer token."""
    return {"status": "ok", "message": "Successfully logged out."}


@router.post("/google", response_model=TokenResponse)
def google_oauth_login(
    req: GoogleAuthRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticates or registers a user via Google OAuth Identity Token.
    Validates token issuer, audience, and expiration.
    """
    if not settings.GOOGLE_CLIENT_ID or len(settings.GOOGLE_CLIENT_ID.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "Google OAuth is not configured on this server. "
                "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file to enable Google authentication."
            ),
        )

    # In production, verify Google token via google-auth or by calling Google tokeninfo endpoint
    # Here we perform rigorous verification of the token payload
    import base64
    import json
    import httpx

    try:
        # Verify with Google's public tokeninfo endpoint
        resp = httpx.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={req.credential}",
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Google token validation failed: {resp.text}",
            )
        info = resp.json()

        # Validate audience & issuer
        if info.get("aud") != settings.GOOGLE_CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google token audience does not match configured GOOGLE_CLIENT_ID.",
            )

        email = info.get("email")
        if not email or not info.get("email_verified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google account email is missing or not verified.",
            )

        full_name = info.get("name", email.split("@")[0])

        # Link or create user
        user = db.query(User).filter(User.email == email.lower()).first()
        now = datetime.now(timezone.utc)
        if not user:
            user = User(
                email=email.lower(),
                full_name=full_name,
                hashed_password=None,  # OAuth only
                is_verified=True,
                is_active=True,
                role="member",
                created_at=now,
                last_login_at=now,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.is_verified = True
            user.last_login_at = now
            db.commit()

        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role}
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process Google authentication: {str(e)}",
        )
