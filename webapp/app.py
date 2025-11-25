# webapp/app.py

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import json
import os
import traceback
from functools import wraps
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

load_dotenv()

# SQLAlchemy init
from db import init_db, db
# sample_data uses SQLAlchemy
from sample_data import ensure_sample_data
# matcher uses SQLAlchemy
from matcher import evaluate_rules_for_profile, evaluate_rule, evaluate_rule_with_details

# ORM models
from models import Scheme, SchemeRule, UserProfile, MatchResult

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-for-demo")

# Initialize DB (Postgres) via SQLAlchemy and ensure sample data
init_db(app)
with app.app_context():
    # If the database tables are new or were dropped, this will populate them.
    ensure_sample_data()

INDIAN_STATES_AND_UT = [
    "Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa",
    "Gujarat","Haryana","Himachal Pradesh","Jharkhand","Karnataka","Kerala",
    "Madhya Pradesh","Maharashtra","Manipur","Meghalaya","Mizoram","Nagaland",
    "Odisha","Punjab","Rajasthan","Sikkim","Tamil Nadu","Telangana","Tripura",
    "Uttar Pradesh","Uttarakhand","West Bengal",
    "Andaman and Nicobar Islands","Chandigarh","Dadra and Nagar Haveli and Daman and Diu",
    "Delhi","Jammu and Kashmir","Ladakh","Lakshadweep","Puducherry"
]

CASTE_CATEGORIES = [
    "General/Unreserved",
    "Other Backward Classes (OBC)",
    "Scheduled Caste (SC)",
    "Scheduled Tribe (ST)",
    "Economically Weaker Section (EWS)",
    "Other / Prefer not to say"
]

# ---------------- Helpers ----------------

def _to_int_or_none(v):
    try:
        if v is None or v == '': return None
        return int(v)
    except ValueError: return None

def _to_float_or_none(v):
    try:
        if v is None or v == '': return None
        return float(v)
    except ValueError: return None

def extract_profile_from_form(req_form):
    return {
        'age': _to_int_or_none(req_form.get('age')),
        'income': _to_float_or_none(req_form.get('income')),
        'gender': (req_form.get('gender') or None),
        'state': (req_form.get('state') or None),
        'occupation': (req_form.get('occupation') or None),
        'caste': (req_form.get('caste') or None),
        'disability': (req_form.get('disability') or None),
        'household_size': _to_int_or_none(req_form.get('household_size')) or 1
    }

# ---------------- Routes ----------------

@app.route('/')
def index():
    # 1. Check if "Check for another person" was clicked (Manual Mode)
    if request.args.get('mode') == 'manual':
        return render_template('index.html', 
                               states=INDIAN_STATES_AND_UT, 
                               castes=CASTE_CATEGORIES,
                               manual_mode=True)

    user_id = session.get('user_id')
    
    # 2. Logged-in User Logic
    if user_id:
        user = UserProfile.query.get(user_id)
        
        if user and user.profile:
            # Sync the session profile with the DB profile so Details page matches Homepage
            session['profile'] = user.profile 

            results = evaluate_rules_for_profile(user.profile)
            return render_template('results.html', 
                                   results=results, 
                                   profile=user.profile, 
                                   is_dashboard=True)
        else:
            flash("Welcome! Please complete your profile to see eligible schemes.")
            return redirect(url_for('profile'))

    # 3. Guest User (Standard Form)
    return render_template('index.html', states=INDIAN_STATES_AND_UT, castes=CASTE_CATEGORIES)


@app.route('/results')
def results():
    # Retrieve data stored in session by the /match route
    results = session.get('last_results', [])
    profile = session.get('profile', {})
    return render_template('results.html', results=results, profile=profile)


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    # 1. Check if session has a user_id
    if not session.get('user_id'):
        flash('Please login to edit your profile')
        return redirect(url_for('login'))
    
    user = UserProfile.query.get(session['user_id'])
    
    # Handle "Ghost" Sessions (if DB was reset but session remains)
    if user is None:
        session.pop('user_id', None)
        flash('Session expired or invalid. Please login again.')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        new_profile_data = extract_profile_from_form(request.form)
        user.profile = new_profile_data
        db.session.commit()
        flash('Profile updated successfully!')
        return redirect(url_for('index'))
        
    return render_template('profile.html', 
                           user=user, 
                           states=INDIAN_STATES_AND_UT, 
                           castes=CASTE_CATEGORIES)


