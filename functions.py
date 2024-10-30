from flask import request
import json
from binance.client import Client
from binance.exceptions import BinanceAPIException
import config
import datetime
import hmac
import hashlib
from typing import Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Binance client
client = None

def initialize_binance():
    """Initialize Binance client with API credentials"""
    global client
    try:
        client = Client(config.api_key, config.api_secret)
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Binance client: {e}")
        return False

def verify_webhook_signature(request_data: str, signature: str) -> bool:
    """Verify webhook request signature"""
    computed_signature = hmac.new(
        config.webhook_secret.encode(),
        request_data.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed_signature, signature)

def get_account_balance() -> Dict:
    """Get account balance information"""
    try:
        account = client.futures_account()
        balance = {
            'total_balance': float(account['totalWalletBalance']),
            'available_balance': float(account['availableBalance']),
            'position_margin': float(account['totalPositionInitialMargin']),
            'unrealized_pnl': float(account['totalUnrealizedProfit'])
        }
        return balance
    except BinanceAPIException as e:
        logger.error(f"Failed to get account balance: {e}")
        return {}

def place_order(action: str, symbol: str, quantity: float, price: float = None, 
                tp_price: float = None, sl_price: float = None) -> Dict:
    """Place a new order on Binance Futures"""
    try:
        # Set order type based on price parameter
        order_type = Client.ORDER_TYPE_MARKET if price is None else Client.ORDER_TYPE_LIMIT
        side = Client.SIDE_BUY if action.upper() == "BUY" else Client.SIDE_SELL

        # Prepare order parameters
        order_params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }

        if price is not None:
            order_params["price"] = price
            order_params["timeInForce"] = Client.TIME_IN_FORCE_GTC

        # Place the main order
        order = client.futures_create_order(**order_params)

        # Place take profit and stop loss if enabled
        if config.enable_tp_sl and tp_price and sl_price:
            if side == Client.SIDE_BUY:
                # Place take profit
                client.futures_create_order(
                    symbol=symbol,
                    side=Client.SIDE_SELL,
                    type=Client.ORDER_TYPE_TAKE_PROFIT_MARKET,
                    stopPrice=tp_price,
                    closePosition=True
                )
                # Place stop loss
                client.futures_create_order(
                    symbol=symbol,
                    side=Client.SIDE_SELL,
                    type=Client.ORDER_TYPE_STOP_MARKET,
                    stopPrice=sl_price,
                    closePosition=True
                )
            else:
                # Place take profit
                client.futures_create_order(
                    symbol=symbol,
                    side=Client.SIDE_BUY,
                    type=Client.ORDER_TYPE_TAKE_PROFIT_MARKET,
                    stopPrice=tp_price,
                    closePosition=True
                )
                # Place stop loss
                client.futures_create_order(
                    symbol=symbol,
                    side=Client.SIDE_BUY,
                    type=Client.ORDER_TYPE_STOP_MARKET,
                    stopPrice=sl_price,
                    closePosition=True
                )

        return order
    except BinanceAPIException as e:
        logger.error(f"Failed to place order: {e}")
        return None

def close_position(symbol: str) -> bool:
    """Close an open position"""
    try:
        position = client.futures_position_information(symbol=symbol)[0]
        if float(position['positionAmt']) != 0:
            side = Client.SIDE_SELL if float(position['positionAmt']) > 0 else Client.SIDE_BUY
            client.futures_create_order(
                symbol=symbol,
                side=side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=abs(float(position['positionAmt'])),
                reduceOnly=True
            )
            return True
    except BinanceAPIException as e:
        logger.error(f"Failed to close position: {e}")
    return False

def get_positions() -> List[Dict]:
    """Get all open positions"""
    try:
        positions = client.futures_position_information()
        return [pos for pos in positions if float(pos['positionAmt']) != 0]
    except BinanceAPIException as e:
        logger.error(f"Failed to get positions: {e}")
        return []

def set_leverage(symbol: str, leverage: int) -> bool:
    """Set leverage for a trading pair"""
    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
        return True
    except BinanceAPIException as e:
        logger.error(f"Failed to set leverage: {e}")
        return False

def write_trade_data(order_data: Dict) -> None:
    """Write trade data to JSON file"""
    try:
        with open('trades.json', 'r') as f:
            trades = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        trades = []
    
    trade_info = {
        'order_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'order_id': order_data.get('orderId'),
        'symbol': order_data.get('symbol'),
        'action': order_data.get('side'),
        'price': order_data.get('price'),
        'qty': order_data.get('origQty'),
        'status': order_data.get('status')
    }
    
    trades.append(trade_info)
    
    with open('trades.json', 'w') as f:
        json.dump(trades, f, indent=4)

def write_signal_data(signal_data: Dict) -> None:
    """Write signal data to JSON file"""
    try:
        with open('signals.json', 'r') as f:
            signals = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        signals = []
    
    signal_info = {
        'signal_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'symbol': signal_data.get('symbol'),
        'action': signal_data.get('action'),
        'entry': signal_data.get('price'),
        'tp': signal_data.get('tp'),
        'sl': signal_data.get('sl'),
        'qty': signal_data.get('qty')
    }
    
    signals.append(signal_info)
    
    with open('signals.json', 'w') as f:
        json.dump(signals, f, indent=4)

# Authentication helper functions
def read_auth_file(filename: str) -> str:
    """Read authentication file content"""
    try:
        with open(filename, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return ''

def write_auth_file(filename: str, content: str) -> None:
    """Write content to authentication file"""
    with open(filename, 'w') as f:
        f.write(content)

def ip_address() -> str:
    """Get client IP address"""
    if 'X-Forwarded-For' in request.headers:
        return request.headers['X-Forwarded-For'].split(',')[0].strip()
    return request.remote_addr