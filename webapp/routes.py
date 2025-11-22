# routes.py
import os
import json
import traceback
from functools import wraps
from flask import (
    request, jsonify, render_template, redirect, url_for,
    abort, current_app
)

from app import app
from db import db
from models import Scheme, SchemeRule, UserProfile, MatchResult

# ------------------------------------------------------------------
# Matcher integration: try direct python import first, else HTTP call
# Person B should expose a function: match_profile(profile: dict) -> list[dict]
# Each dict: {"scheme_id": int, "result": "eligible"/"maybe"/"not", "score": float, "reasons": {...}}
# ------------------------------------------------------------------
MATCHER_TYPE = "none"
match_profile = None

try:
    # try direct import (preferred)
    from matcher.engine import match_profile as match_profile_py  # adjust path if needed
    match_profile = match_profile_py
    MATCHER_TYPE = "python"
    app.logger.info("Matcher integrated: python import")
except Exception:
    # fallback to HTTP
    MATCHER_HTTP_URL = os.getenv("MATCHER_HTTP_URL", "http://localhost:8000/match")
    MATCHER_TYPE = "http"
    app.logger.info("Matcher not available via python import; will use HTTP at %s", MATCHER_HTTP_URL)


# ------------------------------------------------------------------
# Basic admin auth decorator (very small, env-configured)
# Use ADMIN_USER and ADMIN_PASS environment variables.
# For production, replace with proper auth!
# ------------------------------------------------------------------
def check_admin_auth(username, password):
    return username == os.getenv("ADMIN_USER", "admin") and password == os.getenv("ADMIN_PASS", "password")


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_admin_auth(auth.username, auth.password):
            return current_app.make_response(('Could not verify your access level for that URL.\n'
                                              'You have to login with proper credentials', 401,
                                              {'WWW-Authenticate': 'Basic realm="Login Required"'}))
        return f(*args, **kwargs)
    return decorated


# ------------------------------------------------------------------
# Landing page
# ------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html") if os.path.exists(os.path.join(app.root_path, "templates", "index.html")) else "Gov Schemes - Home"


# ------------------------------------------------------------------
# Simple profile input page (Jinja form) - client-side JS posts to /api/match
# ------------------------------------------------------------------
@app.route("/match", methods=["GET"])
def match_form():
    # If template exists, render it. Else show a minimal HTML form
    template_path = os.path.join(app.root_path, "templates", "match_form.html")
    if os.path.exists(template_path):
        return render_template("match_form.html")
    return """
    <h2>Profile Input</h2>
    <form id="p">
      Age: <input name="age"><br>
      Income: <input name="income"><br>
      Gender: <input name="gender"><br>
      State: <input name="state"><br>
      Occupation: <input name="occupation"><br>
      <button type="submit">Submit</button>
    </form>
    <pre id="out"></pre>
    <script>
    document.getElementById('p').onsubmit = async e => {
      e.preventDefault();
      const f = e.target;
      const data = {
        age: Number(f.age.value) || null,
        income: Number(f.income.value) || null,
        gender: f.gender.value || null,
        state: f.state.value || null,
        occupation: f.occupation.value || null
      };
      const res = await fetch('/api/match', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(data)});
      const j = await res.json();
      document.getElementById('out').innerText = JSON.stringify(j, null, 2);
    };
    </script>
    """


# ------------------------------------------------------------------
# API: get scheme details + its parsed rules
# ------------------------------------------------------------------
@app.route("/api/scheme/<int:scheme_id>", methods=["GET"])
def api_scheme(scheme_id):
    scheme = Scheme.query.get_or_404(scheme_id)
    rules = SchemeRule.query.filter_by(scheme_id=scheme_id).all()
    return jsonify({
        "scheme": scheme.to_dict() if hasattr(scheme, "to_dict") else {
            "id": scheme.id, "title": scheme.title, "description": scheme.description, "source_url": scheme.source_url
        },
        "rules": [
            {
                "id": r.id,
                "rule_json": r.rule_json,
                "snippet": r.snippet,
                "parser_confidence": r.parser_confidence,
                "verified": r.verified
            } for r in rules
        ]
    })


# ------------------------------------------------------------------
# API: run matching for a profile
# - saves user profile into users table
# - persists match results into matches
# ------------------------------------------------------------------
@app.route("/api/match", methods=["POST"])
def api_match():
    try:
        profile = request.get_json(silent=True)
        if not profile or not isinstance(profile, dict):
            return jsonify({"error": "Profile JSON required"}), 400

        # Save user profile
        user = UserProfile(profile=profile)
        db.session.add(user)
        db.session.commit()

        # Call matcher
        results = []
        if MATCHER_TYPE == "python" and match_profile:
            try:
                results = match_profile(profile)
            except Exception as e:
                app.logger.exception("Matcher (python) failed: %s", e)
                return jsonify({"error": "Internal matcher error", "detail": str(e)}), 500
        else:
            # HTTP fallback
            TRY_URL = os.getenv("MATCHER_HTTP_URL", "http://localhost:8000/match")
            try:
                import requests
                resp = requests.post(TRY_URL, json=profile, timeout=15)
                resp.raise_for_status()
                results = resp.json()
            except Exception as e:
                app.logger.exception("Matcher (http) failed: %s", e)
                # As a fallback, return empty results (or stub) but keep user saved
                # You may prefer to return 500 instead.
                return jsonify({"error": "Matcher service unavailable", "detail": str(e)}), 502

        # Validate results format (basic)
        if not isinstance(results, list):
            return jsonify({"error": "Invalid matcher response format"}), 502

        # Persist match results
        saved = []
        for r in results:
            try:
                scheme_id = int(r.get("scheme_id"))
                result_label = r.get("result", "not")
                score = r.get("score")
                reasons = r.get("reasons", {})
                mr = MatchResult(user_id=user.id, scheme_id=scheme_id, result=result_label, score=score, reasons=reasons)
                db.session.add(mr)
                saved.append({
                    "scheme_id": scheme_id,
                    "result": result_label,
                    "score": score,
                    "reasons": reasons
                })
            except Exception:
                app.logger.exception("Failed saving match result: %s", r)
        db.session.commit()

        return jsonify({"user_id": user.id, "results": saved}), 200

    except Exception as e:
        app.logger.exception("Unhandled /api/match error")
        return jsonify({"error": "Internal server error", "detail": str(e)}), 500


