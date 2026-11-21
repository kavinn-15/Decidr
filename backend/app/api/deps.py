from typing import Optional
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.models import User, ProjectMember, Meeting

security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """
    Validates the Bearer JWT token from the Authorization header or HTTPBearer credentials.
    Returns the authenticated User or raises HTTP 401 Unauthorized.
    """
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with this token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    return user


def get_current_verified_user(
    user: User = Depends(get_current_user),
) -> User:
    """
    Ensures the authenticated user has verified their email address.
    """
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address not verified. Please verify your email before continuing.",
        )
    return user


def require_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Enforces administrator authorization.
    Raises HTTP 403 Forbidden if the authenticated user does not have the 'admin' role.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required to perform this action.",
        )
    return current_user



def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Returns the User if a valid Bearer token is provided, or None if omitted/invalid.
    """
    try:
        return get_current_user(credentials=credentials, authorization=authorization, db=db)
    except HTTPException:
        return None


def verify_project_access(
    project: str,
    user: User,
    db: Session,
    required_role: str = "member",
) -> bool:
    """
    Enforces multi-user project isolation:
    - Admins have access to all projects.
    - If user is a member/owner of the project, access is granted.
    - If project is private to another user, raises HTTP 403 Forbidden.
    """
    if user.role == "admin":
        return True

    # Check explicit project membership
    membership = (
        db.query(ProjectMember)
        .filter(ProjectMember.project == project, ProjectMember.user_id == user.id)
        .first()
    )
    if membership:
        return True

    # Check if project has an owner or any members
    has_owner = db.query(Meeting).filter(Meeting.project == project, Meeting.owner_id.isnot(None)).first()
    has_members = db.query(ProjectMember).filter(ProjectMember.project == project).first()

    if has_owner or has_members:
        # Project is private and current user is not a member!
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You do not have permission to access project '{project}'.",
        )

    # Legacy demo projects without specific owners are accessible
    return True
