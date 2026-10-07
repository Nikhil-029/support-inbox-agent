# Support Inbox Automation Agent

Reads incoming support emails, classifies what they need, drafts a reply
grounded in your own FAQ/knowledge base, and either sends it automatically
or holds it for a human — depending on how confident and how risky it is.

## What it does

1. **Fetch** — pull new emails from a mailbox (demo sample data or a real
   IMAP inbox)
2. **Classify** — an LLM call tags each email with an intent (billing,
   account access, API/integration, complaint, general inquiry, spam) and
   an urgency level
3. **Retrieve** — the email is matched against your knowledge base
   (markdown FAQ docs, indexed with TF-IDF) to find the most relevant
   passages
4. **Draft** — an LLM drafts a reply using *only* the retrieved passages,
   with a confidence score for how well they actually answer the question
5. **Decide** — a deliberately conservative policy decides what happens
   next:
   - **Auto-send**: intent is in the safe list (billing/account/API
     questions), it's not flagged as a complaint, urgency isn't high, and
     draft confidence clears the threshold
   - **Human review**: anything else — and the UI shows *exactly why* it
     was held (e.g. "flagged as a complaint/escalation", "confidence 0.41
     is below the 0.85 threshold")
6. **Review** — a human can edit the draft inline, approve, reject, or
   send it

## Why this design

The whole point of a support-automation tool is that a bad auto-send is
far more costly than an over-cautious one. So the auto-send rule is an
AND of four independent checks, not a single confidence score — a
complaint-sounding email about billing (a normally auto-sendable intent)
still gets held for a human, because tone matters as much as topic.

## Architecture

```
mailbox connector (demo | IMAP)
     │
     ▼
fetch new emails (dedup by message_id)
     │
     ▼
LLM classification (intent, urgency, complaint flag)
     │
     ▼
spam/other?  ──yes──▶  no_reply_needed
     │no
     ▼
TF-IDF retrieval over knowledge_base/*.md
     │
     ▼
LLM drafts reply, grounded only in retrieved passages, self-reports confidence
     │
     ▼
auto-send rules (intent + complaint flag + urgency + confidence)
     │
  ┌──┴──┐
 pass   fail
  │      │
  ▼      ▼
auto-send   pending_review (with a human-readable hold reason)
            │
            ▼
       human edits/approves/rejects → send
```

The mailbox connector follows the same pluggable-interface pattern as the
Invoice Sync Agent's accounting connectors: `MailboxConnector` defines
`fetch_new_emails()` / `send_reply()`, and the rest of the app never talks
to IMAP/SMTP directly. Swapping in Gmail API or Outlook Graph later is a
new connector file, not a rewrite.

## Setup

### 1. Install

```bash
python -m venv venv
source venv/bin/activate      # venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your Groq API key.

### 2. Run

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000, click **Fetch new emails** — this loads the
4 sample emails in `data/sample_emails/`, which deliberately cover every
routing path: a clean FAQ match (auto-send candidate), a complaint that
must be held regardless of confidence, a vague question with weak
retrieval (low confidence, held), and another clean FAQ match.

### 3. Connect a real mailbox (optional)

Set `ACTIVE_CONNECTOR=imap` in `.env` and fill in `IMAP_*`/`SMTP_*`. For
Gmail, use an [App Password](https://myaccount.google.com/apppasswords),
not your real password.

### 4. Customize the knowledge base

Add or edit markdown files in `knowledge_base/` — each `##` heading
becomes one retrievable section. No rebuild step needed beyond restarting
the app (the index is built fresh on startup).

## Demo tips

- Walk through all 4 sample emails and point out *why* each one landed
  where it did — that's the actual feature, not just "it drafted a
  reply"
- Edit a held draft before approving it, to show the human-in-the-loop
  step isn't just a rubber stamp
- The `requires_human_reason` column is worth narrating line by line —
  it's what makes this trustworthy enough to actually deploy, versus a
  demo that silently auto-sends everything

## Possible extensions

- Gmail API / Outlook Graph connectors (same `MailboxConnector` interface)
- Per-category auto-send thresholds instead of one global value
- A feedback loop where edited drafts get added back into the knowledge
  base as examples
