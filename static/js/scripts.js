// static/js/main.js

// Global Variables
let activePositions = [];
let priceUpdateInterval;

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize TradingView widget if container exists
    initializeTradingView();
    
    // Start real-time price updates
    startPriceUpdates();
    
    // Initialize event listeners
    initializeEventListeners();
    
    // Update positions data
    updatePositionsData();
});

// TradingView Widget Initialization
function initializeTradingView() {
    const tradingViewContainer = document.getElementById('tradingview_chart');
    if (tradingViewContainer) {
        new TradingView.widget({
            "width": "100%",
            "height": 500,
            "symbol": "BINANCE:BTCUSDT",
            "interval": "D",
            "timezone": "Etc/UTC",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "toolbar_bg": "#1c2c4f",
            "enable_publishing": false,
            "hide_top_toolbar": true,
            "hide_legend": true,
            "save_image": false,
            "container_id": "tradingview_chart"
        });
    }
}

// Real-time price updates
function startPriceUpdates() {
    if (priceUpdateInterval) {
        clearInterval(priceUpdateInterval);
    }
    
    updatePrices();
    priceUpdateInterval = setInterval(updatePrices, 5000);
}

async function updatePrices() {
    try {
        const response = await fetch('/get_prices');
        const prices = await response.json();
        
        Object.entries(prices).forEach(([symbol, price]) => {
            const priceElement = document.querySelector(`[data-price-symbol="${symbol}"]`);
            if (priceElement) {
                const oldPrice = parseFloat(priceElement.dataset.price);
                const newPrice = parseFloat(price);
                
                // Update price with color animation
                priceElement.textContent = parseFloat(price).toFixed(2);
                priceElement.dataset.price = price;
                
                if (oldPrice < newPrice) {
                    priceElement.classList.add('price-up');
                } else if (oldPrice > newPrice) {
                    priceElement.classList.add('price-down');
                }
                
                setTimeout(() => {
                    priceElement.classList.remove('price-up', 'price-down');
                }, 1000);
            }
        });
    } catch (error) {
        console.error('Error updating prices:', error);
    }
}

// Position Management
async function updatePositionsData() {
    try {
        const response = await fetch('/api/positions');
        const positions = await response.json();
        activePositions = positions;
        
        updatePositionsTable();
        updatePositionsSummary();
    } catch (error) {
        console.error('Error updating positions:', error);
    }
}

function updatePositionsTable() {
    const tableBody = document.querySelector('#positions-table tbody');
    if (!tableBody) return;
    
    tableBody.innerHTML = activePositions.map(position => `
        <tr>
            <td>${position.symbol}</td>
            <td class="${position.side.toLowerCase()}">${position.side}</td>
            <td>${parseFloat(position.size).toFixed(4)}</td>
            <td>${parseFloat(position.entry_price).toFixed(2)}</td>
            <td class="${position.pnl >= 0 ? 'profit' : 'loss'}">
                ${position.pnl.toFixed(2)} (${position.pnl_percent.toFixed(2)}%)
            </td>
            <td>
                <button onclick="closePosition('${position.symbol}')" class="btn btn-danger btn-sm">
                    Close
                </button>
            </td>
        </tr>
    `).join('');
}

// API Connections
async function closePosition(symbol) {
    try {
        const response = await fetch('/api/close_position', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ symbol })
        });
        
        const result = await response.json();
        if (response.ok) {
            showNotification('Position closed successfully', 'success');
            updatePositionsData();
        } else {
            showNotification(result.error, 'error');
        }
    } catch (error) {
        showNotification('Error closing position', 'error');
        console.error('Error:', error);
    }
}

// Form Handling
function handleOrderSubmit(event) {
    event.preventDefault();
    const formData = new FormData(event.target);
    const order = {
        symbol: formData.get('symbol'),
        side: formData.get('side'),
        quantity: formData.get('quantity'),
        price: formData.get('price') || null,
        tp_price: formData.get('tp_price') || null,
        sl_price: formData.get('sl_price') || null
    };
    
    placeOrder(order);
}

async function placeOrder(orderData) {
    try {
        const response = await fetch('/api/place_order', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(orderData)
        });
        
        const result = await response.json();
        if (response.ok) {
            showNotification('Order placed successfully', 'success');
            updatePositionsData();
        } else {
            showNotification(result.error, 'error');
        }
    } catch (error) {
        showNotification('Error placing order', 'error');
        console.error('Error:', error);
    }
}

// UI Utilities
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    notification.textContent = message;
    
    const container = document.querySelector('.notifications-container') || document.body;
    container.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    sidebar.classList.toggle('open');
}

function initializeEventListeners() {
    // Mobile menu toggle
    const menuToggle = document.querySelector('.menu-toggle');
    if (menuToggle) {
        menuToggle.addEventListener('click', toggleSidebar);
    }
    
    // Order form submission
    const orderForm = document.querySelector('#order-form');
    if (orderForm) {
        orderForm.addEventListener('submit', handleOrderSubmit);
    }
    
    // API form submission
    const apiForm = document.querySelector('#api-form');
    if (apiForm) {
        apiForm.addEventListener('submit', handleApiSubmit);
    }
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (priceUpdateInterval) {
        clearInterval(priceUpdateInterval);
    }
});