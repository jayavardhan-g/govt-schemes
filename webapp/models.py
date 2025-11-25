# models.py

from db import db
from datetime import datetime
import json

class Scheme(db.Model):
    __tablename__ = "schemes"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    # FIX: Added state column, which is used in sample_data.py
    state = db.Column(db.String, nullable=True) 
    # Use db.Text for potentially long descriptions
    description = db.Column(db.Text) 
    source_url = db.Column(db.String)
    last_scraped = db.Column(db.DateTime)
    raw_html_path = db.Column(db.String)

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "description": self.description,
            "state": self.state, # Added to dictionary representation
            "source_url": self.source_url, "last_scraped": self.last_scraped.isoformat() if self.last_scraped else None
        }

class SchemeRule(db.Model):
    __tablename__ = "scheme_rules"
    id = db.Column(db.Integer, primary_key=True)
    scheme_id = db.Column(db.Integer, db.ForeignKey("schemes.id"), nullable=False)
    rule_json = db.Column(db.JSON)
    # Use db.Text for snippets
    snippet = db.Column(db.Text) 
    parser_confidence = db.Column(db.Float, default=0.0)
    verified = db.Column(db.Boolean, default=False)

class UserProfile(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    # Basic account fields for user management
    email = db.Column(db.String, unique=True, nullable=True)
    password_hash = db.Column(db.String, nullable=True)
    name = db.Column(db.String, nullable=True)
    phone = db.Column(db.String, nullable=True)
    # store the submitted profile JSON (demographic/profile info used for matching)
    profile = db.Column(db.JSON)

class MatchResult(db.Model):
    __tablename__ = "matches"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    scheme_id = db.Column(db.Integer, db.ForeignKey("schemes.id"))
    result = db.Column(db.String)    # eligible/maybe/not
    score = db.Column(db.Float)
    reasons = db.Column(db.JSON)
    created = db.Column(db.DateTime, default=datetime.utcnow)