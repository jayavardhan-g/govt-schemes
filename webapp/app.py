from flask import Flask
from db import init_db
import models   # <<< THIS IS IMPORTANT

app = Flask(__name__)

# Connect database
init_db(app)

@app.route("/")
def home():
    return "Postgres connected successfully!"

if __name__ == "__main__":
    app.run(debug=True)
