
import os, re, json, datetime, math
from typing import Dict, List, Optional

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Optional OpenAI client (lazy import to avoid hard dependency when key not present)
def _get_openai():
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        return None

def extract_info(text: str) -> Dict[str, Optional[str]]:
    # simple regex-based extraction
    phone_match = re.search(r'(\+?\d[\d\s\-]{7,}\d)', text)
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    # crude "requirements" summary: first 30 words
    words = re.findall(r'\w+', text)
    summary = " ".join(words[:30]) + ("..." if len(words) > 30 else "")
    return {
        "phone": phone_match.group(1) if phone_match else None,
        "alt_email": email_match.group(0) if email_match else None,
        "summary": summary
    }

NEG_WORDS = {"immediately","urgent","cannot","error","down","failed","critical","asap","blocked","not working","issue","frustrated","angry","delay","access","locked"}
POS_WORDS = {"thanks","thank you","great","appreciate","working","resolved","love","happy"}

def analyze_sentiment(text: str) -> str:
    client = _get_openai()
    if client:
        try:
            # lightweight classification
            prompt = f"Classify the sentiment of the following customer email as Positive, Negative, or Neutral. Only return one word.\n\nEmail:\n{text}"
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"user","content":prompt}],
                temperature=0
            )
            out = resp.choices[0].message.content.strip()
            out = out.capitalize()
            return "Positive" if out.startswith("Pos") else "Negative" if out.startswith("Neg") else "Neutral"
        except Exception:
            pass
    # fallback heuristic
    t = text.lower()
    score = 0
    for w in NEG_WORDS:
        if w in t:
            score -= 1
    for w in POS_WORDS:
        if w in t:
            score += 1
    if score > 0: return "Positive"
    if score < 0: return "Negative"
    return "Neutral"

def determine_priority(text: str) -> str:
    t = text.lower()
    urgent_tokens = ["immediately","urgent","critical","cannot access","down","asap","blocked","high priority","severe","production","p0","p1"]
    return "Urgent" if any(tok in t for tok in urgent_tokens) else "Not urgent"

def _load_kb_docs():
    kb_path = os.path.join(os.path.dirname(__file__), "..", "docs", "kb")
    docs = []
    if os.path.isdir(kb_path):
        for fn in os.listdir(kb_path):
            if fn.endswith(".md") or fn.endswith(".txt") or fn.endswith(".json"):
                with open(os.path.join(kb_path, fn), "r", encoding="utf-8") as f:
                    docs.append({"title": fn, "content": f.read()})
    return docs

def retrieve_context(query: str, top_k: int = 2) -> List[Dict]:
    # Simple term-overlap retrieval to avoid heavy deps
    docs = _load_kb_docs()
    q_terms = set(re.findall(r'\w+', query.lower()))
    scored = []
    for d in docs:
        d_terms = set(re.findall(r'\w+', d["content"].lower()))
        overlap = len(q_terms & d_terms)
        scored.append((overlap, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for score, d in scored[:top_k] if score > 0] or docs[:1]

def generate_reply(sender: str, subject: str, body: str, sentiment: str, priority: str) -> str:
    client = _get_openai()
    context_docs = retrieve_context(subject + "\n" + body, top_k=2)
    kb_text = "\n\n".join([f"[{d['title']}]\n{d['content']}" for d in context_docs])

    sys_prompt = (
        "You are a helpful, professional customer support assistant. "
        "Write concise, empathetic, and actionable replies. If the customer is frustrated, acknowledge it. "
        "Use the provided knowledge base when relevant. Keep under 180 words."
    )

    user_prompt = f"""
Customer email (from: {sender}):
Subject: {subject}

Body:
{body}

Detected sentiment: {sentiment}
Priority: {priority}

Knowledge Base:
{kb_text}

Write a reply email. Include:
- A brief acknowledgement
- A specific response referencing the product/issue if mentioned
- Clear next steps or solution
- A polite closing with a ticket-style reference placeholder (#{{TICKET_ID}})
"""

    if client:
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role":"system","content":sys_prompt},
                    {"role":"user","content":user_prompt}
                ],
                temperature=0.3
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            pass

    # Fallback templated reply
    greeting = "Hi there,"
    if sentiment == "Negative":
        ack = "I'm sorry for the trouble you're facing. I understand how frustrating this can be."
    else:
        ack = "Thanks for reaching out. I'm happy to help."

    steps = "Could you share any error screenshots and the email/ID used to log in? Meanwhile, try resetting your password and clearing cache."
    closing = "We’ll prioritize this and get back quickly.\n\nBest regards,\nSupport Team\nRef: #{TICKET_ID}"
    return f"""{greeting}

{ack}

Regarding your message about "{subject}", here's what we suggest:
{steps}

If this is time-sensitive, reply with "URGENT" and your phone number for a quick call-back.

{closing}"""
