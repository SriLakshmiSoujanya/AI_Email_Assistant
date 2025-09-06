
import os, imaplib, email, re, datetime
from email.header import decode_header
from .db_utils import upsert_email_by_message_id
from .ai_utils import analyze_sentiment, determine_priority, extract_info

IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.environ.get("IMAP_USER")  # your email
IMAP_PASS = os.environ.get("IMAP_PASS")  # app password if using Gmail 2FA

SUPPORT_KEYWORDS = ["support", "query", "request", "help"]

def _decode_header_part(part):
    if not part:
        return ""
    decoded = decode_header(part)
    out = ""
    for text, enc in decoded:
        if isinstance(text, bytes):
            out += text.decode(enc or "utf-8", errors="ignore")
        else:
            out += text
    return out

def fetch_and_ingest(limit=50):
    if not (IMAP_USER and IMAP_PASS):
        raise RuntimeError("IMAP_USER or IMAP_PASS not set. Please add them to .env")

    M = imaplib.IMAP4_SSL(IMAP_HOST)
    M.login(IMAP_USER, IMAP_PASS)
    M.select("INBOX")

    # Search all unseen or recent emails; fallback to ALL
    for criterion in [r'(UNSEEN)', r'(RECENT)', r'(ALL)']:
        status, data = M.search(None, criterion)
        if status == "OK" and data and data[0]:
            ids = data[0].split()
            break
    else:
        ids = []

    ids = ids[-limit:]

    ingested = 0
    for num in reversed(ids):
        status, msg_data = M.fetch(num, "(RFC822)")
        if status != "OK":
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        message_id = msg.get("Message-ID")
        raw_subject = _decode_header_part(msg.get("Subject"))
        subject = raw_subject.strip()
        from_addr = email.utils.parseaddr(msg.get("From"))[1]
        date_tuple = email.utils.parsedate_tz(msg.get("Date"))
        if date_tuple:
            ts = email.utils.mktime_tz(date_tuple)
            received_at = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        else:
            received_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # filter by keywords in subject
        subj_lower = subject.lower()
        if not any(k in subj_lower for k in SUPPORT_KEYWORDS):
            continue

        # extract body (prefer plain)
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = str(part.get("Content-Disposition"))
                if ctype == "text/plain" and "attachment" not in (disp or ""):
                    charset = part.get_content_charset() or "utf-8"
                    body += part.get_payload(decode=True).decode(charset, errors="ignore")
        else:
            charset = msg.get_content_charset() or "utf-8"
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                body = payload.decode(charset, errors="ignore")
            else:
                body = str(payload)

        info = extract_info(body)
        sentiment = analyze_sentiment(body)
        priority = determine_priority(subject + " " + body)

        rec = {
            "message_id": message_id,
            "sender": from_addr,
            "subject": subject,
            "body": body,
            "received_at": received_at,
            "sentiment": sentiment,
            "priority": priority,
            "phone": info.get("phone"),
            "alt_email": info.get("alt_email"),
            "request_summary": info.get("summary"),
            "status": "pending"
        }
        upsert_email_by_message_id(rec)
        ingested += 1

    M.logout()
    return {"ingested": ingested}
