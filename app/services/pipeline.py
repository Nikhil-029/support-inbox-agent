"""
Orchestrates the full loop: fetch new emails -> classify intent/urgency ->
retrieve relevant KB sections -> draft a grounded reply -> decide whether
it's safe to auto-send or must go to a human.

Auto-send safety rules (deliberately conservative -- false negatives
[sending something reviewable to review] are fine, false positives
[auto-sending something that should have been reviewed] are not):
  - intent must be in AUTO_SENDABLE_INTENTS
  - is_complaint_or_escalation must be False
  - urgency must not be "high"
  - draft confidence must be >= AUTO_SEND_CONFIDENCE_THRESHOLD
Anything that fails any of these goes to PENDING_REVIEW with a reason
recorded, so a human reviewer can see *why* it was held.
"""
import json
import logging
import os
from typing import List

from sqlalchemy.orm import Session

from app.models import Ticket, TicketStatus
from app.knowledge_base import knowledge_base
from app.services.classifier import classify_email
from app.services.responder import draft_reply
from app.connectors.base import MailboxConnector

logger = logging.getLogger("support-inbox-agent")

AUTO_SENDABLE_INTENTS = {"billing_question", "account_access", "api_integration"}


def _auto_send_threshold() -> float:
    return float(os.getenv("AUTO_SEND_CONFIDENCE_THRESHOLD", "0.85"))


def process_new_emails(db: Session, connector: MailboxConnector) -> List[Ticket]:
    incoming = connector.fetch_new_emails()
    known_ids = {mid for (mid,) in db.query(Ticket.message_id).all() if mid}

    created: List[Ticket] = []

    for email in incoming:
        if email.message_id in known_ids:
            continue

        try:
            classification = classify_email(email.subject, email.body)
        except Exception as exc:  # noqa: BLE001
            # One email's LLM call failing (rate limit, transient network
            # error) shouldn't block the rest of the batch -- record it as
            # a ticket that needs a human, with the error visible, and
            # move on to the next email.
            logger.exception("Classification failed for %s", email.message_id)
            ticket = Ticket(
                message_id=email.message_id,
                from_email=email.from_email,
                subject=email.subject,
                body=email.body,
                received_at=email.received_at,
                status=TicketStatus.PENDING_REVIEW,
                requires_human=True,
                requires_human_reason=f"classification failed: {exc}",
            )
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            created.append(ticket)
            continue

        intent = classification.get("intent", "general_inquiry")
        urgency = classification.get("urgency", "medium")
        is_complaint = bool(classification.get("is_complaint_or_escalation", False))

        ticket = Ticket(
            message_id=email.message_id,
            from_email=email.from_email,
            subject=email.subject,
            body=email.body,
            received_at=email.received_at,
            intent=intent,
            urgency=urgency,
        )

        if intent == "spam_or_other":
            ticket.status = TicketStatus.NO_REPLY_NEEDED
            ticket.requires_human = False
            ticket.requires_human_reason = None
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            created.append(ticket)
            continue

        kb_sections = knowledge_base.search(f"{email.subject}\n{email.body}", top_k=3)
        try:
            draft = draft_reply(email.subject, email.body, kb_sections)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Drafting failed for %s", email.message_id)
            ticket.status = TicketStatus.PENDING_REVIEW
            ticket.requires_human = True
            ticket.requires_human_reason = f"reply drafting failed: {exc}"
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            created.append(ticket)
            continue

        ticket.draft_reply = draft.get("draft_reply", "")
        ticket.confidence = float(draft.get("confidence", 0.0))
        ticket.sources_used_json = json.dumps(draft.get("sources_used", []))

        hold_reasons = []
        if intent not in AUTO_SENDABLE_INTENTS:
            hold_reasons.append(f"intent '{intent}' is not in the auto-send list")
        if is_complaint:
            hold_reasons.append("flagged as a complaint/escalation")
        if urgency == "high":
            hold_reasons.append("urgency is high")
        if ticket.confidence < _auto_send_threshold():
            hold_reasons.append(
                f"confidence {ticket.confidence:.2f} is below the "
                f"{_auto_send_threshold():.2f} auto-send threshold"
            )

        if hold_reasons:
            ticket.requires_human = True
            ticket.requires_human_reason = "; ".join(hold_reasons)
            ticket.status = TicketStatus.PENDING_REVIEW
        else:
            ticket.requires_human = False
            result = connector.send_reply(email.from_email, f"Re: {email.subject}", ticket.draft_reply)
            ticket.connector_used = connector.name
            if result.success:
                ticket.status = TicketStatus.AUTO_SENT
            else:
                ticket.status = TicketStatus.PENDING_REVIEW
                ticket.requires_human = True
                ticket.requires_human_reason = f"auto-send failed: {result.message}"

        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        created.append(ticket)

    return created
