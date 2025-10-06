import os
from flask import Flask, request, jsonify
from oracle_automation import process_and_anchor

app = Flask(__name__)

AUTH_TOKEN = os.getenv("AUTH_TOKEN")  # optional bearer auth

@app.get("/")
def health():
    return "🟢 Oracle backend running!"

@app.post("/anchor")
def anchor():
    try:
        # Simple bearer auth
        if AUTH_TOKEN:
            auth = request.headers.get("Authorization")
            if auth != f"Bearer {AUTH_TOKEN}":
                return jsonify({"status": "error", "message": "Unauthorized"}), 401

        payload = request.get_json(force=True)
        panel_id, event_type, tx_hash = process_and_anchor(payload, event_type="installation")

        return jsonify({
            "status": "success",
            "panel_id": panel_id,
            "event_type": event_type,
            "tx_hash": tx_hash
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    # For local testing only; on Render use gunicorn
    app.run(host="0.0.0.0", port=5000)
