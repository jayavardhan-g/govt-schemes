"""
Database models for the Government Schemes matching application.
Stores scheme definitions, eligibility rules, user profiles, and matching results.
"""

from db import db
from datetime import datetime
import json

class Scheme(db.Model):
    """Government scheme with metadata and eligibility descriptions."""
    __tablename__ = "schemes"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    # State column for filtering schemes by geographic eligibility
    state = db.Column(db.String, nullable=True) 
    # Long text field for full description
    description = db.Column(db.Text) 
    # URL where scheme information was sourced from
    source_url = db.Column(db.String)
    # Timestamp of last web scrape
    last_scraped = db.Column(db.DateTime)
    # Path to cached HTML file for reference
    raw_html_path = db.Column(db.String)

    def to_dict(self):
        """Convert scheme to JSON-serializable dict."""
        return {
            "id": self.id, 
            "title": self.title, 
            "description": self.description,
            "state": self.state,
            "source_url": self.source_url, 
            "last_scraped": self.last_scraped.isoformat() if self.last_scraped else None
        }

class SchemeRule(db.Model):
    """Parsed eligibility rules in JSON format for a scheme."""
    __tablename__ = "scheme_rules"
    id = db.Column(db.Integer, primary_key=True)
    # Foreign key to parent scheme
    scheme_id = db.Column(db.Integer, db.ForeignKey("schemes.id"), nullable=False)
    # Rule logic in JSON AST format (e.g., {"all": [...]})
    rule_json = db.Column(db.JSON)
    # Original snippet from HTML for admin reference
    snippet = db.Column(db.Text) 
    # Confidence score from parser (0.0-1.0)
    parser_confidence = db.Column(db.Float, default=0.0)
    # Flag indicating admin has reviewed and approved
    verified = db.Column(db.Boolean, default=False)

class UserProfile(db.Model):
    """User account and demographic profile for matching."""
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    # Account creation timestamp
    created = db.Column(db.DateTime, default=datetime.utcnow)
    # Email for login (must be unique)
    email = db.Column(db.String, unique=True, nullable=True)
    # Hashed password for authentication
    password_hash = db.Column(db.String, nullable=True)
    # User's display name
    name = db.Column(db.String, nullable=True)
    # Contact phone number
    phone = db.Column(db.String, nullable=True)
    # JSON containing demographic data used for matching (age, income, state, etc.)
    profile = db.Column(db.JSON)

class MatchResult(db.Model):
    """Records of scheme eligibility evaluations for users."""
    __tablename__ = "matches"
    id = db.Column(db.Integer, primary_key=True)
    # Reference to user who was evaluated
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    # Reference to scheme being evaluated
    scheme_id = db.Column(db.Integer, db.ForeignKey("schemes.id"))
    # Result label (eligible/maybe/not_eligible)
    result = db.Column(db.String)
    # Score from 0 to 1 (higher = better match)
    score = db.Column(db.Float)
    # Detailed explanation of eligibility determination
    reasons = db.Column(db.JSON)
    # When this evaluation was performed
    created = db.Column(db.DateTime, default=datetime.utcnow)