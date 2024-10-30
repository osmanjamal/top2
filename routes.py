from flask import render_template, request, redirect, url_for, flash, jsonify
from binance.client import Client
from binance.exceptions import BinanceAPIException
import json
import config
import pandas as pd
from datetime import datetime
from functions import (
    initialize_binance, get_account_balance, get_positions,
    place_order, close_position, write_trade_data, write_signal_data,
    read_auth_file, write_auth_file, ip_address
)
from main import app

# Authentication middleware
def require_auth(f):
    def wrapper(*args, **kwargs):
        auth_session = read_auth_file('auth.txt')
        ip_session = read_auth_file('ip_address.txt')
        current_ip = ip_address()
        
        if auth_session != 'authenticated' or ip_session != current_ip:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == config.admin_username and password == config.admin_password:
            write_auth_file('auth.txt', 'authenticated')
            write_auth_file('ip_address.txt', ip_address())
            flash('Successfully logged in!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    write_auth_file('auth.txt', 'unauthenticated')
    write_auth_file('ip_address.txt', '')
    flash('Successfully logged out.', 'success')
    return redirect(url_for('login'))

# Main Routes
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@require_auth
def dashboard():
    try:
        # Get account information
        account_info = get_account_balance()
        
        # Get open positions
        positions = get_positions()
        
        # Get recent trades
        try:
            with open('trades.json', 'r') as f:
                recent_trades = json.load(f)[-5:]  # Last 5 trades
        except (FileNotFoundError, json.JSONDecodeError):
            recent_trades = []
            
        return render_template('dashboard.html',
                             account=account_info,
                             positions=positions,
                             recent_trades=recent_trades,
                             trading_pairs=config.trading_pairs)
                             
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('dashboard.html', error=str(e))

@app.route('/signals')
@require_auth
def signals():
    try:
        with open('signals.json', 'r') as f:
            signals_data = json.load(f)
        
        df = pd.DataFrame(signals_data)
        if not df.empty:
            df = df.sort_values(by='signal_time', ascending=False)
            
        return render_template('signals.html',
                             signals=signals_data,
                             tables=[df.to_html(classes='data')],
                             titles=df.columns.values)
    except Exception as e:
        flash(f'Error loading signals: {str(e)}', 'error')
        return render_template('signals.html', signals=[])

@app.route('/api-settings', methods=['GET', 'POST'])
@require_auth
def api_settings():
    if request.method == 'POST':
        api_key = request.form.get('api_key')
        api_secret = request.form.get('api_secret')
        
        if api_key and api_secret:
            try:
                # Test the API credentials
                test_client = Client(api_key, api_secret)
                test_client.get_account()
                
                # Update config if test is successful
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
                
                initialize_binance()  # Reinitialize with new credentials
                flash('API credentials updated successfully', 'success')
                
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
@require_auth
def settings():
    if request.method == 'POST':
        try:
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
            
            flash('Settings updated successfully', 'success')
            
        except Exception as e:
            flash(f'Error updating settings: {str(e)}', 'error')
        
        return redirect(url_for('settings'))
    
    return render_template('settings.html',
                         position_size=config.position_size_percent,
                         leverage=config.default_leverage,
                         enable_tp_sl=config.enable_tp_sl,
                         max_daily_trades=config.max_daily_trades,
                         max_loss=config.max_loss_percentage)

# API Routes
@app.route('/api/close_position', methods=['POST'])
@require_auth
def api_close_position():
    try:
        symbol = request.json.get('symbol')
        if not symbol:
            return jsonify({'error': 'Symbol is required'}), 400
            
        success = close_position(symbol)
        if success:
            return jsonify({'message': f'Position closed for {symbol}'}), 200
        else:
            return jsonify({'error': f'Failed to close position for {symbol}'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/place_order', methods=['POST'])
@require_auth
def api_place_order():
    try:
        data = request.json
        required_fields = ['symbol', 'side', 'quantity']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
            
        order = place_order(
            action=data['side'],
            symbol=data['symbol'],
            quantity=float(data['quantity']),
            price=data.get('price'),
            tp_price=data.get('tp_price'),
            sl_price=data.get('sl_price')
        )
        
        if order:
            write_trade_data(order)
            return jsonify({'message': 'Order placed successfully', 'order': order}), 200
        else:
            return jsonify({'error': 'Failed to place order'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500