# Binance API Configuration
api_key = ''
api_secret = ''

# Admin Credentials
admin_username = 'admin'
admin_password = 'admin'

# Bot Configuration
max_positions = 5
default_leverage = 10
position_size_percent = 1  # Position size as percentage of balance

# Telegram Configuration (Optional)
tg_token = ''
tg_channel = ''

# Trading pairs configuration
trading_pairs = [
    'BTCUSDT',
    'ETHUSDT',
    'BNBUSDT',
    'XRPUSDT',
    'DOGEUSDT'
]

# Risk management
max_daily_trades = 10
max_loss_percentage = 2  # Maximum loss percentage per trade
trailing_stop = False
enable_tp_sl = True  # Enable Take Profit and Stop Loss

# Webhook Security
webhook_secret = 'your_webhook_secret_here'  # Used to verify webhook requests

# Database Configuration
use_database = False  # Set to True if you want to use a database instead of JSON files
database_url = 'sqlite:///trading.db'  # SQLite database path