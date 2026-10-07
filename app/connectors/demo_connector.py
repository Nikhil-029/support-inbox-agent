"""
DemoConnector -- used by default so this project can be tested, and
deployed as a public demo, without any real mailbox credentials and
without ever sending a real email.

fetch_new_emails() reads a fixed set of sample emails from
data/sample_emails/*.json. The pipeline service skips any message_id it
has already turned into a ticket, so calling this repeatedly is safe.

send_reply() never makes a network call -- it just returns success
immediately. What the UI shows as "sent" only ever means a ticket's
status was updated locally.
"""
import json
import os
from typing import List

from app.connectors.base import MailboxConnector, IncomingEmail, SendResult

SAMPLE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "sample_emails"
)


class DemoConnector(MailboxConnector):
    name = "demo"

    def fetch_new_emails(self) -> List[IncomingEmail]:
        emails = []
        if not os.path.isdir(SAMPLE_DIR):
            return emails

        for filename in sorted(os.listdir(SAMPLE_DIR)):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(SAMPLE_DIR, filename)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            emails.append(IncomingEmail(
                message_id=data["message_id"],
                from_email=data["from_email"],
                subject=data.get("subject", ""),
                body=data["body"],
                received_at=data.get("received_at", ""),
            ))

        return emails

    def send_reply(self, to_email: str, subject: str, body: str) -> SendResult:
        return SendResult(success=True, message="Demo mode -- no real email sent")
