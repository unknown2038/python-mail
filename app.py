from flask import Flask, jsonify
from flask_cors import CORS
import config
from database.db import get_db_connection
from src.routes.receive_mails_routes import receive_mail_bp

# Check if the database connection is successful
conn = get_db_connection()
if not conn:
    print("DATABASE CONNECTION FAILED")

# Initialize the Flask app and register the blueprints
app = Flask(__name__)
CORS(app)
app.register_blueprint(receive_mail_bp)

# Define the home route
@app.route("/")
def home():
    return jsonify({"message": "Flask is running"})

# Run the app
if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
