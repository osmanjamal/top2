from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
from binance.client import Client
from binance.exceptions import BinanceAPIException
import json
import config
import logging
from functions import (
    initialize_binance, verify_webhook_signature, get_account_balance,
    place_order, close_position, get_positions, write_trade_data,
    write_signal_data, read_auth_file, write_auth_file, ip_address
)
import pandas as pd
from datetime import datetime
import threading
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = config.webhook_secret

# Initialize Binance client
initialize_binance()

def validate_session():
    """Validate user session"""
    auth_session = read_auth_file('auth.txt')
    ip_session = read_auth_file('ip_address.txt')
    current_ip = ip_address()
    return auth_session == 'authenticated' and ip_session == current_ip

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == config.admin_username and password == config.admin_password:
            write_auth_file('auth.txt', 'authenticated')
            write_auth_file('ip_address.txt', ip_address())
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Handle user logout"""
    write_auth_file('auth.txt', 'unauthenticated')
    write_auth_file('ip_address.txt', '')
    return redirect(url_for('login'))

@app.route('/')
def index():
    """Root route redirects to dashboard if authenticated"""
    if validate_session():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    """Main dashboard view"""
    if not validate_session():
        return redirect(url_for('login'))
    
    try:
        # Get account information
        account_info = get_account_balance()
        
        # Get open positions
        positions = get_positions()
        
        # Process positions data
        positions_data = []
        for pos in positions:
            pnl_percent = (float(pos['unrealizedProfit']) / float(pos['positionInitialMargin'])) * 100
            positions_data.append({
                'symbol': pos['symbol'],
                'side': 'Long' if float(pos['positionAmt']) > 0 else 'Short',
                'size': abs(float(pos['positionAmt'])),
                'entry_price': float(pos['entryPrice']),
                'mark_price': float(pos['markPrice']),
                'leverage': pos['leverage'],
                'pnl': float(pos['unrealizedProfit']),
                'pnl_percent': round(pnl_percent, 2),
                'margin': float(pos['positionInitialMargin'])
            })

        # Get recent trades from JSON file
        try:
            with open('trades.json', 'r') as f:
                recent_trades = json.load(f)[-5:]  # Get last 5 trades
        except (FileNotFoundError, json.JSONDecodeError):
            recent_trades = []

        return render_template('dashboard.html',
                             account=account_info,
                             positions=positions_data,
                             recent_trades=recent_trades,
                             trading_pairs=config.trading_pairs)

    except BinanceAPIException as e:
        logger.error(f"Binance API error: {e}")
        flash(f"Error fetching data: {e}", 'error')
        return render_template('dashboard.html', error=str(e))

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        flash(f"Unexpected error: {e}", 'error')
        return render_template('dashboard.html', error=str(e))

# Real-time price update endpoint
@app.route('/get_prices')
def get_prices():
    """Get current prices for trading pairs"""
    if not validate_session():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        prices = Client().get_symbol_ticker()
        filtered_prices = {p['symbol']: p['price'] for p in prices if p['symbol'] in config.trading_pairs}
        return jsonify(filtered_prices)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Start background tasks
def background_tasks():
    """Background tasks for updating data"""
    while True:
        try:
            # Update positions and account data periodically
            # This data will be cached and used by the frontend
            if hasattr(app, 'positions'):
                app.positions = get_positions()
            if hasattr(app, 'account_info'):
                app.account_info = get_account_balance()
        except Exception as e:
            logger.error(f"Background task error: {e}")
        time.sleep(5)  # Update every 5 seconds

# Start background thread
background_thread = threading.Thread(target=background_tasks, daemon=True)
background_thread.start()

# Signal and Trade Management Routes
@app.route('/signals')
def signals():
    """Display trading signals"""
    if not validate_session():
        return redirect(url_for('login'))
    
    try:
        with open('signals.json', 'r') as f:
            signals_data = json.load(f)
        
        # Convert to DataFrame for easy display
        df = pd.DataFrame(signals_data)
        if not df.empty:
            df = df.sort_values(by='signal_time', ascending=False)
        
        return render_template('signals.html', 
                             signals=signals_data, 
                             tables=[df.to_html(classes='data', index=False)],
                             titles=df.columns.values if not df.empty else [])
    
    except FileNotFoundError:
        return render_template('signals.html', signals=[], tables=[], titles=[])
    except Exception as e:
        flash(f"Error loading signals: {e}", 'error')
        return render_template('signals.html', signals=[], tables=[], titles=[])

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook signals"""
    try:
        # Verify webhook signature if provided
        if 'X-Webhook-Signature' in request.headers:
            if not verify_webhook_signature(request.data.decode(), 
                                         request.headers['X-Webhook-Signature']):
                return jsonify({'error': 'Invalid signature'}), 401

        data = request.json
        required_fields = ['symbol', 'action', 'price']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400

        # Validate symbol
        if data['symbol'] not in config.trading_pairs:
            return jsonify({'error': 'Invalid trading pair'}), 400

        # Process the signal
        try:
            # Calculate position size
            account = get_account_balance()
            position_size = (account['available_balance'] * 
                           config.position_size_percent / 100)

            # Set leverage
            leverage = data.get('leverage', config.default_leverage)
            set_leverage(data['symbol'], leverage)

            # Calculate TP/SL if provided
            tp_price = None
            sl_price = None
            if 'tp_percent' in data and config.enable_tp_sl:
                tp_distance = float(data['price']) * (float(data['tp_percent']) / 100)
                tp_price = (float(data['price']) + tp_distance if data['action'].upper() == 'BUY'
                          else float(data['price']) - tp_distance)
            
            if 'sl_percent' in data and config.enable_tp_sl:
                sl_distance = float(data['price']) * (float(data['sl_percent']) / 100)
                sl_price = (float(data['price']) - sl_distance if data['action'].upper() == 'BUY'
                          else float(data['price']) + sl_distance)

            # Place the order
            order = place_order(
                action=data['action'],
                symbol=data['symbol'],
                quantity=position_size,
                price=float(data['price']),
                tp_price=tp_price,
                sl_price=sl_price
            )

            if order:
                # Record the signal and trade
                write_signal_data(data)
                write_trade_data(order)
                return jsonify({'message': 'Order executed successfully', 
                              'order_id': order['orderId']}), 200
            else:
                return jsonify({'error': 'Failed to place order'}), 500

        except BinanceAPIException as e:
            logger.error(f"Binance API error: {e}")
            return jsonify({'error': str(e)}), 500
        
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return jsonify({'error': str(e)}), 500

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'error': str(e)}), 500
    


