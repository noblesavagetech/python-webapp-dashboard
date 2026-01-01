// static/js/investments.js

class InvestmentsPage {
    constructor() {
        this.portfolio = {};
        this.risk = {};
        this.transactions = [];
        this.dividends = {};
        this.charts = {};
    }

    async init() {
        this.showLoading();
        this.setupEventListeners();
        await this.loadData();
        this.hideLoading();
    }

    // ============================================
    // EVENT LISTENERS
    // ============================================

    setupEventListeners() {
        document.getElementById('sidebarToggle').addEventListener('click', () => {
            document.querySelector('.sidebar').classList.toggle('open');
        });
    }

    // ============================================
    // DATA LOADING
    // ============================================

    async loadData() {
        try {
            const response = await fetch('/api/dashboard/portfolio');
            if (!response.ok) throw new Error('Failed to load portfolio data');
            
            const data = await response.json();
            this.portfolio = data.summary || {};
            this.risk = data.risk_analysis || {};
            this.transactions = data.transactions || [];
            this.dividends = data.dividends || {};

            this.renderAll();
        } catch (error) {
            console.error('Error loading investment data:', error);
            this.showToast('Failed to load investment data', 'error');
            this.renderEmptyState();
        }
    }

    // ============================================
    // RENDERING
    // ============================================

    renderAll() {
        this.renderOverview();
        this.renderRiskAnalysis();
        this.renderHoldings();
        this.renderActivity();
        this.initCharts();
    }

    renderOverview() {
        document.getElementById('portfolioValue').textContent = this.formatCurrency(this.portfolio.total_value);
        document.getElementById('costBasis').textContent = this.formatCurrency(this.portfolio.total_cost_basis);
        
        const totalGain = this.portfolio.total_gain_loss || 0;
        const gainPercent = this.portfolio.total_gain_loss_percent || 0;
        const gainEl = document.getElementById('totalGain');
        const gainPercentEl = document.getElementById('gainPercent');

        gainEl.textContent = this.formatCurrency(totalGain, true);
        gainPercentEl.textContent = `${gainPercent.toFixed(2)}%`;
        
        if (totalGain >= 0) {
            gainEl.classList.add('positive');
            gainPercentEl.classList.add('positive');
        } else {
            gainEl.classList.add('negative');
            gainPercentEl.classList.add('negative');
        }

        document.getElementById('dividendIncome').textContent = this.formatCurrency(this.dividends.total_dividends);
    }

    renderRiskAnalysis() {
        const score = this.risk.diversification_score || 0;
        document.getElementById('diversificationScore').textContent = score.toFixed(0);
        document.getElementById('diversificationBar').style.width = `${score}%`;

        const concentration = this.risk.concentration_risk || {};
        const riskBadge = document.getElementById('concentrationRisk');
        riskBadge.textContent = concentration.level || 'N/A';
        riskBadge.className = `risk-badge ${concentration.level?.toLowerCase()}`;

        document.getElementById('holdingsCount').textContent = this.risk.total_holdings || 0;
        document.getElementById('sectorsCount').textContent = this.risk.total_sectors || 0;

        const recommendationsList = document.getElementById('recommendationsList');
        const recommendations = this.risk.recommendations || [];
        if (recommendations.length > 0) {
            recommendationsList.innerHTML = recommendations.map(rec => `<li>${rec}</li>`).join('');
        } else {
            recommendationsList.innerHTML = '<li>Portfolio appears well-balanced.</li>';
        }
    }

    renderHoldings() {
        const tbody = document.getElementById('holdingsBody');
        const holdings = this.portfolio.holdings || [];
        document.getElementById('holdingsCountLabel').textContent = `${holdings.length} holdings`;

        if (holdings.length === 0) {
            tbody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="8">
                        <div class="empty-state">
                            <i class="fas fa-chart-pie"></i>
                            <p>No holdings to display</p>
                            <span>Link an investment account to see your holdings</span>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = holdings.map(h => {
            const gain = h.unrealized_gain_loss || 0;
            const gainClass = gain >= 0 ? 'positive' : 'negative';
            return `
                <tr>
                    <td>${h.ticker_symbol || 'N/A'}</td>
                    <td>${h.name}</td>
                    <td>${this.formatType(h.type)}</td>
                    <td class="text-right">${parseFloat(h.quantity).toFixed(4)}</td>
                    <td class="text-right">${this.formatCurrency(h.price)}</td>
                    <td class="text-right">${this.formatCurrency(h.value)}</td>
                    <td class="text-right">${this.formatCurrency(h.cost_basis)}</td>
                    <td class="text-right ${gainClass}">${this.formatCurrency(gain, true)}</td>
                </tr>
            `;
        }).join('');
    }

    renderActivity() {
        const list = document.getElementById('activityList');
        if (this.transactions.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-history"></i>
                    <p>No recent investment activity</p>
                </div>
            `;
            return;
        }

        list.innerHTML = this.transactions.map(t => {
            const typeClass = t.type === 'buy' ? 'buy' : 'sell';
            const icon = t.type === 'buy' ? 'fa-arrow-up' : 'fa-arrow-down';
            return `
                <div class="activity-item">
                    <div class="activity-icon ${typeClass}">
                        <i class="fas ${icon}"></i>
                    </div>
                    <div class="activity-details">
                        <span class="activity-type">${this.formatType(t.type)}: ${t.name}</span>
                        <span class="activity-info">
                            ${parseFloat(t.quantity).toFixed(2)} shares @ ${this.formatCurrency(t.price)}
                        </span>
                    </div>
                    <div class="activity-meta">
                        <span class="activity-amount">${this.formatCurrency(t.amount)}</span>
                        <span class="activity-date">${this.formatDate(t.date)}</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    renderEmptyState() {
        // Hide loading, show empty states in all sections
        this.hideLoading();
        // You can add more specific empty state rendering if needed
    }

    // ============================================
    // CHARTS
    // ============================================

    initCharts() {
        this.initAllocationChart();
    }

    initAllocationChart() {
        const ctx = document.getElementById('allocationChart');
        if (!ctx) return;

        const allocation = this.portfolio.allocation_by_type || {};
        const labels = Object.keys(allocation);
        const data = labels.map(l => allocation[l].value);
        const colors = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#3b82f6'];

        this.charts.allocation = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels.length ? labels : ['No Data'],
                datasets: [{
                    data: data.length ? data : [1],
                    backgroundColor: colors,
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
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
        const legendContainer = document.getElementById('allocationLegend');
        if (legendContainer && labels.length) {
            legendContainer.innerHTML = labels.map((label, i) => `
                <div class="legend-item">
                    <div class="legend-color" style="background-color: ${colors[i]}"></div>
                    <span>${this.formatType(label)}</span>
                    <span class="legend-value">${this.formatCurrency(data[i])}</span>
                </div>
            `).join('');
        }
    }

    // ============================================
    // UTILITIES
    // ============================================

    formatCurrency(amount, showSign = false) {
        const value = new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(amount);
        
        if (showSign && amount > 0) {
            return `+${value}`;
        }
        return value;
    }

    formatDate(dateStr) {
        return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }

    formatType(type) {
        if (!type) return 'N/A';
        return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    showLoading() {
        document.getElementById('loadingOverlay').classList.add('active');
    }

    hideLoading() {
        document.getElementById('loadingOverlay').classList.remove('active');
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

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const page = new InvestmentsPage();
    page.init();
});
