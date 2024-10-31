{% set active_page = request.endpoint %}

<!-- Navigation -->
<nav class="fixed top-0 left-0 h-full w-64 bg-[#1c2c4f] shadow-lg z-40 transition-transform duration-300 transform">
    <!-- Brand Logo -->
    <div class="p-4 border-b border-gray-700">
        <div class="flex items-center">
            <img src="{{ url_for('static', filename='images/logo.png') }}" alt="Logo" class="w-8 h-8 mr-3">
            <span class="text-lg font-semibold text-white">Trading Platform</span>
        </div>
    </div>

    <!-- User Info -->
    <div class="p-4 border-b border-gray-700">
        <div class="flex items-center space-x-3">
            <div class="w-10 h-10 rounded-full bg-[#2d4a7c] flex items-center justify-center">
                <i data-feather="user" class="w-5 h-5 text-gray-300"></i>
            </div>
            <div>
                <div class="text-sm font-medium text-white">{{ current_user.username }}</div>
                <div class="text-xs text-gray-400">{{ current_user.account_type }}</div>
            </div>
        </div>
    </div>

    <!-- Balance Info -->
    <div class="p-4 border-b border-gray-700">
        <div class="text-xs text-gray-400 mb-1">Total Balance</div>
        <div class="text-lg font-semibold text-white" id="total-balance">
            $0.00
        </div>
        <div class="flex items-center mt-1">
            <span class="text-xs text-gray-400 mr-2">PNL 24h:</span>
            <span class="text-xs font-medium pnl-value" id="daily-pnl">+$0.00</span>
        </div>
    </div>

    <!-- Navigation Links -->
    <div class="py-4">
        <!-- Dashboard -->
        <a href="{{ url_for('dashboard') }}" 
           class="flex items-center px-4 py-3 text-gray-400 hover:bg-[#2d4a7c] hover:text-white transition-colors {% if active_page == 'dashboard' %}bg-[#2d4a7c] text-white{% endif %}">
            <i data-feather="grid" class="w-5 h-5 mr-3"></i>
            <span>Dashboard</span>
        </a>

        <!-- Trading -->
        <a href="{{ url_for('trading') }}" 
           class="flex items-center px-4 py-3 text-gray-400 hover:bg-[#2d4a7c] hover:text-white transition-colors {% if active_page == 'trading' %}bg-[#2d4a7c] text-white{% endif %}">
            <i data-feather="trending-up" class="w-5 h-5 mr-3"></i>
            <span>Trading</span>
        </a>

        <!-- Signals -->
        <a href="{{ url_for('signals') }}" 
           class="flex items-center px-4 py-3 text-gray-400 hover:bg-[#2d4a7c] hover:text-white transition-colors {% if active_page == 'signals' %}bg-[#2d4a7c] text-white{% endif %}">
            <i data-feather="zap" class="w-5 h-5 mr-3"></i>
            <span>Signals</span>
            <span class="ml-auto bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded text-xs" id="active-signals-count">0</span>
        </a>

        <!-- Positions -->
        <a href="{{ url_for('positions') }}" 
           class="flex items-center px-4 py-3 text-gray-400 hover:bg-[#2d4a7c] hover:text-white transition-colors {% if active_page == 'positions' %}bg-[#2d4a7c] text-white{% endif %}">
            <i data-feather="layers" class="w-5 h-5 mr-3"></i>
            <span>Positions</span>
            <span class="ml-auto bg-blue-500/20 text-blue-400 px-2 py-1 rounded text-xs" id="active-positions-count">0</span>
        </a>

        <!-- History -->
        <a href="{{ url_for('history') }}" 
           class="flex items-center px-4 py-3 text-gray-400 hover:bg-[#2d4a7c] hover:text-white transition-colors {% if active_page == 'history' %}bg-[#2d4a7c] text-white{% endif %}">
            <i data-feather="clock" class="w-5 h-5 mr-3"></i>
            <span>History</span>
        </a>

        <!-- Settings Dropdown -->
        <div class="relative" x-data="{ open: false }">
            <button @click="open = !open" 
                    class="w-full flex items-center px-4 py-3 text-gray-400 hover:bg-[#2d4a7c] hover:text-white transition-colors">
                <i data-feather="settings" class="w-5 h-5 mr-3"></i>
                <span>Settings</span>
                <i data-feather="chevron-down" class="w-4 h-4 ml-auto" :class="{'transform rotate-180': open}"></i>
            </button>
            
            <div x-show="open" 
                 @click.away="open = false" 
                 class="pl-4"
                 x-transition:enter="transition ease-out duration-200"
                 x-transition:enter-start="opacity-0 transform -translate-y-2"
                 x-transition:enter-end="opacity-100 transform translate-y-0"
                 x-transition:leave="transition ease-in duration-150"
                 x-transition:leave-start="opacity-100 transform translate-y-0"
                 x-transition:leave-end="opacity-0 transform -translate-y-2">
                <a href="{{ url_for('api_settings') }}" 
                   class="flex items-center px-4 py-2 text-gray-400 hover:text-white {% if active_page == 'api_settings' %}text-white{% endif %}">
                    <i data-feather="key" class="w-4 h-4 mr-3"></i>
                    <span>API Settings</span>
                </a>
                <a href="{{ url_for('preferences') }}" 
                   class="flex items-center px-4 py-2 text-gray-400 hover:text-white {% if active_page == 'preferences' %}text-white{% endif %}">
                    <i data-feather="sliders" class="w-4 h-4 mr-3"></i>
                    <span>Preferences</span>
                </a>
                <a href="{{ url_for('notifications') }}" 
                   class="flex items-center px-4 py-2 text-gray-400 hover:text-white {% if active_page == 'notifications' %}text-white{% endif %}">
                    <i data-feather="bell" class="w-4 h-4 mr-3"></i>
                    <span>Notifications</span>
                    <span class="notification-badge hidden ml-2"></span>
                </a>
            </div>
        </div>
    </div>

    <!-- Bottom Actions -->
    <div class="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-700">
        <div class="flex items-center justify-between">
            <button class="text-gray-400 hover:text-white" 
                    onclick="toggleDarkMode()" 
                    title="Toggle Dark Mode">
                <i data-feather="moon" class="w-5 h-5"></i>
            </button>
            <form action="{{ url_for('logout') }}" method="post" class="inline">
                <button type="submit" 
                        class="flex items-center text-gray-400 hover:text-white"
                        title="Logout">
                    <i data-feather="log-out" class="w-5 h-5 mr-2"></i>
                    <span>Logout</span>
                </button>
            </form>
        </div>
    </div>
</nav>

<!-- Mobile Menu Toggle -->
<button class="fixed top-4 right-4 z-50 p-2 bg-[#2d4a7c] rounded-lg md:hidden" 
        onclick="toggleMobileMenu()"
        aria-label="Toggle Menu">
    <i data-feather="menu" class="w-6 h-6 text-white"></i>
</button>

<!-- Navigation Scripts -->
<script src="{{ url_for('static', filename='js/nav.js') }}"></script>

<!-- Load Icons -->
<script>
    document.addEventListener('DOMContentLoaded', function() {
        feather.replace();
    });
</script>