import json
import os

from groq import Groq

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set. Add it to your .env file.")
        _client = Groq(api_key=api_key)
    return _client


CLASSIFY_SYSTEM_PROMPT = """You are a support inbox triage system.

Classify the incoming email and respond with ONLY valid JSON, no markdown
fences, no commentary:

{
  "intent": one of ["billing_question", "account_access", "api_integration", "complaint", "general_inquiry", "spam_or_other"],
  "urgency": one of ["low", "medium", "high"],
  "is_complaint_or_escalation": boolean,
  "summary": "one sentence summary of what the sender wants"
}

Rules:
- "complaint" or is_complaint_or_escalation=true applies whenever the sender
  expresses frustration, mentions cancelling, says this is a repeated issue,
  or demands a human -- even if the underlying topic is billing or account
  access. Tone matters as much as topic.
- "spam_or_other" covers anything that is not a genuine support request.
- urgency "high" means the sender is blocked from using the product right
  now, or is threatening to churn.
"""


def classify_email(subject: str, body: str) -> dict:
    client = _get_client()

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
            {"role": "user", "content": f"Subject: {subject}\n\nBody:\n{body}"},
        ],
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "intent": "general_inquiry",
            "urgency": "medium",
            "is_complaint_or_escalation": True,
            "summary": "Could not parse classification -- routed to human review.",
        }
