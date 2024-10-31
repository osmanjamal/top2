from flask import (
    render_template, request, redirect, 
    url_for, flash, jsonify, session
)
from functools import wraps
from binance.client import Client
from binance.exceptions import BinanceAPIException
import app.config as config
import json
from datetime import datetime, timedelta
import pandas as pd
from app.functions import BinanceAPI

# ======= Authentication Decorator =======
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ======= Authentication Routes =======
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == config.admin_username and password == config.admin_password:
            session['user_id'] = username
            session['account_type'] = 'admin'
            flash('Successfully logged in!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Successfully logged out.', 'success')
    return redirect(url_for('login'))

# ======= Main Routes =======
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        binance = BinanceAPI()
        
        # Get account information
        account_info = binance.get_account_info()
        
        # Get active positions
        positions = binance.get_positions()
        
        # Get recent trades
        try:
            with open('trades.json', 'r') as f:
                recent_trades = json.load(f)
                # Get last 10 trades
                recent_trades = recent_trades[-10:]
        except (FileNotFoundError, json.JSONDecodeError):
            recent_trades = []
        
        # Get active signals
        try:
            with open('signals.json', 'r') as f:
                signals = json.load(f)
                active_signals = [s for s in signals if s.get('status') == 'active']
        except (FileNotFoundError, json.JSONDecodeError):
            active_signals = []

        # Calculate daily stats
        daily_stats = calculate_daily_stats(recent_trades)
        
        return render_template('dashboard.html',
            account=account_info,
            positions=positions,
            recent_trades=recent_trades,
            active_signals=active_signals,
            daily_stats=daily_stats
        )
        
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return render_template('dashboard.html', error=str(e))

@app.route('/trading')
@login_required
def trading():
    try:
        binance = BinanceAPI()
        
        # Get trading pairs
        trading_pairs = config.trading_pairs
        
        # Get current positions
        positions = binance.get_positions()
        
        # Get account leverage settings
        leverage_settings = {
            pair: binance.client.futures_leverage_bracket(symbol=pair)[0]
            for pair in trading_pairs
        }
        
        return render_template('trading.html',
            trading_pairs=trading_pairs,
            positions=positions,
            leverage_settings=leverage_settings
        )
        
    except Exception as e:
        flash(f'Error loading trading page: {str(e)}', 'error')
        return render_template('trading.html', error=str(e))

@app.route('/positions')
@login_required
def positions():
    try:
        binance = BinanceAPI()
        positions = binance.get_positions()
        
        # Calculate additional metrics for each position
        for position in positions:
            position['roe'] = calculate_roe(position)
            position['duration'] = calculate_position_duration(position)
            position['risk_ratio'] = calculate_risk_ratio(position)
        
        return render_template('positions.html', positions=positions)
        
    except Exception as e:
        flash(f'Error loading positions: {str(e)}', 'error')
        return render_template('positions.html', error=str(e))

# ======= Helper Functions =======
def calculate_daily_stats(trades):
    """Calculate daily trading statistics"""
    today = datetime.now().date()
    today_trades = [
        trade for trade in trades
        if datetime.strptime(trade['order_time'], '%Y-%m-%d %H:%M:%S').date() == today
    ]
    
    return {
        'total_trades': len(today_trades),
        'winning_trades': len([t for t in today_trades if float(t.get('pnl', 0)) > 0]),
        'total_pnl': sum(float(t.get('pnl', 0)) for t in today_trades),
        'biggest_win': max((float(t.get('pnl', 0)) for t in today_trades), default=0),
        'biggest_loss': min((float(t.get('pnl', 0)) for t in today_trades), default=0)
    }

def calculate_roe(position):
    """Calculate Return on Equity for a position"""
    initial_margin = float(position['positionInitialMargin'])
    unrealized_pnl = float(position['unrealizedProfit'])
    return (unrealized_pnl / initial_margin * 100) if initial_margin != 0 else 0

def calculate_position_duration(position):
    """Calculate how long a position has been open"""
    entry_time = datetime.fromtimestamp(position['updateTime'] / 1000)
    duration = datetime.now() - entry_time
    return format_duration(duration)

def calculate_risk_ratio(position):
    """Calculate risk/reward ratio for a position"""
    entry_price = float(position['entryPrice'])
    mark_price = float(position['markPrice'])
    stop_loss = float(position.get('stopLoss', 0))
    take_profit = float(position.get('takeProfit', 0))
    
    if stop_loss != 0 and take_profit != 0:
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        return reward / risk if risk != 0 else 0
    return None

def format_duration(duration):
    """Format timedelta into human readable string"""
    days = duration.days
    hours = duration.seconds // 3600
    minutes = (duration.seconds % 3600) // 60
    
    if days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"
    

# ======= Signal Routes =======
@app.route('/signals')
@login_required
def signals():
    try:
        # Load signals from file
        with open('signals.json', 'r') as f:
            signals_data = json.load(f)
        
        # Convert to DataFrame for easy manipulation
        df = pd.DataFrame(signals_data)
        if not df.empty:
            df['order_time'] = pd.to_datetime(df['order_time'])
            df = df.sort_values('order_time', ascending=False)
            
            # Calculate success rate
            total_signals = len(df)
            successful_signals = len(df[df['result'].apply(
                lambda x: x.get('pnl_percent', 0) > 0 if x else False
            )])
            success_rate = (successful_signals / total_signals * 100) if total_signals > 0 else 0
            
            # Calculate total PNL
            total_pnl = df['result'].apply(
                lambda x: float(x.get('pnl_usdt', 0)) if x else 0
            ).sum()
        else:
            success_rate = 0
            total_pnl = 0
        
        return render_template('signals.html',
            signals=signals_data,
            success_rate=success_rate,
            total_pnl=total_pnl,
            total_signals=len(signals_data)
        )
        
    except Exception as e:
        flash(f'Error loading signals: {str(e)}', 'error')
        return render_template('signals.html', signals=[])

