import json
import os
from typing import List

from groq import Groq

from app.knowledge_base import KBSection

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


DRAFT_SYSTEM_PROMPT = """You are a customer support reply-drafting assistant
for Northbeam Analytics.

You will be given a customer's email and a set of knowledge base excerpts.
Draft a helpful, friendly, concise reply using ONLY the information in the
excerpts. Do not invent policies, numbers, or capabilities not present in
the excerpts.

Respond with ONLY valid JSON, no markdown fences:

{
  "draft_reply": "the full reply text, ready to send, signed 'The Northbeam Support Team'",
  "confidence": a number from 0 to 1 for how well the knowledge base excerpts actually answer this specific question,
  "sources_used": ["doc title", "doc title"]
}

Rules:
- If the excerpts don't clearly answer the question, keep confidence LOW
  (below 0.5) and write a reply that acknowledges the question and says a
  team member will follow up with specifics -- never guess at an answer
  the excerpts don't support.
- confidence should reflect topical match AND specificity, not just that
  some excerpt was retrieved.
"""


def draft_reply(subject: str, body: str, kb_sections: List[KBSection]) -> dict:
    client = _get_client()

    if kb_sections:
        excerpts_text = "\n\n---\n\n".join(
            f"[{s.doc_title} — {s.heading}]\n{s.text}" for s in kb_sections
        )
    else:
        excerpts_text = "(no relevant knowledge base excerpts found)"

    user_content = (
        f"Customer email:\nSubject: {subject}\n\n{body}\n\n"
        f"Knowledge base excerpts:\n\n{excerpts_text}"
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.3,
        messages=[
            {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {
            "draft_reply": "A team member will follow up on this shortly.",
            "confidence": 0.0,
            "sources_used": [],
        }

    data.setdefault("confidence", 0.0)
    data.setdefault("sources_used", [])
    return data
