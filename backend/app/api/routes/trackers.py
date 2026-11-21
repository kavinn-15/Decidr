from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import TrackerTicket
from app.schemas.schemas import TrackerTicketRead

router = APIRouter(tags=["trackers"])


@router.get("/mock-tracker", response_class=HTMLResponse)
def get_mock_tracker_ui(db: Session = Depends(get_db)) -> str:
    """
    Simple read-only HTML page showing all tickets, comments, and status in MockTracker.
    """
    tickets = (
        db.query(TrackerTicket)
        .order_by(TrackerTicket.id.desc())
        .all()
    )

    tickets_html = ""
    if not tickets:
        tickets_html = """
        <div class="empty-state">
            <p>No tickets created yet.</p>
            <p class="subtitle">Approved proposals will create tickets here when executed.</p>
        </div>
        """
    else:
        for t in tickets:
            status_class = f"status-{t.status.lower()}"
            labels_html = "".join([f'<span class="tag">{label}</span>' for label in (t.labels or [])])
            
            comments_html = ""
            if t.comments:
                comments_list = "".join([
                    f'<div class="comment-item"><strong>{c.get("created_at", "")[:19]}</strong>: {c.get("text", "")}</div>'
                    for c in t.comments
                ])
                comments_html = f"""
                <div class="comments-section">
                    <div class="comments-title">Comments ({len(t.comments)})</div>
                    {comments_list}
                </div>
                """

            tickets_html += f"""
            <div class="ticket-card" id="{t.ticket_ref}">
                <div class="ticket-header">
                    <div>
                        <span class="ticket-ref">{t.ticket_ref}</span>
                        <span class="ticket-title">{t.title}</span>
                    </div>
                    <span class="badge {status_class}">{t.status}</span>
                </div>
                <div class="ticket-meta">
                    <span>Assignee: <strong>{t.assignee or "Unassigned"}</strong></span>
                    <span>Due: <strong>{t.due_date or "No deadline"}</strong></span>
                    <span>Key: <code>{t.idempotency_key or "None"}</code></span>
                    <span>Created: {t.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if t.created_at else ''}</span>
                </div>
                <div class="tags-container">{labels_html}</div>
                {f'<div class="ticket-body">{t.body}</div>' if t.body else ''}
                {comments_html}
            </div>
            """

    total_count = len(tickets)
    open_count = sum(1 for t in tickets if t.status == "open")
    cancelled_count = sum(1 for t in tickets if t.status == "cancelled")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Decidr Mock Tracker</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f8fafc;
            color: #0f172a;
            margin: 0;
            padding: 32px 16px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        h1 {{
            margin: 0;
            font-size: 26px;
            font-weight: 700;
            color: #0f172a;
        }}
        .stats {{
            display: flex;
            gap: 16px;
        }}
        .stat-badge {{
            background: #ffffff;
            border: 1px solid #e2e8f0;
            padding: 6px 14px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
        }}
        .stat-badge strong {{
            color: #2563eb;
        }}
        .ticket-card {{
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            transition: box-shadow 0.2s;
        }}
        .ticket-card:hover {{
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        }}
        .ticket-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 8px;
        }}
        .ticket-ref {{
            font-family: monospace;
            font-size: 16px;
            font-weight: 700;
            color: #2563eb;
            margin-right: 12px;
        }}
        .ticket-title {{
            font-size: 17px;
            font-weight: 600;
            color: #1e293b;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .status-open {{
            background: #dcfce7;
            color: #15803d;
        }}
        .status-cancelled {{
            background: #f1f5f9;
            color: #64748b;
        }}
        .ticket-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            font-size: 13px;
            color: #64748b;
            margin-bottom: 12px;
        }}
        .ticket-meta code {{
            background: #f1f5f9;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 12px;
        }}
        .tags-container {{
            margin-bottom: 12px;
        }}
        .tag {{
            display: inline-block;
            background: #e0e7ff;
            color: #3730a3;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            margin-right: 6px;
        }}
        .ticket-body {{
            background: #f8fafc;
            border-left: 3px solid #cbd5e1;
            padding: 12px;
            border-radius: 4px;
            font-size: 14px;
            color: #334155;
            white-space: pre-wrap;
            margin-bottom: 14px;
        }}
        .comments-section {{
            border-top: 1px dashed #e2e8f0;
            padding-top: 12px;
            margin-top: 12px;
        }}
        .comments-title {{
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            color: #64748b;
            margin-bottom: 8px;
        }}
        .comment-item {{
            background: #f1f5f9;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 13px;
            color: #1e293b;
            margin-bottom: 6px;
        }}
        .empty-state {{
            text-align: center;
            background: #ffffff;
            border: 2px dashed #e2e8f0;
            border-radius: 12px;
            padding: 48px 24px;
            color: #64748b;
        }}
        .empty-state p {{
            margin: 0;
            font-size: 16px;
            font-weight: 600;
        }}
        .empty-state .subtitle {{
            margin-top: 8px;
            font-size: 14px;
            color: #94a3b8;
            font-weight: 400;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>Decidr Mock Issue Tracker</h1>
                <div style="font-size: 13px; color: #64748b; margin-top: 4px;">Local simulation of external issue tracker</div>
            </div>
            <div class="stats">
                <div class="stat-badge">Total: <strong>{total_count}</strong></div>
                <div class="stat-badge">Open: <strong>{open_count}</strong></div>
                <div class="stat-badge">Cancelled: <strong>{cancelled_count}</strong></div>
            </div>
        </div>
        {tickets_html}
    </div>
</body>
</html>
"""
    return html_content


@router.get("/api/mock-tracker/tickets", response_model=list[TrackerTicketRead])
def get_mock_tracker_tickets_json(db: Session = Depends(get_db)):
    """
    JSON API endpoint for querying mock tracker tickets.
    """
    return (
        db.query(TrackerTicket)
        .order_by(TrackerTicket.id.desc())
        .all()
    )