# ======= History Routes =======
@app.route('/history')
@login_required
def history():
    try:
        # Load trade history
        with open('trades.json', 'r') as f:
            trades = json.load(f)
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(trades)
        df['order_time'] = pd.to_datetime(df['order_time'])
        df = df.sort_values('order_time', ascending=False)
        
        # Calculate statistics
        stats = {
            'total_trades': len(df),
            'winning_trades': len(df[df['pnl'] > 0]),
            'total_pnl': df['pnl'].sum(),
            'average_pnl': df['pnl'].mean(),
            'largest_win': df['pnl'].max(),
            'largest_loss': df['pnl'].min(),
            'win_rate': (len(df[df['pnl'] > 0]) / len(df) * 100) if len(df) > 0 else 0
        }
        
        return render_template('history.html', trades=trades, stats=stats)
        
    except Exception as e:
        flash(f'Error loading history: {str(e)}', 'error')
        return render_template('history.html', trades=[], stats={})

# ======= Settings Routes =======
@app.route('/api-settings', methods=['GET', 'POST'])
@login_required
def api_settings():
    if request.method == 'POST':
        api_key = request.form.get('api_key')
        api_secret = request.form.get('api_secret')
        
        if api_key and api_secret:
            try:
                # Test API connection
                test_client = Client(api_key, api_secret)
                test_client.get_account()
                
                # Update config file
                update_config('api_key', api_key)
                update_config('api_secret', api_secret)
                
                flash('API credentials updated successfully', 'success')
                return redirect(url_for('api_settings'))
                
            except BinanceAPIException as e:
                flash(f'Invalid API credentials: {str(e)}', 'error')
            except Exception as e:
                flash(f'Error updating API credentials: {str(e)}', 'error')
    
    # Mask API credentials for display
    masked_key = f"{'*' * 16}{config.api_key[-4:]}" if config.api_key else None
    connection_status = test_api_connection()
    
    return render_template('api_settings.html',
        api_key=masked_key,
        connection_status=connection_status
    )

@app.route('/preferences', methods=['GET', 'POST'])
@login_required
def preferences():
    if request.method == 'POST':
        try:
            # Update trading settings
            update_config('position_size_percent', float(request.form.get('position_size', 1)))
            update_config('default_leverage', int(request.form.get('leverage', 10)))
            update_config('enable_tp_sl', request.form.get('enable_tp_sl') == 'on')
            update_config('max_daily_trades', int(request.form.get('max_daily_trades', 10)))
            update_config('max_loss_percentage', float(request.form.get('max_loss', 2)))
            
            # Update trading pairs
            pairs = request.form.getlist('trading_pairs')
            if pairs:
                update_config('trading_pairs', pairs)
            
            flash('Settings updated successfully', 'success')
            
        except Exception as e:
            flash(f'Error updating settings: {str(e)}', 'error')
            
        return redirect(url_for('preferences'))
    
    return render_template('preferences.html',
        settings=config,
        available_pairs=get_available_pairs()
    )

# ======= API Routes =======
@app.route('/api/nav_stats')
@login_required
def nav_stats():
    try:
        binance = BinanceAPI()
        account = binance.get_account_info()
        positions = binance.get_positions()
        
        # Get signals count
        try:
            with open('signals.json', 'r') as f:
                signals = json.load(f)
                active_signals = len([s for s in signals if s.get('status') == 'active'])
        except:
            active_signals = 0
        
        return jsonify({
            'total_balance': account['total_balance'],
            'daily_pnl': account['unrealized_pnl'],
            'active_signals': active_signals,
            'active_positions': len(positions)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/place_order', methods=['POST'])
@login_required
def api_place_order():
    try:
        data = request.json
        required_fields = ['symbol', 'side', 'quantity']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        binance = BinanceAPI()
        order = binance.place_order(
            symbol=data['symbol'],
            side=data['side'],
            quantity=float(data['quantity']),
            price=data.get('price'),
            stop_loss=data.get('stop_loss'),
            take_profit=data.get('take_profit')
        )
        
        if order:
            return jsonify({
                'message': 'Order placed successfully',
                'order': order
            }), 200
        return jsonify({'error': 'Failed to place order'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/close_position', methods=['POST'])
@login_required
def api_close_position():
    try:
        data = request.json
        if not data.get('symbol'):
            return jsonify({'error': 'Symbol is required'}), 400
        
        binance = BinanceAPI()
        result = binance.close_position(data['symbol'])
        
        if result:
            return jsonify({'message': f'Position closed for {data["symbol"]}'}), 200
        return jsonify({'error': 'No position found or error closing position'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ======= Helper Functions =======
def update_config(key, value):
    """Update configuration file with new values"""
    with open('config.py', 'r') as f:
        lines = f.readlines()
    
    with open('config.py', 'w') as f:
        for line in lines:
            if line.startswith(f'{key} = '):
                f.write(f'{key} = {repr(value)}\n')
            else:
                f.write(line)

def test_api_connection():
    """Test Binance API connection"""
    try:
        binance = BinanceAPI()
        binance.client.get_account()
        return 'Connected'
    except:
        return 'Not Connected'

def get_available_pairs():
    """Get available trading pairs from Binance"""
    try:
        binance = BinanceAPI()
        exchange_info = binance.client.get_exchange_info()
        return [s['symbol'] for s in exchange_info['symbols'] if s['symbol'].endswith('USDT')]
    except:
        return []

# ======= Error Handlers =======
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500    