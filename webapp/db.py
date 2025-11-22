from flask_sqlalchemy import SQLAlchemy
import os

DATABASE_URL="postgresql://postgres:kali@localhost/gov_schemes"

db = SQLAlchemy()

def init_db(app):
    #DATABASE_URL = os.getenv("DATABASE_URL")
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()