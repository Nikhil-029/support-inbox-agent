"""
Every mailbox connector (demo, IMAP/SMTP, ...) implements this same
interface. The rest of the app only ever talks to `MailboxConnector`,
never to a specific email library directly -- same pluggable-connector
pattern used in the invoice sync agent's AccountingConnector.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class IncomingEmail:
    message_id: str
    from_email: str
    subject: str
    body: str
    received_at: str


@dataclass
class SendResult:
    success: bool
    message: str = ""


class MailboxConnector(ABC):
    name: str = "base"

    @abstractmethod
    def fetch_new_emails(self) -> List[IncomingEmail]:
        raise NotImplementedError

    @abstractmethod
    def send_reply(self, to_email: str, subject: str, body: str) -> SendResult:
        raise NotImplementedError
