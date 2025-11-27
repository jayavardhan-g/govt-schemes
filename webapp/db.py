"""
Database initialization and configuration module.
Sets up SQLAlchemy connection to PostgreSQL with connection pooling.
"""

import os
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

# Create SQLAlchemy instance (will be initialized with Flask app in init_db)
db = SQLAlchemy()

def init_db(app):
    """
    Configure and initialize the database connection.
    Reads DATABASE_URL from environment and creates tables if needed.
    """
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set in environment (.env)")

    # Configure Flask-SQLAlchemy
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # # DEBUG: Uncomment to see SQL statements
    # app.config["SQLALCHEMY_ECHO"] = True

    # Bind SQLAlchemy instance to Flask app
    db.init_app(app)

    # Create tables based on model definitions from models.py
    with app.app_context():
        # # DEBUG: Log table creation
        # print("[DEBUG] Creating database tables if they don't exist...")
        db.create_all()
        # # DEBUG: Confirm tables created
        # print("[DEBUG] Database initialization complete")
