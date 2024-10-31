from flask import request
from binance.client import Client
from binance.exceptions import BinanceAPIException
import json
import hmac
import hashlib
from datetime import datetime
import logging
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BinanceAPI:
    def __init__(self, api_key=None, api_secret=None):
        self.api_key = api_key or config.api_key
        self.api_secret = api_secret or config.api_secret
        self.client = None
        self.initialize()

    def initialize(self):
        try:
            self.client = Client(self.api_key, self.api_secret)
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Binance client: {e}")
            return False

    def get_account_balance(self):
        try:
            account = self.client.futures_account()
            return {
                'total_balance': float(account['totalWalletBalance']),
                'unrealized_pnl': float(account['totalUnrealizedProfit']),
                'used_margin': float(account['totalPositionInitialMargin']),
                'free_margin': float(account['availableBalance']),
                'margin_ratio': float(account['totalMarginBalance']),
                'positions': len([p for p in account['positions'] if float(p['positionAmt']) != 0])
            }
        except BinanceAPIException as e:
            logger.error(f"Error getting account info: {e}")
            return None

    def get_positions(self):
        """Get all open positions"""
        try:
            positions = self.client.futures_position_information()
            active_positions = []
            
            for pos in positions:
                if float(pos['positionAmt']) != 0:
                    unrealized_pnl = float(pos['unRealizedProfit'])
                    entry_price = float(pos['entryPrice'])
                    current_price = float(pos['markPrice'])
                    position_size = abs(float(pos['positionAmt']))
                    
                    # Calculate ROE (Return on Equity)
                    margin = float(pos['isolatedWallet']) if pos['isolated'] else float(pos['positionInitialMargin'])
                    roe = (unrealized_pnl / margin * 100) if margin != 0 else 0
                    
                    position_data = {
                        'symbol': pos['symbol'],
                        'size': position_size,
                        'side': 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT',
                        'entry_price': entry_price,
                        'mark_price': current_price,
                        'liquidation_price': float(pos['liquidationPrice']),
                        'leverage': int(pos['leverage']),
                        'unrealized_pnl': unrealized_pnl,
                        'roe_percent': round(roe, 2),
                        'margin_type': 'isolated' if pos['isolated'] else 'cross'
                    }
                    active_positions.append(position_data)
            
            return active_positions
        except BinanceAPIException as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def place_order(self, symbol, side, quantity, order_type='MARKET', price=None, 
                   stop_loss=None, take_profit=None):
        """Place a new order"""
        try:
            # Prepare base order parameters
            params = {
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'type': order_type
            }

            # Add price for limit orders
            if order_type == 'LIMIT':
                params['price'] = price
                params['timeInForce'] = 'GTC'

            # Place the main order
            order = self.client.futures_create_order(**params)

            # If stop loss is specified
            if stop_loss:
                sl_side = 'SELL' if side == 'BUY' else 'BUY'
                self.client.futures_create_order(
                    symbol=symbol,
                    side=sl_side,
                    type='STOP_MARKET',
                    stopPrice=stop_loss,
                    closePosition=True,
                    timeInForce='GTC'
                )

            # If take profit is specified
            if take_profit:
                tp_side = 'SELL' if side == 'BUY' else 'BUY'
                self.client.futures_create_order(
                    symbol=symbol,
                    side=tp_side,
                    type='TAKE_PROFIT_MARKET',
                    stopPrice=take_profit,
                    closePosition=True,
                    timeInForce='GTC'
                )

            self._log_trade(order)
            return order
        except BinanceAPIException as e:
            logger.error(f"Error placing order: {e}")
            return None

    def close_position(self, symbol):
        """Close an open position"""
        try:
            position = [p for p in self.get_positions() if p['symbol'] == symbol]
            if position:
                pos = position[0]
                side = 'SELL' if pos['side'] == 'LONG' else 'BUY'
                
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type='MARKET',
                    quantity=pos['size'],
                    reduceOnly=True
                )
                
                self._log_trade(order, is_close=True)
                return order
            return None
        except BinanceAPIException as e:
            logger.error(f"Error closing position: {e}")
            return None

    def set_leverage(self, symbol, leverage):
        """Set leverage for a symbol"""
        try:
            return self.client.futures_change_leverage(
                symbol=symbol,
                leverage=leverage
            )
        except BinanceAPIException as e:
            logger.error(f"Error setting leverage: {e}")
            return None

    def get_market_price(self, symbol):
        """Get current market price for a symbol"""
        try:
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            logger.error(f"Error getting market price: {e}")
            return None

    def _log_trade(self, order, is_close=False):
        """Log trade to JSON file"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            trade_data = {
                'timestamp': timestamp,
                'order_id': order['orderId'],
                'symbol': order['symbol'],
                'side': order['side'],
                'quantity': float(order['origQty']),
                'price': float(order.get('avgPrice', 0)),
                'type': 'CLOSE' if is_close else 'OPEN'
            }
            
            try:
                with open('trades.json', 'r') as f:
                    trades = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                trades = []
            
            trades.append(trade_data)
            
            with open('trades.json', 'w') as f:
                json.dump(trades, f, indent=4)
                
        except Exception as e:
            logger.error(f"Error logging trade: {e}")

def verify_webhook(request_data, signature):
    """Verify webhook signature"""
    expected_signature = hmac.new(
        config.webhook_secret.encode(),
        request_data.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

def process_webhook_data(data):
    """Process incoming webhook data"""
    try:
        binance = BinanceAPI()
        
        # Validate required fields
        required_fields = ['symbol', 'side', 'quantity']
        if not all(field in data for field in required_fields):
            raise ValueError("Missing required fields")
            
        # Process the order
        order = binance.place_order(
            symbol=data['symbol'],
            side=data['side'],
            quantity=float(data['quantity']),
            order_type=data.get('type', 'MARKET'),
            price=data.get('price'),
            stop_loss=data.get('stop_loss'),
            take_profit=data.get('take_profit')
        )
        
        if order:
            return {'status': 'success', 'order_id': order['orderId']}
        return {'status': 'error', 'message': 'Failed to place order'}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {'status': 'error', 'message': str(e)}