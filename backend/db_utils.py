
import sqlite3
from contextlib import contextmanager
import os

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "assistant.db"))

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT,
    sender TEXT,
    subject TEXT,
    body TEXT,
    received_at TEXT,
    sentiment TEXT,
    priority TEXT,
    phone TEXT,
    alt_email TEXT,
    request_summary TEXT,
    status TEXT DEFAULT 'pending' -- pending | responded
);

CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER,
    draft TEXT,
    final TEXT,
    sent_at TEXT,
    FOREIGN KEY (email_id) REFERENCES emails(id)
);
"""

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.commit()
    conn.close()

def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)

def insert_email(rec):
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO emails (message_id, sender, subject, body, received_at, sentiment, priority, phone, alt_email, request_summary, status)
            VALUES (:message_id, :sender, :subject, :body, :received_at, :sentiment, :priority, :phone, :alt_email, :request_summary, :status)
        """, rec)
        return cur.lastrowid

def upsert_email_by_message_id(rec):
    # avoid duplicates using message_id if provided
    with get_conn() as conn:
        if rec.get("message_id"):
            cur = conn.execute("SELECT id FROM emails WHERE message_id = ?", (rec["message_id"],))
            row = cur.fetchone()
            if row:
                conn.execute("""
                    UPDATE emails SET sender=:sender, subject=:subject, body=:body, received_at=:received_at,
                        sentiment=:sentiment, priority=:priority, phone=:phone, alt_email=:alt_email,
                        request_summary=:request_summary, status=:status
                    WHERE id = :id
                """, {**rec, "id": row["id"]})
                return row["id"]
        return insert_email(rec)

def list_emails(order_by_priority=True, only_support=True):
    with get_conn() as conn:
        q = "SELECT * FROM emails"
        if only_support:
            q += " WHERE subject LIKE '%Support%' OR subject LIKE '%Query%' OR subject LIKE '%Request%' OR subject LIKE '%Help%'"
        if order_by_priority:
            q += " ORDER BY CASE priority WHEN 'Urgent' THEN 0 ELSE 1 END, datetime(received_at) DESC"
        else:
            q += " ORDER BY datetime(received_at) DESC"
        cur = conn.execute(q)
        return [dict(r) for r in cur.fetchall()]

def get_email(email_id):
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM emails WHERE id=?", (email_id,))
        row = cur.fetchone()
        return dict(row) if row else None

def mark_responded(email_id):
    with get_conn() as conn:
        conn.execute("UPDATE emails SET status='responded' WHERE id=?", (email_id,))

def insert_response(email_id, draft, final=None, sent_at=None):
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO responses (email_id, draft, final, sent_at)
            VALUES (?, ?, ?, ?)
        """, (email_id, draft, final, sent_at))
        return cur.lastrowid

def analytics(last_hours=24):
    with get_conn() as conn:
        res = {}
        res["total"] = conn.execute("SELECT COUNT(*) c FROM emails").fetchone()[0]
        res["last_24h"] = conn.execute("SELECT COUNT(*) c FROM emails WHERE datetime(received_at) >= datetime('now', '-24 hours')").fetchone()[0]
        res["resolved"] = conn.execute("SELECT COUNT(*) c FROM emails WHERE status='responded'").fetchone()[0]
        res["pending"] = conn.execute("SELECT COUNT(*) c FROM emails WHERE status!='responded'").fetchone()[0]
        # sentiment counts
        res["sentiment"] = {k: v for k, v in conn.execute("SELECT sentiment, COUNT(*) FROM emails GROUP BY sentiment").fetchall() if k}
        # priority counts
        res["priority"] = {k: v for k, v in conn.execute("SELECT priority, COUNT(*) FROM emails GROUP BY priority").fetchall() if k}
        return res
