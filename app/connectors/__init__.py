import os

from app.connectors.base import MailboxConnector

_CONNECTOR_CACHE = {}


def get_connector(name: str = None) -> MailboxConnector:
    if os.getenv("DEMO_MODE", "false").lower() == "true":
        name = "demo"
    else:
        name = name or os.getenv("ACTIVE_CONNECTOR", "demo")

    if name in _CONNECTOR_CACHE:
        return _CONNECTOR_CACHE[name]

    if name == "demo":
        from app.connectors.demo_connector import DemoConnector
        connector = DemoConnector()
    elif name == "imap":
        from app.connectors.imap_connector import IMAPConnector
        connector = IMAPConnector()
    else:
        raise ValueError(f"Unknown connector: {name}")

    _CONNECTOR_CACHE[name] = connector
    return connector
