from flask import Flask, render_template
from flask_session import Session
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Basic configuration
app.config.update(
    SECRET_KEY='your-secret-key-here',
    SESSION_TYPE='filesystem',
)

# Initialize session
Session(app)

# أي استيرادات أخرى تأتي بعد تعريف app
from app import routes

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500