@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        phone = request.form.get('phone')

        if not email or not password:
            flash('Email and password are required')
            return redirect(url_for('signup'))

        # check if user exists
        existing = UserProfile.query.filter_by(email=email).first()
        if existing:
            flash('An account with that email already exists')
            return redirect(url_for('signup'))

        # Create user
        pw_hash = generate_password_hash(password)
        user = UserProfile(email=email, password_hash=pw_hash, name=name, phone=phone, profile={})
        db.session.add(user)
        db.session.commit()
        
        session['user_id'] = user.id
        
        flash('Account created! Please fill in your details to get started.')
        return redirect(url_for('profile'))
        
    return render_template('signup.html')


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            flash('Email and password required')
            return redirect(url_for('login'))
        user = UserProfile.query.filter_by(email=email).first()
        if not user or not user.password_hash:
            flash('Invalid credentials')
            return redirect(url_for('login'))
        if not check_password_hash(user.password_hash, password):
            flash('Invalid credentials')
            return redirect(url_for('login'))
        session['user_id'] = user.id
        flash('Logged in')
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out')
    return redirect(url_for('index'))


@app.route('/match', methods=['POST'])
def match():
    profile = extract_profile_from_form(request.form)

    # Logic: Only save to DB if user is logged in AND it's not a temporary manual check
    is_manual_check = request.form.get('is_manual_check') == '1'

    if session.get('user_id') and not is_manual_check:
        user = UserProfile.query.get(session['user_id'])
        if user:
            user.profile = profile
            db.session.commit()

    try:
        results = evaluate_rules_for_profile(profile)
    except TypeError:
        # Fallback if signature mismatch
        results = evaluate_rules_for_profile(profile)

    session['last_results'] = results
    session['profile'] = profile
    return redirect(url_for('results'))


@app.route('/scheme/<int:scheme_id>')
def scheme_detail(scheme_id):
    s = Scheme.query.get(scheme_id)
    if not s:
        return 'Scheme not found', 404

    rules = SchemeRule.query.filter_by(scheme_id=scheme_id).all()

    scheme_data = {
        'id': s.id,
        'title': s.title,
        'description': s.description,
        'source_url': s.source_url
    }

    snippet = None
    rule_json = None
    confidence = None
    if rules:
        r0 = rules[0]
        snippet = getattr(r0, 'snippet', '') or ''
        rule_json = r0.rule_json
        confidence = getattr(r0, 'parser_confidence', None)

    # Get the profile from session (synced in index/match)
    profile = session.get('profile')

    evaluation = None
    evaluation_details = []
    try:
        if profile and rules:
            for r in rules:
                rule_obj = r.rule_json
                passed, score, details = evaluate_rule_with_details(rule_obj, profile)
                score_pct = round(float(score) * 100.0, 2)
                
                failed_any = any(d.get('status') is False for d in details)
                skipped_any = any(d.get('skipped') for d in details)
                
                if failed_any:
                    label = 'Not Eligible'
                elif score <= 0:
                    label = 'Not Eligible'
                elif score >= 1.0:
                    label = 'Eligible' if not skipped_any else 'Maybe Eligible'
                else:
                    label = 'Maybe Eligible'

                evaluation_details.append({
                    'rule_id': getattr(r, 'id', None),
                    'score': score_pct,
                    'label': label,
                    'parser_confidence': getattr(r, 'parser_confidence', None),
                    'evaluations': details,
                    'snippet': getattr(r, 'snippet', None)
                })
            
            best = max(evaluation_details, key=lambda x: x['score'])
            evaluation = {
                'label': best['label'],
                'score': best['score'],
                'parser_confidence': best.get('parser_confidence'),
                'snippet': best.get('snippet'),
                'rule_id': best.get('rule_id')
            }
        else:
            evaluation = None
    except Exception as e:
        evaluation = {'error': str(e)}

    skipped_total = 0
    try:
        for det in evaluation_details:
            for ev in det.get('evaluations', []):
                if ev.get('skipped'):
                    skipped_total += 1
    except Exception:
        skipped_total = 0

    pretty_rule = None
    if rule_json:
        try:
            pretty_rule = json.dumps(rule_json, indent=2)
        except:
            pretty_rule = str(rule_json)

    return render_template(
        'scheme.html',
        scheme=scheme_data,
        snippet=snippet,
        rule_json=pretty_rule,
        confidence=confidence,
        evaluation=evaluation,
        evaluation_details=evaluation_details,
        skipped_total=skipped_total
    )

# ---------------- Admin ----------------

@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
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