# API Settings and Management Routes
@app.route('/api-connection', methods=['GET', 'POST'])
def api_settings():
    """Handle API connection settings"""
    if not validate_session():
        return redirect(url_for('login'))

    if request.method == 'POST':
        api_key = request.form.get('api_key')
        api_secret = request.form.get('api_secret')

        if api_key and api_secret:
            try:
                # Test connection with new credentials
                test_client = Client(api_key, api_secret)
                test_client.get_account()

                # Update config if test successful
                with open('config.py', 'r') as file:
                    lines = file.readlines()

                with open('config.py', 'w') as file:
                    for line in lines:
                        if line.startswith('api_key'):
                            file.write(f"api_key = '{api_key}'\n")
                        elif line.startswith('api_secret'):
                            file.write(f"api_secret = '{api_secret}'\n")
                        else:
                            file.write(line)

                flash('API credentials updated successfully', 'success')
                # Reinitialize client with new credentials
                initialize_binance()
                
            except BinanceAPIException as e:
                flash(f'Invalid API credentials: {str(e)}', 'error')
            except Exception as e:
                flash(f'Error updating API credentials: {str(e)}', 'error')

        return redirect(url_for('api_settings'))

    # Display current API settings (masked)
    masked_key = '************' + config.api_key[-4:] if config.api_key else None
    connection_status = 'Connected' if initialize_binance() else 'Not Connected'

    return render_template('api-connection.html', 
                         api_key=masked_key,
                         connection_status=connection_status)

@app.route('/settings', methods=['GET', 'POST'])
def trading_settings():
    """Handle trading settings"""
    if not validate_session():
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            # Update trading settings
            settings = {
                'position_size_percent': float(request.form.get('position_size', 1)),
                'default_leverage': int(request.form.get('leverage', 10)),
                'enable_tp_sl': request.form.get('enable_tp_sl') == 'on',
                'max_daily_trades': int(request.form.get('max_daily_trades', 10)),
                'max_loss_percentage': float(request.form.get('max_loss', 2))
            }

            # Update config file
            with open('config.py', 'r') as file:
                lines = file.readlines()

            with open('config.py', 'w') as file:
                for line in lines:
                    for key, value in settings.items():
                        if line.startswith(key):
                            file.write(f"{key} = {value}\n")
                            break
                    else:
                        file.write(line)

            flash('Trading settings updated successfully', 'success')

        except Exception as e:
            flash(f'Error updating settings: {str(e)}', 'error')

        return redirect(url_for('trading_settings'))

    # Get current settings
    current_settings = {
        'position_size_percent': config.position_size_percent,
        'default_leverage': config.default_leverage,
        'enable_tp_sl': config.enable_tp_sl,
        'max_daily_trades': config.max_daily_trades,
        'max_loss_percentage': config.max_loss_percentage,
        'trading_pairs': config.trading_pairs
    }

    return render_template('settings.html', settings=current_settings)

@app.route('/update_trading_pairs', methods=['POST'])
def update_trading_pairs():
    """Update available trading pairs"""
    if not validate_session():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        pairs = request.json.get('pairs', [])
        # Validate pairs exist on Binance
        exchange_info = Client().get_exchange_info()
        valid_symbols = {s['symbol'] for s in exchange_info['symbols']}
        
        valid_pairs = [pair for pair in pairs if pair in valid_symbols]

        # Update config file
        with open('config.py', 'r') as file:
            lines = file.readlines()

        with open('config.py', 'w') as file:
            for line in lines:
                if line.startswith('trading_pairs'):
                    file.write(f"trading_pairs = {valid_pairs}\n")
                else:
                    file.write(line)

        return jsonify({'message': 'Trading pairs updated successfully',
                       'pairs': valid_pairs}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
