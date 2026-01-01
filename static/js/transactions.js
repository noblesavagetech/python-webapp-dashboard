// static/js/transactions.js

class TransactionsPage {
    constructor() {
        this.transactions = [];
        this.accounts = [];
        this.filters = {
            page: 1,
            per_page: 50,
            search: '',
            start_date: '',
            end_date: '',
            account_id: '',
            type: ''
        };
        this.pagination = {};
    }

    async init() {
        this.showLoading();
        this.setupEventListeners();
        await this.loadInitialData();
        this.hideLoading();
    }

    // ============================================
    // EVENT LISTENERS
    // ============================================

    setupEventListeners() {
        // Sidebar
        document.getElementById('sidebarToggle').addEventListener('click', () => {
            document.querySelector('.sidebar').classList.toggle('open');
        });

        // Filters
        document.getElementById('searchInput').addEventListener('debounce', this.handleFilterChange.bind(this));
        document.getElementById('startDate').addEventListener('change', this.handleFilterChange.bind(this));
        document.getElementById('endDate').addEventListener('change', this.handleFilterChange.bind(this));
        document.getElementById('accountFilter').addEventListener('change', this.handleFilterChange.bind(this));
        document.getElementById('typeFilter').addEventListener('change', this.handleFilterChange.bind(this));
        
        // Debounce search input
        this.debounceInput(document.getElementById('searchInput'), 300);

        // Clear filters
        document.getElementById('clearFilters').addEventListener('click', this.clearFilters.bind(this));

        // Pagination
        document.getElementById('prevPage').addEventListener('click', () => this.changePage(this.filters.page - 1));
        document.getElementById('nextPage').addEventListener('click', () => this.changePage(this.filters.page + 1));
        
        // Export
        document.getElementById('exportBtn').addEventListener('click', this.exportToCSV.bind(this));
    }

    debounceInput(element, delay) {
        let timer;
        element.addEventListener('input', () => {
            clearTimeout(timer);
            timer = setTimeout(() => {
                element.dispatchEvent(new CustomEvent('debounce'));
            }, delay);
        });
    }

    // ============================================
    // DATA LOADING
    // ============================================

    async loadInitialData() {
        try {
            await this.loadAccounts();
            await this.loadTransactions();
        } catch (error) {
            console.error("Error loading initial data:", error);
            this.showToast('Failed to load page data', 'error');
        }
    }

    async loadAccounts() {
        try {
            const response = await fetch('/api/dashboard/accounts');
            if (!response.ok) throw new Error('Failed to load accounts');
            this.accounts = await response.json();
            this.populateAccountFilter();
        } catch (error) {
            console.error("Error loading accounts:", error);
            this.showToast('Failed to load accounts filter', 'error');
        }
    }

    async loadTransactions() {
        this.showLoading();
        try {
            const query = new URLSearchParams(this.filters).toString();
            const response = await fetch(`/api/dashboard/transactions?${query}`);
            if (!response.ok) throw new Error('Failed to load transactions');
            
            const data = await response.json();
            this.transactions = data.transactions;
            this.pagination = data.pagination;
            
            this.renderTransactions();
            this.updatePagination();
        } catch (error) {
            console.error("Error loading transactions:", error);
            this.showToast('Failed to load transactions', 'error');
            this.renderEmptyState();
        } finally {
            this.hideLoading();
        }
    }

    // ============================================
    // RENDERING & UI UPDATES
    // ============================================

    populateAccountFilter() {
        const select = document.getElementById('accountFilter');
        this.accounts.forEach(acc => {
            const option = document.createElement('option');
            option.value = acc.id;
            option.textContent = `${acc.name} (${acc.mask})`;
            select.appendChild(option);
        });
    }