# ------------------------------------------------------------------
# Example analytics endpoint: schemes grouped by source_url (demonstration)
# Adapt to your actual 'state' column or extraction
# ------------------------------------------------------------------
@app.route("/api/stats/schemes_by_state", methods=["GET"])
def stats_schemes_by_state():
    try:
        # Example: if schemes store state in raw_html_path or description, you'd adapt this.
        # Here we group by source_url as a placeholder.
        from sqlalchemy import func
        rows = db.session.query(Scheme.source_url, func.count(Scheme.id)).group_by(Scheme.source_url).all()
        return jsonify([{"source_url": r[0], "count": r[1]} for r in rows])
    except Exception as e:
        app.logger.exception("Error computing stats")
        return jsonify({"error": "Failed to compute stats", "detail": str(e)}), 500


# ------------------------------------------------------------------
# ADMIN UI: list unverified/low-confidence rules
# ------------------------------------------------------------------
@app.route("/admin", methods=["GET"])
@require_admin
def admin_index():
    try:
        pending = SchemeRule.query.filter_by(verified=False).order_by(SchemeRule.parser_confidence.asc()).limit(200).all()
        # If template exists, render it
        template_path = os.path.join(app.root_path, "templates", "admin_index.html")
        if os.path.exists(template_path):
            return render_template("admin_index.html", pending=pending)
        # Minimal HTML fallback
        html = "<h1>Admin - Pending Rules</h1><ul>"
        for r in pending:
            html += f"<li>Rule #{r.id} (scheme={r.scheme_id}) - confidence={r.parser_confidence} - <a href='{url_for('admin_verify', rule_id=r.id)}'>verify</a></li>"
        html += "</ul>"
        return html
    except Exception as e:
        app.logger.exception("Admin index error")
        return "Admin error", 500


# ------------------------------------------------------------------
# ADMIN: verify & edit a single rule
# ------------------------------------------------------------------
@app.route("/admin/verify/<int:rule_id>", methods=["GET", "POST"])
@require_admin
def admin_verify(rule_id):
    rule = SchemeRule.query.get_or_404(rule_id)
    if request.method == "POST":
        # admin submitted edited JSON (form or raw)
        raw = request.form.get("rule_json") or request.get_data(as_text=True)
        if not raw:
            return "No rule_json submitted", 400
        try:
            parsed = json.loads(raw)
        except Exception as e:
            return f"Invalid JSON: {e}", 400
        rule.rule_json = parsed
        rule.verified = True
        db.session.commit()
        return redirect(url_for("admin_index"))
    # GET -> render verification page
    template_path = os.path.join(app.root_path, "templates", "admin_verify.html")
    if os.path.exists(template_path):
        return render_template("admin_verify.html", rule=rule)
    # Minimal HTML fallback
    return f"""
    <h2>Verify Rule #{rule.id} (scheme {rule.scheme_id})</h2>
    <h3>Original snippet</h3>
    <pre>{rule.snippet or ''}</pre>
    <h3>Current JSON</h3>
    <form method="post">
      <textarea name="rule_json" style="width:100%;min-height:300px;">{json.dumps(rule.rule_json or {}, indent=2)}</textarea>
      <br><button type="submit">Save & Verify</button>
    </form>
    """


# ------------------------------------------------------------------
# ADMIN API: update rule (JSON)
# ------------------------------------------------------------------
@app.route("/admin/update_rule", methods=["POST"])
@require_admin
def admin_update_rule():
    try:
        payload = request.get_json(force=True)
        rule_id = payload.get("rule_id")
        new_rule = payload.get("rule_json")
        if not rule_id or new_rule is None:
            return jsonify({"error": "rule_id and rule_json required"}), 400
        rule = SchemeRule.query.get_or_404(rule_id)
        rule.rule_json = new_rule
        rule.verified = True
        # optional: update parser_confidence
        if "parser_confidence" in payload:
            try:
                rule.parser_confidence = float(payload["parser_confidence"])
            except Exception:
                pass
        db.session.commit()
        return jsonify({"ok": True, "rule_id": rule.id}), 200
    except Exception as e:
        app.logger.exception("admin_update_rule failed")
        return jsonify({"error": "update failed", "detail": str(e)}), 500


# ------------------------------------------------------------------
# Error handlers (optional niceties)
# ------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_err(e):
    tb = traceback.format_exc()
    app.logger.error("Internal error: %s", tb)
    return jsonify({"error": "Internal server error"}), 500
