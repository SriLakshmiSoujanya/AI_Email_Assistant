
import os, datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

from .db_utils import init_db, list_emails, get_email, insert_response, mark_responded, analytics
from .email_utils import fetch_and_ingest
from .ai_utils import analyze_sentiment, determine_priority, generate_reply

load_dotenv()

app = Flask(__name__)
CORS(app)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/init", methods=["POST"])
def init():
    init_db()
    return jsonify({"ok": True})

@app.route("/fetch_emails", methods=["POST"])
def fetch_emails():
    limit = int(request.json.get("limit", 50)) if request.is_json else 50
    out = fetch_and_ingest(limit=limit)
    return jsonify(out)

@app.route("/emails", methods=["GET"])
def emails():
    order = request.args.get("order_by_priority", "true").lower() == "true"
    only_support = request.args.get("only_support", "true").lower() == "true"
    rows = list_emails(order_by_priority=order, only_support=only_support)
    return jsonify(rows)

@app.route("/respond", methods=["POST"])
def respond():
    data = request.get_json(force=True)
    email_id = int(data["email_id"])
    row = get_email(email_id)
    if not row:
        return jsonify({"error": "email not found"}), 404

    draft = generate_reply(row["sender"], row["subject"], row["body"], row.get("sentiment") or "Neutral", row.get("priority") or "Not urgent")
    rid = insert_response(email_id, draft=draft)
    return jsonify({"response_id": rid, "draft": draft})

@app.route("/send", methods=["POST"])
def send():
    # Sending via SMTP can be added here; for now we simulate and mark responded.
    data = request.get_json(force=True)
    email_id = int(data["email_id"])
    final_text = data.get("final") or data.get("draft")
    rid = insert_response(email_id, draft=final_text, final=final_text, sent_at=datetime.datetime.utcnow().isoformat(timespec='seconds'))
    mark_responded(email_id)
    return jsonify({"sent": True, "response_id": rid})

@app.route("/analytics", methods=["GET"])
def analytics_ep():
    return jsonify(analytics())

if __name__ == "__main__":
    # local debug
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
