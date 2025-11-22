#models.py
from db import db
from datetime import datetime
import json

class Scheme(db.Model):
    __tablename__ = "schemes"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    description = db.Column(db.Text)
    source_url = db.Column(db.String)
    last_scraped = db.Column(db.DateTime)
    raw_html_path = db.Column(db.String)

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "description": self.description,
            "source_url": self.source_url, "last_scraped": self.last_scraped.isoformat() if self.last_scraped else None
        }

class SchemeRule(db.Model):
    __tablename__ = "scheme_rules"
    id = db.Column(db.Integer, primary_key=True)
    scheme_id = db.Column(db.Integer, db.ForeignKey("schemes.id"), nullable=False)
    rule_json = db.Column(db.JSON)
    snippet = db.Column(db.Text)
    parser_confidence = db.Column(db.Float, default=0.0)
    verified = db.Column(db.Boolean, default=False)

class UserProfile(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    profile = db.Column(db.JSON)   # store the submitted profile JSON

class MatchResult(db.Model):
    __tablename__ = "matches"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    scheme_id = db.Column(db.Integer, db.ForeignKey("schemes.id"))
    result = db.Column(db.String)   # eligible/maybe/not
    score = db.Column(db.Float)
    reasons = db.Column(db.JSON)
    created = db.Column(db.DateTime, default=datetime.utcnow)
