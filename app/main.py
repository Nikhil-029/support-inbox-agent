import json
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("support-inbox-agent")

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Ticket, TicketStatus
from app.knowledge_base import knowledge_base
from app.connectors import get_connector
from app.services.pipeline import process_new_emails
from app.rate_limit import enforce_fetch_rate_limit

Base.metadata.create_all(bind=engine)

BASE_DIR = os.path.dirname(__file__)

app = FastAPI(title="Support Inbox Automation Agent")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


@app.on_event("startup")
def startup():
    logger.info("Building knowledge base index...")
    knowledge_base.build()
    logger.info(f"Knowledge base ready: {len(knowledge_base.sections)} sections indexed")


def ticket_to_dict(t: Ticket) -> dict:
    return {
        "id": t.id,
        "from_email": t.from_email,
        "subject": t.subject,
        "body": t.body,
        "intent": t.intent,
        "urgency": t.urgency,
        "confidence": t.confidence,
        "requires_human": t.requires_human,
        "requires_human_reason": t.requires_human_reason,
        "draft_reply": t.draft_reply,
        "sources_used": json.loads(t.sources_used_json or "[]"),
        "status": t.status.value if hasattr(t.status, "value") else t.status,
        "send_error": t.send_error,
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    tickets = db.query(Ticket).order_by(Ticket.created_at.desc()).all()
    demo_mode = os.getenv("DEMO_MODE", "false").lower() == "true"
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tickets": [ticket_to_dict(t) for t in tickets],
            "active_connector": "demo (public showcase)" if demo_mode else os.getenv("ACTIVE_CONNECTOR", "demo"),
            "demo_mode": demo_mode,
        },
    )


@app.post("/api/fetch")
def fetch_emails(request: Request, db: Session = Depends(get_db)):
    enforce_fetch_rate_limit(request)
    connector = get_connector()
    try:
        created = process_new_emails(db, connector)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed while processing new emails")
        raise HTTPException(status_code=502, detail=f"LLM/processing error: {exc}")
    return {"new_tickets": len(created), "tickets": [ticket_to_dict(t) for t in created]}


@app.get("/api/tickets")
def list_tickets(db: Session = Depends(get_db)):
    tickets = db.query(Ticket).order_by(Ticket.created_at.desc()).all()
    return [ticket_to_dict(t) for t in tickets]


@app.post("/api/tickets/{ticket_id}/update")
def update_ticket(ticket_id: int, payload: dict, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if "draft_reply" in payload:
        ticket.draft_reply = payload["draft_reply"]
    db.commit()
    db.refresh(ticket)
    return ticket_to_dict(ticket)


@app.post("/api/tickets/{ticket_id}/approve")
def approve_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    ticket.status = TicketStatus.APPROVED
    db.commit()
    return {"status": "approved"}


@app.post("/api/tickets/{ticket_id}/reject")
def reject_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    ticket.status = TicketStatus.REJECTED
    db.commit()
    return {"status": "rejected"}


@app.post("/api/tickets/{ticket_id}/send")
def send_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    if ticket.status != TicketStatus.APPROVED:
        raise HTTPException(400, "Ticket must be approved before sending")

    connector = get_connector()
    result = connector.send_reply(ticket.from_email, f"Re: {ticket.subject}", ticket.draft_reply)
    ticket.connector_used = connector.name

    if result.success:
        ticket.status = TicketStatus.SENT
        ticket.send_error = None
    else:
        ticket.send_error = result.message

    db.commit()
    return {"status": ticket.status.value, "message": result.message}