    renderTransactions() {
        const tbody = document.getElementById('transactionsBody');
        const countEl = document.getElementById('transactionCount');

        if (this.transactions.length === 0) {
            this.renderEmptyState();
            countEl.textContent = '0 transactions';
            return;
        }

        tbody.innerHTML = this.transactions.map(txn => {
            const isIncome = txn.amount < 0;
            return `
                <tr>
                    <td>${this.formatDate(txn.date)}</td>
                    <td>
                        <div class="description-cell">
                            <span class="description-main">${txn.merchant_name || txn.name}</span>
                            <span class="description-sub">${txn.pending ? 'Pending' : ''}</span>
                        </div>
                    </td>
                    <td>
                        <span class="category-badge">${this.formatCategory(txn.category)}</span>
                    </td>
                    <td>${this.getAccountName(txn.account_id)}</td>
                    <td class="amount-cell ${isIncome ? 'income' : 'expense'}">
                        ${isIncome ? '+' : '-'}${this.formatCurrency(Math.abs(txn.amount))}
                    </td>
                </tr>
            `;
        }).join('');

        countEl.textContent = `${this.pagination.total} transactions`;
    }

    renderEmptyState() {
        const tbody = document.getElementById('transactionsBody');
        tbody.innerHTML = `
            <tr>
                <td colspan="5">
                    <div class="empty-state-row">
                        <i class="fas fa-receipt"></i>
                        <h3>No transactions found</h3>
                        <p>Try adjusting your filters or link an account to see transactions.</p>
                    </div>
                </td>
            </tr>
        `;
    }

    updatePagination() {
        const { page, pages, has_prev, has_next } = this.pagination;
        document.getElementById('pageInfo').textContent = `Page ${page} of ${pages}`;
        document.getElementById('prevPage').disabled = !has_prev;
        document.getElementById('nextPage').disabled = !has_next;
    }

    // ============================================
    // EVENT HANDLERS
    // ============================================

    handleFilterChange() {
        this.filters.page = 1;
        this.filters.search = document.getElementById('searchInput').value;
        this.filters.start_date = document.getElementById('startDate').value;
        this.filters.end_date = document.getElementById('endDate').value;
        this.filters.account_id = document.getElementById('accountFilter').value;
        this.filters.type = document.getElementById('typeFilter').value;
        this.loadTransactions();
    }

    clearFilters() {
        this.filters = { page: 1, per_page: 50, search: '', start_date: '', end_date: '', account_id: '', type: '' };
        
        document.getElementById('searchInput').value = '';
        document.getElementById('startDate').value = '';
        document.getElementById('endDate').value = '';
        document.getElementById('accountFilter').value = '';
        document.getElementById('typeFilter').value = '';

        this.loadTransactions();
    }

    changePage(newPage) {
        if (newPage > 0 && newPage <= this.pagination.pages) {
            this.filters.page = newPage;
            this.loadTransactions();
        }
    }
    
    // ============================================
    // EXPORT
    // ============================================

    exportToCSV() {
        if (this.transactions.length === 0) {
            this.showToast('No transactions to export', 'info');
            return;
        }

        const headers = ['Date', 'Description', 'Category', 'Account', 'Amount', 'Currency'];
        const rows = this.transactions.map(txn => [
            txn.date,
            `"${txn.merchant_name || txn.name}"`,
            `"${this.formatCategory(txn.category)}"`,
            `"${this.getAccountName(txn.account_id)}"`,
            txn.amount,
            txn.iso_currency_code
        ]);

        let csvContent = "data:text/csv;charset=utf-8," 
            + headers.join(",") + "\n" 
            + rows.map(e => e.join(",")).join("\n");

        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", "transactions.csv");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // ============================================
    // UTILITIES
    // ============================================

    formatDate(dateStr) {
        return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }

    formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(amount);
    }

    formatCategory(category) {
        if (!category) return 'Uncategorized';
        return category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    getAccountName(accountId) {
        const account = this.accounts.find(acc => acc.id === accountId);
        return account ? account.name : 'N/A';
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
    const page = new TransactionsPage();
    page.init();
});
