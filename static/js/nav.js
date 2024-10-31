

// Global Variables
let websocket = null;
const WEBSOCKET_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}://${window.location.host}/ws`;
const PRICE_UPDATE_INTERVAL = 5000; // 5 seconds

// Document Ready Handler
document.addEventListener('DOMContentLoaded', () => {
    initializeFeatherIcons();
    initializeWebSocket();
    startPriceUpdates();
    initializeEventListeners();
    checkDarkMode();
});

// Initialize Feather Icons
function initializeFeatherIcons() {
    feather.replace();
}

// WebSocket Functions
function initializeWebSocket() {
    try {
        websocket = new WebSocket(WEBSOCKET_URL);
        
        websocket.onopen = () => {
            console.log('WebSocket connected');
            updateConnectionStatus('Connected');
        };

        websocket.onclose = () => {
            console.log('WebSocket disconnected');
            updateConnectionStatus('Disconnected');
            // Try to reconnect after 5 seconds
            setTimeout(initializeWebSocket, 5000);
        };

        websocket.onmessage = (event) => {
            handleWebSocketMessage(JSON.parse(event.data));
        };

        websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            updateConnectionStatus('Error');
        };
    } catch (error) {
        console.error('WebSocket initialization error:', error);
    }
}

// Handle WebSocket Messages
function handleWebSocketMessage(data) {
    switch(data.type) {
        case 'balance_update':
            updateBalance(data.balance);
            break;
        case 'positions_update':
            updatePositions(data.positions);
            break;
        case 'price_update':
            updatePrices(data.prices);
            break;
        case 'signal':
            handleSignal(data.signal);
            break;
    }
}

// Update Functions
async function updateNavStats() {
    try {
        const response = await fetch('/api/nav_stats');
        const data = await response.json();
        
        if (data.error) {
            console.error('Error fetching nav stats:', data.error);
            return;
        }

        // Update balance
        const balanceElement = document.getElementById('total-balance');
        if (balanceElement) {
            balanceElement.innerText = formatCurrency(data.total_balance);
            updateValueWithAnimation(balanceElement, data.total_balance);
        }

        // Update PNL
        const pnlElement = document.getElementById('daily-pnl');
        if (pnlElement) {
            const pnlFormatted = formatPNL(data.daily_pnl);
            pnlElement.innerText = pnlFormatted;
            pnlElement.className = `text-xs font-medium ${data.daily_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`;
        }

        // Update counters
        updateCounter('active-signals-count', data.active_signals);
        updateCounter('active-positions-count', data.active_positions);

    } catch (error) {
        console.error('Error updating nav stats:', error);
    }
}

// Real-time Price Updates
async function startPriceUpdates() {
    try {
        const response = await fetch('/get_prices');
        if (!response.ok) throw new Error('Failed to fetch prices');
        
        const prices = await response.json();
        updatePrices(prices);
    } catch (error) {
        console.error('Error fetching prices:', error);
    }
    
    setTimeout(startPriceUpdates, PRICE_UPDATE_INTERVAL);
}

// Event Listeners
function initializeEventListeners() {
    // Mobile menu toggle
    const menuToggle = document.querySelector('#mobile-menu-toggle');
    if (menuToggle) {
        menuToggle.addEventListener('click', toggleMobileMenu);
    }

    // Dark mode toggle
    const darkModeToggle = document.querySelector('#dark-mode-toggle');
    if (darkModeToggle) {
        darkModeToggle.addEventListener('click', toggleDarkMode);
    }

    // Dropdowns
    document.querySelectorAll('.dropdown-toggle').forEach(dropdown => {
        dropdown.addEventListener('click', toggleDropdown);
    });

    // Close dropdowns when clicking outside
    document.addEventListener('click', handleClickOutside);
}

// UI Functions
function toggleMobileMenu() {
    const nav = document.querySelector('nav');
    const mainContent = document.querySelector('.main-content');
    
    nav.classList.toggle('-translate-x-full');
    mainContent.classList.toggle('ml-0');
}

function toggleDarkMode() {
    document.documentElement.classList.toggle('dark');
    localStorage.setItem('darkMode', document.documentElement.classList.contains('dark'));
    
    // Update icon
    const icon = document.querySelector('#dark-mode-toggle i');
    if (document.documentElement.classList.contains('dark')) {
        feather.replace(icon, { 'name': 'sun' });
    } else {
        feather.replace(icon, { 'name': 'moon' });
    }
}

function toggleDropdown(event) {
    event.preventDefault();
    const dropdown = event.currentTarget.nextElementSibling;
    dropdown.classList.toggle('hidden');
}

// Utility Functions
function formatCurrency(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(value);
}

function formatPNL(value) {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${formatCurrency(value)}`;
}

function updateCounter(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = value;
        element.classList.add('update-animation');
        setTimeout(() => element.classList.remove('update-animation'), 500);
    }
}

function updateConnectionStatus(status) {
    const element = document.getElementById('connection-status');
    if (element) {
        element.textContent = status;
        element.className = `connection-status ${status.toLowerCase()}`;
    }
}

function checkDarkMode() {
    if (localStorage.getItem('darkMode') === 'true' || 
        window.matchMedia('(prefers-color-scheme: dark)').matches) {
        document.documentElement.classList.add('dark');
    }
}

// Cleanup
window.addEventListener('beforeunload', () => {
    if (websocket) {
        websocket.close();
    }
});