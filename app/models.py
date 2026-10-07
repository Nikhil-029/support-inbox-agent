import enum
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum, Boolean
from app.database import Base


class TicketStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"   # drafted, waiting on a human
    APPROVED = "approved"               # human approved, ready to send
    AUTO_SENT = "auto_sent"             # sent automatically, no human touch
    SENT = "sent"                       # human-approved reply, now sent
    REJECTED = "rejected"               # human rejected the draft
    NO_REPLY_NEEDED = "no_reply_needed" # classified as not needing a reply (e.g. spam)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, nullable=True, index=True)

    from_email = Column(String, nullable=False)
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=False)
    received_at = Column(String, nullable=True)

    intent = Column(String, nullable=True)
    urgency = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    requires_human = Column(Boolean, default=True)
    requires_human_reason = Column(String, nullable=True)

    draft_reply = Column(Text, nullable=True)
    sources_used_json = Column(Text, nullable=True)

    status = Column(Enum(TicketStatus), default=TicketStatus.PENDING_REVIEW)
    connector_used = Column(String, nullable=True)
    send_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
