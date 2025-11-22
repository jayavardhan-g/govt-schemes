# webapp/db.py
import os
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()

def init_db(app):
    """
    Initialize SQLAlchemy with Flask app. Uses DATABASE_URL from .env.
    """
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set in environment (.env)")

    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    # create tables if they don't exist (uses models.py metadata)
    with app.app_context():
        db.create_all()
