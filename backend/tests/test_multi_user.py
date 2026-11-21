from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.core.security import hash_password, create_access_token
from app.models.models import User, Meeting, Utterance, Item, Alert, ChangeProposal, ChangeAction, ProjectMember
from app.models.enums import MeetingStatus, ItemType, ReviewState, AlertKind, AlertState, ProposalState, ActionState, ActionType


from app.db.session import get_db

@pytest.fixture
def clean_client(db):
    """Client with dependency overrides removed to test raw authentication and authorization."""
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def test_direct_api_access_without_token_returns_401(clean_client):
    """Test 13: Direct API access without token returns HTTP 401 Unauthorized."""
    resp = clean_client.get("/meetings/1")
    assert resp.status_code == 401
    assert "authentication required" in resp.json()["detail"].lower()


def test_direct_api_access_with_invalid_token_returns_401(clean_client):
    """Test: Direct API access with invalid or forged Bearer token returns HTTP 401."""
    resp = clean_client.get("/meetings/1", headers={"Authorization": "Bearer invalid.forged.token"})
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


def test_multi_user_project_isolation(clean_client, db):
    """
    Test 14 & Multi-User Security:
    - User A owns private project 'Project-Alpha'.
    - User B is in 'Project-Beta'.
    - User B CANNOT access User A's meetings, transcripts, decisions, or approve User A's repairs.
    """
    # 1. Create User A and User B
    user_a = User(
        email="usera@corp.com",
        full_name="User Alpha",
        hashed_password=hash_password("Password123!"),
        is_verified=True,
        role="member",
    )
    user_b = User(
        email="userb@corp.com",
        full_name="User Beta",
        hashed_password=hash_password("Password123!"),
        is_verified=True,
        role="member",
    )
    admin_user = User(
        email="superadmin@corp.com",
        full_name="Super Admin",
        hashed_password=hash_password("Password123!"),
        is_verified=True,
        role="admin",
    )
    db.add_all([user_a, user_b, admin_user])
    db.commit()
    db.refresh(user_a)
    db.refresh(user_b)
    db.refresh(admin_user)

    # 2. Create User A's meeting in 'Project-Alpha'
    meeting_a = Meeting(
        title="Alpha Architecture Planning",
        date=date(2026, 11, 20),
        project="Project-Alpha",
        region="US",
        release="1.0",
        transcript_ref="alpha.vtt",
        status=MeetingStatus.uploaded,
        owner_id=user_a.id,
    )
    db.add(meeting_a)
    db.flush()

    # Enroll User A in ProjectMember as owner
    pm_a = ProjectMember(project="Project-Alpha", user_id=user_a.id, role="owner")
    db.add(pm_a)

    # Add utterance to meeting A
    utt_a = Utterance(
        meeting_id=meeting_a.id,
        idx=0,
        speaker_raw="Alice",
        text="Confidential architecture discussion for Project Alpha.",
    )
    db.add(utt_a)

    # Add Alert and ChangeProposal for Meeting A
    alert_a = Alert(
        meeting_id=meeting_a.id,
        kind=AlertKind.premise_break,
        verdict="undermines",
        state=AlertState.open,
        old_quote="Old assumption",
        new_quote="New statement",
    )
    db.add(alert_a)
    db.flush()

    proposal_a = ChangeProposal(
        trigger_type="alert",
        trigger_id=alert_a.id,
        summary="Repair for Alpha",
        state=ProposalState.draft,
    )
    db.add(proposal_a)
    db.flush()
    alert_a.proposal_id = proposal_a.id
    db.commit()

    # 3. Generate tokens
    token_a = create_access_token({"sub": str(user_a.id), "email": user_a.email, "role": user_a.role})
    token_b = create_access_token({"sub": str(user_b.id), "email": user_b.email, "role": user_b.role})
    token_admin = create_access_token({"sub": str(admin_user.id), "email": admin_user.email, "role": admin_user.role})

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    # 4. User A accesses their own meeting -> 200 OK
    resp_a = clean_client.get(f"/meetings/{meeting_a.id}", headers=headers_a)
    assert resp_a.status_code == 200
    assert resp_a.json()["project"] == "Project-Alpha"

    # 5. User B attempts to access User A's meeting -> 403 FORBIDDEN!
    resp_b = clean_client.get(f"/meetings/{meeting_a.id}", headers=headers_b)
    assert resp_b.status_code == 403
    assert "access denied" in resp_b.json()["detail"].lower()

    # 6. User B attempts to access User A's transcript utterances -> 403 FORBIDDEN!
    resp_b_utts = clean_client.get(f"/meetings/{meeting_a.id}/utterances", headers=headers_b)
    assert resp_b_utts.status_code == 403

    # 7. User B attempts to access User A's review queue -> 403 FORBIDDEN!
    resp_b_review = clean_client.get(f"/meetings/{meeting_a.id}/review", headers=headers_b)
    assert resp_b_review.status_code == 403

    # 8. User B attempts to approve User A's repair proposal -> 403 FORBIDDEN!
    resp_b_prop = clean_client.post(f"/proposals/{proposal_a.id}/approve", json={"actor": "User B"}, headers=headers_b)
    assert resp_b_prop.status_code == 403

    # 9. Admin user CAN access User A's meeting -> 200 OK
    resp_admin = clean_client.get(f"/meetings/{meeting_a.id}", headers=headers_admin)
    assert resp_admin.status_code == 200

    # 10. Grant User B membership in Project-Alpha -> User B can now access!
    pm_b = ProjectMember(project="Project-Alpha", user_id=user_b.id, role="member")
    db.add(pm_b)
    db.commit()

    resp_b_after = clean_client.get(f"/meetings/{meeting_a.id}", headers=headers_b)
    assert resp_b_after.status_code == 200
