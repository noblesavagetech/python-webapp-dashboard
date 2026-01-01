// static/js/dashboard.js - Main Dashboard JavaScript

class FinancialDashboard {
    constructor() {
        this.charts = {};
        this.data = {};
        this.plaidHandler = null;
    }

    async init() {
        this.showLoading();
        this.setupEventListeners();
        await this.loadDashboardData();
        this.hideLoading();
    }

    // ============================================
    // EVENT LISTENERS
    // ============================================

    setupEventListeners() {
        // Sidebar toggle
        const sidebarToggle = document.getElementById('sidebarToggle');
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => {
                document.querySelector('.sidebar').classList.toggle('open');
            });
        }

        // Chart period selector
        document.querySelectorAll('.period-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.loadNetWorthHistory(parseInt(e.target.dataset.period));
            });
        });
    }

    // ============================================
    // DATA LOADING
    // ============================================

    async loadDashboardData() {
        try {
            const response = await fetch('/api/dashboard/overview');
            if (!response.ok) throw new Error('Failed to load dashboard data');
            
            this.data = await response.json();
            this.renderDashboard();
        } catch (error) {
            console.error('Error loading dashboard:', error);
            this.showToast('Failed to load dashboard data', 'error');
        }
    }

    async loadNetWorthHistory(days = 30) {
        try {
            const response = await fetch(`/api/dashboard/net-worth?days=${days}`);
            if (!response.ok) throw new Error('Failed to load history');
            
            const data = await response.json();
            this.updateNetWorthChart(data.history);
        } catch (error) {
            console.error('Error loading history:', error);
        }
    }

    // ============================================
    // RENDERING
    // ============================================

    renderDashboard() {
        this.renderNetWorth();
        this.renderStats();
        this.renderAccounts();
        this.renderTransactions();
        this.renderInsights();
        this.renderPortfolio();
        this.initCharts();
    }

    renderNetWorth() {
        const netWorth = this.data.net_worth || {};
        
        // Net worth amount
        const netWorthAmount = document.getElementById('netWorthAmount');
        if (netWorthAmount) {
            netWorthAmount.textContent = this.formatNumber(netWorth.net_worth || 0);
        }

        // Total assets
        const totalAssets = document.getElementById('totalAssets');
        if (totalAssets) {
            totalAssets.textContent = this.formatCurrency(netWorth.total_assets || 0);
        }

        // Total liabilities
        const totalLiabilities = document.getElementById('totalLiabilities');
        if (totalLiabilities) {
            totalLiabilities.textContent = this.formatCurrency(netWorth.total_liabilities || 0);
        }

        // Net worth change
        const changeElement = document.getElementById('netWorthChange');
        if (changeElement && netWorth.changes) {
            const monthly = netWorth.changes.monthly || {};
            const changeAmount = monthly.amount || 0;
            const changePercent = monthly.percent || 0;
            const isPositive = changeAmount >= 0;
            
            changeElement.innerHTML = `
                <span class="change-badge ${isPositive ? 'positive' : 'negative'}">
                    <i class="fas fa-arrow-${isPositive ? 'up' : 'down'}"></i>
                    ${isPositive ? '+' : ''}${this.formatCurrency(changeAmount)} (${changePercent.toFixed(1)}%) this month
                </span>
            `;
        }

        // Last updated
        const lastUpdated = document.getElementById('lastUpdated');
        if (lastUpdated && this.data.summary) {
            const lastSync = this.data.summary.last_sync;
            if (lastSync) {
                lastUpdated.textContent = `Updated ${this.formatRelativeTime(lastSync)}`;
            }
        }
    }

    renderStats() {
        const cashFlow = this.data.cash_flow || {};
        const portfolio = this.data.portfolio || {};

        // Income
        const totalIncome = document.getElementById('totalIncome');
        if (totalIncome) {
            totalIncome.textContent = this.formatCurrency(cashFlow.total_income || 0);
        }

        // Expenses
        const totalExpenses = document.getElementById('totalExpenses');
        if (totalExpenses) {
            totalExpenses.textContent = this.formatCurrency(cashFlow.total_expenses || 0);
        }

        // Savings rate
        const savingsRate = document.getElementById('savingsRate');
        if (savingsRate) {
            savingsRate.textContent = `${(cashFlow.savings_rate || 0).toFixed(0)}%`;
        }

        // Portfolio value
        const portfolioValue = document.getElementById('portfolioValue');
        if (portfolioValue) {
            portfolioValue.textContent = this.formatCurrency(portfolio.total_value || 0);
        }
    }

    renderAccounts() {
        const accounts = this.data.net_worth?.assets_breakdown || [];
        const liabilities = this.data.net_worth?.liabilities_breakdown || [];
        const allAccounts = [...accounts, ...liabilities];
        
        const container = document.getElementById('accountsList');
        if (!container) return;

        if (allAccounts.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-university"></i>
                    <p>No accounts linked yet</p>
                    <button class="btn btn-primary btn-sm" onclick="openPlaidLink()">
                        Link Your First Account
                    </button>
                </div>
            `;
            return;
        }

        container.innerHTML = allAccounts.slice(0, 5).map(account => `
            <div class="account-item">
                <div class="account-icon ${this.getAccountIconClass(account.type)}">
                    <i class="fas ${this.getAccountIcon(account.type)}"></i>
                </div>
                <div class="account-info">
                    <div class="account-name">${account.name}</div>
                    <div class="account-type">${this.formatAccountType(account.type, account.subtype)}</div>
                </div>
                <div class="account-balance ${account.balance < 0 ? 'negative' : ''}">
                    <div class="amount">${this.formatCurrency(Math.abs(account.balance))}</div>
                </div>
            </div>
        `).join('');
    }

    renderTransactions() {
        const transactions = this.data.recent_transactions || [];
        const container = document.getElementById('transactionsList');
        
        if (!container) return;

        if (transactions.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-receipt"></i>
                    <p>No transactions yet</p>
                    <span>Link an account to see your transactions</span>
                </div>
            `;
            return;
        }

        container.innerHTML = transactions.map(txn => {
            const isIncome = txn.amount < 0;
            return `
                <div class="transaction-item">
                    <div class="transaction-icon ${isIncome ? 'income' : 'expense'}">
                        <i class="fas fa-${isIncome ? 'arrow-down' : 'arrow-up'}"></i>
                    </div>
                    <div class="transaction-info">
                        <div class="transaction-name">${txn.merchant_name || txn.name}</div>
                        <div class="transaction-date">${this.formatDate(txn.date)}</div>
                    </div>
                    <div class="transaction-amount ${isIncome ? 'income' : 'expense'}">
                        ${isIncome ? '+' : '-'}${this.formatCurrency(Math.abs(txn.amount))}
                    </div>
                </div>
            `;
        }).join('');
    }

    renderInsights() {
        const insights = this.data.cash_flow?.insights?.recommendations || [];
        const container = document.getElementById('insightsList');
        
        if (!container) return;

        if (insights.length === 0) {
            container.innerHTML = `
                <div class="insight-item">
                    <div class="insight-icon">
                        <i class="fas fa-chart-line"></i>
                    </div>
                    <div class="insight-content">
                        <p>Link your accounts to get personalized financial insights.</p>
                    </div>
                </div>
            `;
            return;
        }

        container.innerHTML = insights.map(insight => `
            <div class="insight-item">
                <div class="insight-icon">
                    <i class="fas fa-lightbulb"></i>
                </div>
                <div class="insight-content">
                    <p>${insight}</p>
                </div>
            </div>
        `).join('');
    }

    renderPortfolio() {
        const portfolio = this.data.portfolio || {};
        
        const portfolioTotal = document.getElementById('portfolioTotal');
        if (portfolioTotal) {
            portfolioTotal.textContent = this.formatCurrency(portfolio.total_value || 0);
        }

        const portfolioGain = document.getElementById('portfolioGain');
        if (portfolioGain) {
            const gain = portfolio.total_gain_loss || 0;
            const isPositive = gain >= 0;
            portfolioGain.textContent = `${isPositive ? '+' : ''}${this.formatCurrency(gain)}`;
            portfolioGain.style.color = isPositive ? 'var(--success)' : 'var(--danger)';
        }
    }

    // ============================================
    // CHARTS
    // ============================================

    destroyCharts() {
        // Destroy all existing charts before recreating
        Object.keys(this.charts).forEach(key => {
            if (this.charts[key]) {
                this.charts[key].destroy();
                this.charts[key] = null;
            }
        });
    }

    initCharts() {
        // Destroy existing charts first to prevent "Canvas already in use" error
        this.destroyCharts();
        
        this.initNetWorthChart();
        this.initCashFlowChart();
        this.initSpendingChart();
        this.initAllocationChart();
    }

    initNetWorthChart() {
        const ctx = document.getElementById('netWorthChart');
        if (!ctx) return;

        const history = this.data.net_worth?.history || [];
        const labels = history.map(h => this.formatDateShort(h.date));
        const data = history.map(h => h.net_worth);

        this.charts.netWorth = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels.length ? labels : ['No data'],
                datasets: [{
                    label: 'Net Worth',
                    data: data.length ? data : [0],
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => this.formatCurrency(context.raw)
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { maxTicksLimit: 6 }
                    },
                    y: {
                        grid: { color: 'rgba(0,0,0,0.05)' },
                        ticks: {
                            callback: (value) => this.formatCompact(value)
                        }
                    }
                }
            }
        });
    }

    updateNetWorthChart(history) {
        if (!this.charts.netWorth) return;

        const labels = history.map(h => this.formatDateShort(h.date));
        const data = history.map(h => h.net_worth);

        this.charts.netWorth.data.labels = labels;
        this.charts.netWorth.data.datasets[0].data = data;
        this.charts.netWorth.update();
    }

    initCashFlowChart() {
        const ctx = document.getElementById('cashFlowChart');
        if (!ctx) return;

        const dailyData = this.data.cash_flow?.daily_data || [];
        const labels = dailyData.map(d => this.formatDateShort(d.date));
        const income = dailyData.map(d => d.income);
        const expenses = dailyData.map(d => d.expenses);

        this.charts.cashFlow = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels.length ? labels : ['No data'],
                datasets: [
                    {
                        label: 'Income',
                        data: income.length ? income : [0],
                        backgroundColor: '#22c55e',
                        borderRadius: 4
                    },
                    {
                        label: 'Expenses',
                        data: expenses.length ? expenses : [0],
                        backgroundColor: '#ef4444',
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.dataset.label}: ${this.formatCurrency(context.raw)}`
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { maxTicksLimit: 7 }
                    },
                    y: {
                        grid: { color: 'rgba(0,0,0,0.05)' },
                        ticks: {
                            callback: (value) => this.formatCompact(value)
                        }
                    }
                }
            }
        });
    }

    initSpendingChart() {
        const ctx = document.getElementById('spendingChart');
        if (!ctx) return;

        const categories = this.data.cash_flow?.expenses_by_category || {};
        const labels = Object.keys(categories).slice(0, 6);
        const data = labels.map(l => categories[l]);
        const colors = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#3b82f6'];

        this.charts.spending = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels.length ? labels : ['No data'],
                datasets: [{
                    data: data.length ? data : [1],
                    backgroundColor: colors,
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.label}: ${this.formatCurrency(context.raw)}`
                        }
                    }
                }
            }
        });

        // Render legend
        const legendContainer = document.getElementById('spendingLegend');
        if (legendContainer && labels.length) {
            legendContainer.innerHTML = labels.map((label, i) => `
                <div class="legend-item">
                    <div class="legend-color" style="background-color: ${colors[i]}"></div>
                    <span>${this.formatCategory(label)}</span>
                </div>
            `).join('');
        }
    }

    initAllocationChart() {
        const ctx = document.getElementById('allocationChart');
        if (!ctx) return;

        const allocation = this.data.portfolio?.allocation || {};
        const labels = Object.keys(allocation);
        const data = labels.map(l => allocation[l]?.value || 0);
        const colors = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6'];

        this.charts.allocation = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: labels.length ? labels : ['No holdings'],
                datasets: [{
                    data: data.length ? data : [1],
                    backgroundColor: colors,
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.label}: ${this.formatCurrency(context.raw)}`
                        }
                    }
                }
            }
        });
    }

    // ============================================
    // PLAID INTEGRATION
    // ============================================

    async initPlaidLink() {
        try {
            this.showLoading('Creating Link token...');
            const tokenResponse = await fetch('/api/plaid/create-link-token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!tokenResponse.ok) {
                const errorData = await tokenResponse.json();
                throw new Error(errorData.error || 'Failed to create link token');
            }

            const data = await tokenResponse.json();
            const link_token = data.link_token;
            
            if (!link_token) {
                throw new Error('No link token received from server');
            }

            this.hideLoading();

            // Create Plaid Link handler
            // Sandbox test credentials:
            // - Select any bank (e.g., "First Platypus Bank")
            // - Username: user_good
            // - Password: pass_good
            // - Phone (if asked): 415-555-0010
            // - OTP code (if asked): 123456
            const handler = Plaid.create({
                token: link_token,
                onSuccess: async (public_token, metadata) => {
                    console.log('Plaid Link success:', metadata);
                    this.showLoading('Connecting account...');
                    await this.exchangePublicToken(public_token, metadata);
                    this.hideLoading();
                    this.showToast('Account linked successfully!', 'success');
                    await this.loadDashboardData(); // Refresh dashboard
                },
                onLoad: () => {
                    console.log('Plaid Link loaded');
                },
                onExit: (err, metadata) => {
                    console.log('Plaid Link exit:', err, metadata);
                    if (err != null) {
                        this.showToast(`Link error: ${err.error_message || err.display_message || 'Unknown error'}`, 'error');
                    }
                },
                onEvent: (eventName, metadata) => {
                    console.log('Plaid Link event:', eventName, metadata);
                }
            });

            // Open Plaid Link
            handler.open();

        } catch (error) {
            console.error('Error initializing Plaid Link:', error);
            this.showToast(error.message, 'error');
            this.hideLoading();
        }
    }

    async exchangePublicToken(publicToken, metadata) {
        try {
            const response = await fetch('/api/plaid/exchange-token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    public_token: publicToken,
                    institution: metadata.institution
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to exchange public token');
            }
            
            return await response.json();
        } catch (error) {
            console.error('Token exchange error:', error);
            this.showToast(error.message, 'error');
            throw error;
        }
    }

    // ============================================
    // SYNC
    // ============================================

    async syncAllAccounts() {
        try {
            const syncBtn = document.getElementById('syncBtn');
            if (syncBtn) {
                syncBtn.disabled = true;
                syncBtn.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i><span>Syncing...</span>';
            }

            const response = await fetch('/api/plaid/sync-all', {
                method: 'POST'
            });
            
            if (!response.ok) throw new Error('Sync failed');
            
            const data = await response.json();
            this.showToast(`Synced ${data.items_synced} account(s)`, 'success');
            
            // Reload dashboard
            await this.loadDashboardData();
        } catch (error) {
            console.error('Sync error:', error);
            this.showToast('Failed to sync accounts', 'error');
        } finally {
            const syncBtn = document.getElementById('syncBtn');
            if (syncBtn) {
                syncBtn.disabled = false;
                syncBtn.innerHTML = '<i class="fas fa-sync-alt"></i><span>Sync</span>';
            }
        }
    }

    // ============================================
    // UTILITIES
    // ============================================

    formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    }

    formatNumber(amount) {
        return new Intl.NumberFormat('en-US', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    }

    formatCompact(amount) {
        return new Intl.NumberFormat('en-US', {
            notation: 'compact',
            compactDisplay: 'short',
            maximumFractionDigits: 1
        }).format(amount);
    }

    formatDate(dateStr) {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }

    formatDateShort(dateStr) {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }

    formatRelativeTime(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffMins < 1) return 'just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    }

    formatAccountType(type, subtype) {
        const types = {
            'depository': subtype === 'checking' ? 'Checking' : subtype === 'savings' ? 'Savings' : 'Bank Account',
            'credit': 'Credit Card',
            'investment': 'Investment',
            'loan': 'Loan',
            'mortgage': 'Mortgage'
        };
        return types[type] || type;
    }

    formatCategory(category) {
        return category.replace(/_/g, ' ').toLowerCase()
            .split(' ')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }

    getAccountIcon(type) {
        const icons = {
            'depository': 'fa-landmark',
            'credit': 'fa-credit-card',
            'investment': 'fa-chart-line',
            'loan': 'fa-file-invoice-dollar',
            'mortgage': 'fa-home'
        };
        return icons[type] || 'fa-wallet';
    }

    getAccountIconClass(type) {
        const classes = {
            'depository': 'checking',
            'credit': 'credit',
            'investment': 'investment',
            'loan': 'loan'
        };
        return classes[type] || 'checking';
    }

    showLoading(message = 'Loading...') {
        const overlay = document.getElementById('loadingOverlay');
        const spinner = document.getElementById('loadingSpinner');
        const messageEl = document.getElementById('loadingMessage');

        if (overlay) overlay.classList.add('active');
        if (spinner) spinner.classList.add('active');
        if (messageEl) {
            messageEl.textContent = message;
            messageEl.classList.add('active');
        }
    }

    hideLoading() {
        const overlay = document.getElementById('loadingOverlay');
        const spinner = document.getElementById('loadingSpinner');
        const messageEl = document.getElementById('loadingMessage');

        if (overlay) overlay.classList.remove('active');
        if (spinner) spinner.classList.remove('active');
        if (messageEl) messageEl.classList.remove('active');
    }

    showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        `;
        
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 5000);
    }
}

// Global functions
let dashboard;

function openPlaidLink() {
    if (dashboard) {
        dashboard.initPlaidLink();
    }
}

function syncAllAccounts() {
    if (dashboard) {
        dashboard.syncAllAccounts();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new FinancialDashboard();
    dashboard.init();
});
