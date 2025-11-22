# webapp/app.py
# Uploaded image path (for your reference): /mnt/data/8fa00f43-dcce-414e-a4ae-6ad9bdb10409.png

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import json
import os
from dotenv import load_dotenv

load_dotenv()

# SQLAlchemy init
from db import init_db, db
# sample_data now uses SQLAlchemy
from sample_data import ensure_sample_data
# matcher uses SQLAlchemy (evaluate_rules_for_profile(profile) and evaluate_rule(rule, profile))
from matcher import evaluate_rules_for_profile, evaluate_rule

# ORM models
from models import Scheme, SchemeRule, UserProfile, MatchResult

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-for-demo")

# Initialize DB (Postgres) via SQLAlchemy and ensure sample data
init_db(app)
with app.app_context():
    ensure_sample_data()


# ---------------- Public routes ----------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/match', methods=['POST'])
def match():
    # Build profile from form fields
    profile = {
        'age': int(request.form.get('age') or 0),
        'income': float(request.form.get('income') or 0),
        'gender': request.form.get('gender') or '',
        'state': request.form.get('state') or '',
        'occupation': request.form.get('occupation') or '',
        'caste': request.form.get('caste') or '',
        'disability': request.form.get('disability') or 'no',
        'household_size': int(request.form.get('household_size') or 1)
    }

    # call matcher which now expects (profile) and returns list of dicts
    try:
        results = evaluate_rules_for_profile(profile)
    except TypeError:
        # fallback if matcher signature is different
        results = evaluate_rules_for_profile(profile)

    # store in session briefly to show results page
    session['last_results'] = results
    session['profile'] = profile
    return redirect(url_for('results'))

@app.route('/results')
def results():
    results = session.get('last_results', [])
    profile = session.get('profile', {})
    return render_template('results.html', results=results, profile=profile)

@app.route('/scheme/<int:scheme_id>')
def scheme_detail(scheme_id):
    # Use ORM to fetch scheme and its rule (first rule)
    s = Scheme.query.get(scheme_id)
    if not s:
        return 'Scheme not found', 404

    r_obj = SchemeRule.query.filter_by(scheme_id=scheme_id).first()
    rule_json = r_obj.rule_json if r_obj else None
    snippet = r_obj.snippet if r_obj else ''
    confidence = r_obj.parser_confidence if r_obj else None

    profile = session.get('profile')
    evaluation = None
    if profile and rule_json:
        try:
            # rule_json may already be a dict (db JSON) or a string
            rule_obj = rule_json if isinstance(rule_json, dict) else json.loads(rule_json)
            ok = evaluate_rule(rule_obj, profile)
            evaluation = { 'eligible': ok }
        except Exception as e:
            evaluation = { 'error': str(e) }

    # Ensure rule_json is a pretty string for the template
    pretty_rule = json.dumps(rule_json, indent=2) if rule_json else None

    scheme_data = {
        'id': s.id,
        'title': s.title,
        'description': s.description,
        'source_url': s.source_url
    }
    return render_template('scheme.html', scheme=scheme_data, snippet=snippet, rule_json=pretty_rule, confidence=confidence, evaluation=evaluation)


# ---------------- Admin ----------------
@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # simple check; consider env vars or real auth in production
        if username == os.getenv("ADMIN_USER", "admin") and password == os.getenv("ADMIN_PASS", "password"):
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    # Left join Scheme -> SchemeRule using ORM
    rows = db.session.query(Scheme, SchemeRule).outerjoin(SchemeRule, Scheme.id==SchemeRule.scheme_id).all()
    schemes = []
    for scheme, rule in rows:
        schemes.append({
            'id': scheme.id,
            'title': scheme.title,
            'confidence': rule.parser_confidence if rule else None,
            'has_rule': bool(rule)
        })
    return render_template('admin_dashboard.html', schemes=schemes)

@app.route('/admin/verify/<int:scheme_id>', methods=['GET','POST'])
def admin_verify(scheme_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    s = Scheme.query.get(scheme_id)
    if not s:
        return 'Scheme not found', 404

    if request.method == 'POST':
        rule_json = request.form.get('rule_json')
        snippet = request.form.get('snippet')
        try:
            # Validate JSON; convert to python dict
            parsed = json.loads(rule_json)
        except Exception as e:
            flash('Invalid JSON: ' + str(e))
            return redirect(url_for('admin_verify', scheme_id=scheme_id))

        existing = SchemeRule.query.filter_by(scheme_id=scheme_id).first()
        if existing:
            existing.rule_json = parsed
            existing.snippet = snippet
            existing.parser_confidence = 1.0
            existing.verified = True
        else:
            newr = SchemeRule(scheme_id=scheme_id, rule_json=parsed, snippet=snippet, parser_confidence=1.0, verified=True)
            db.session.add(newr)
        db.session.commit()
        flash('Saved')
        return redirect(url_for('admin_dashboard'))
    else:
        r = SchemeRule.query.filter_by(scheme_id=scheme_id).first()
        rule_json = json.dumps(r.rule_json, indent=2) if r and r.rule_json else json.dumps({'all': []}, indent=2)
        snippet = r.snippet if r else 'No snippet available (dummy data)'
        return render_template('admin_verify.html', scheme={'id': s.id, 'title': s.title}, rule_json=rule_json, snippet=snippet)


# ---------------- Analytics APIs ----------------
@app.route('/api/stats/schemes_by_state')
def stats_schemes_by_state():
    try:
        from sqlalchemy import func
        rows = db.session.query(Scheme.state, func.count(Scheme.id)).group_by(Scheme.state).all()
        return jsonify([{ 'state': r[0] or 'Unknown', 'count': r[1]} for r in rows])
    except Exception as e:
        app.logger.exception("Error computing stats")
        return jsonify({"error": "Failed to compute stats", "detail": str(e)}), 500

@app.route('/api/scheme/<int:scheme_id>')
def api_scheme(scheme_id):
    s = Scheme.query.get(scheme_id)
    if not s:
        return jsonify({'error':'not found'}), 404
    r = SchemeRule.query.filter_by(scheme_id=scheme_id).first()
    return jsonify({
        'id': s.id,
        'title': s.title,
        'description': s.description,
        'source_url': s.source_url,
        'rule': r.rule_json if r else None,
        'snippet': r.snippet if r else None,
        'confidence': r.parser_confidence if r else None
    })


# ---------------- Run ----------------
if __name__ == '__main__':
    # optional: show SQL for debugging
    # app.config['SQLALCHEMY_ECHO'] = True
    app.run(debug=True)
