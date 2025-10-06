import os
import json
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


# --- Access-tier filtering logic ---
def filter_dpp_for_user(dpp_json, user_role):
    result = {}
    for section, fields in dpp_json.items():
        access = fields.get("Access_Tier", "").lower()
        if "public" in access:
            result[section] = fields
        elif user_role == "tier1" and "tier 1" in access:
            result[section] = fields
        elif user_role == "tier2" and ("tier 2" in access or "tier 1" in access):
            result[section] = fields
    return result


@app.get("/api/dpp/<panel_id>")
def get_dpp(panel_id):
    user_role = request.args.get("access", "public")  # default = public
    try:
        with open(f"{panel_id}.json", "r", encoding="utf-8") as f:
            dpp_json = json.load(f)
        filtered = filter_dpp_for_user(dpp_json, user_role)
        return jsonify(filtered)
    except FileNotFoundError:
        return jsonify({"error": "Panel not found"}), 404


if __name__ == "__main__":
    # For local testing only; on Render use gunicorn
    app.run(host="0.0.0.0", port=5000)
