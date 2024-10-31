# Basic imports
from flask import Flask
from flask_session import Session
from binance.client import Client
from binance.exceptions import BinanceAPIException
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
    TEMPLATES_AUTO_RELOAD=True,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024  # 16MB max file size
)

# Initialize session
Session(app)

# Initialize Binance API and config after app creation
# but before routes import to avoid circular imports
try:
    import config
    if hasattr(config, 'webhook_secret'):
        app.config['SECRET_KEY'] = config.webhook_secret
except ImportError:
    logger.warning("Config file not found. Using default configuration.")
except Exception as e:
    logger.error(f"Error loading config: {e}")

# Import routes after app creation
from . import routes

# Register error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# WebSocket support (optional)
try:
    from flask_socketio import SocketIO
    socketio = SocketIO(app)
except ImportError:
    socketio = None
    logger.info("SocketIO not installed. Real-time updates disabled.")

# Context processors
@app.context_processor
def utility_processor():
    def format_price(value):
        try:
            return f"${value:,.2f}"
        except (ValueError, TypeError):
            return value
            
    return dict(format_price=format_price)

# Before request handler
@app.before_request
def before_request():
    if not request.is_secure and app.env != 'development':
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)

# Initialize common variables
app.jinja_env.globals.update(
    app_name="Trading Platform",
    current_year=datetime.now().year
)

# Version info
__version__ = '1.0.0'