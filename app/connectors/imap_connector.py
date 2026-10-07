import email
import imaplib
import os
import smtplib
from email.header import decode_header
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
from typing import List

from app.connectors.base import MailboxConnector, IncomingEmail, SendResult


def _decode(value) -> str:
    if value is None:
        return ""
    parts = decode_header(value)
    decoded = ""
    for text, charset in parts:
        if isinstance(text, bytes):
            decoded += text.decode(charset or "utf-8", errors="replace")
        else:
            decoded += text
    return decoded


class IMAPConnector(MailboxConnector):
    """
    Fetches unseen emails from a real mailbox via IMAP, and sends replies
    via SMTP. Only used when ACTIVE_CONNECTOR=imap -- most people should
    start with the demo connector, which needs no real credentials.
    """
    name = "imap"

    def __init__(self):
        self.imap_host = os.getenv("IMAP_HOST")
        self.imap_port = int(os.getenv("IMAP_PORT", "993"))
        self.imap_user = os.getenv("IMAP_USER")
        self.imap_password = os.getenv("IMAP_PASSWORD")

        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_password = os.getenv("SMTP_PASSWORD")

        missing = [
            n for n, v in [
                ("IMAP_HOST", self.imap_host),
                ("IMAP_USER", self.imap_user),
                ("IMAP_PASSWORD", self.imap_password),
            ] if not v
        ]
        if missing:
            raise RuntimeError(f"Missing IMAP env vars: {', '.join(missing)}")

    def fetch_new_emails(self) -> List[IncomingEmail]:
        results = []
        conn = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        try:
            conn.login(self.imap_user, self.imap_password)
            conn.select("INBOX")

            status, data = conn.search(None, "UNSEEN")
            if status != "OK":
                return results

            for num in data[0].split():
                status, msg_data = conn.fetch(num, "(RFC822)")
                if status != "OK":
                    continue

                msg = email.message_from_bytes(msg_data[0][1])
                message_id = msg.get("Message-ID", f"imap-{num.decode()}")
                subject = _decode(msg.get("Subject"))
                from_email = _decode(msg.get("From"))

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            payload = part.get_payload(decode=True)
                            if payload:
                                body = payload.decode(
                                    part.get_content_charset() or "utf-8",
                                    errors="replace",
                                )
                            break
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        body = payload.decode(
                            msg.get_content_charset() or "utf-8", errors="replace"
                        )

                try:
                    received_at = parsedate_to_datetime(msg.get("Date")).isoformat()
                except Exception:
                    received_at = ""

                results.append(IncomingEmail(
                    message_id=message_id,
                    from_email=from_email,
                    subject=subject,
                    body=body,
                    received_at=received_at,
                ))
        finally:
            conn.logout()

        return results

    def send_reply(self, to_email: str, subject: str, body: str) -> SendResult:
        if not self.smtp_host or not self.smtp_user or not self.smtp_password:
            return SendResult(success=False, message="SMTP credentials not configured")

        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = self.smtp_user
            msg["To"] = to_email

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_user, [to_email], msg.as_string())

            return SendResult(success=True, message="Sent via SMTP")
        except Exception as exc:  # noqa: BLE001
            return SendResult(success=False, message=str(exc))
