// static/js/accounts.js

class AccountsPage {
    constructor() {
        this.accounts = [];
        this.institutions = {};
        this.plaidHandler = null;
    }

    async init() {
        this.showLoading();
        this.setupEventListeners();
        await this.loadAccountsData();
        this.hideLoading();
    }

    // ============================================
    // EVENT LISTENERS
    // ============================================

    setupEventListeners() {
        const sidebarToggle = document.getElementById('sidebarToggle');
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => {
                document.querySelector('.sidebar').classList.toggle('open');
            });
        }

        // Use event delegation for dynamically created sync/delete buttons
        const institutionsList = document.getElementById('institutionsList');
        if (institutionsList) {
            institutionsList.addEventListener('click', (e) => {
                const syncBtn = e.target.closest('.sync-btn');
                const deleteBtn = e.target.closest('.delete-btn');

                if (syncBtn) {
                    const itemId = syncBtn.dataset.itemId;
                    this.syncInstitution(itemId);
                }

                if (deleteBtn) {
                    const itemId = deleteBtn.dataset.itemId;
                    const institutionName = deleteBtn.dataset.institutionName;
                    if (confirm(`Are you sure you want to remove ${institutionName}? This will delete all associated accounts and data.`)) {
                        this.deleteInstitution(itemId);
                    }
                }
            });
        }
    }

    // ============================================
    // DATA LOADING
    // ============================================

    async loadAccountsData() {
        try {
            const response = await fetch('/api/dashboard/accounts');
            if (!response.ok) throw new Error('Failed to load accounts data');
            
            this.accounts = await response.json();
            this.processAndRenderData();
        } catch (error) {
            console.error('Error loading accounts:', error);
            this.showToast('Failed to load accounts data', 'error');
            this.renderEmptyState();
        }
    }

    // ============================================
    // RENDERING
    // ============================================

    processAndRenderData() {
        this.calculateTotals();
        this.groupAccountsByInstitution();
        this.renderInstitutions();
    }

    calculateTotals() {
        let totalAssets = 0;
        let totalLiabilities = 0;
        
        this.accounts.forEach(acc => {
            if (acc.is_asset) {
                totalAssets += parseFloat(acc.balance_current);
            } else {
                totalLiabilities += parseFloat(acc.balance_current);
            }
        });

        const netWorth = totalAssets - totalLiabilities;

        document.getElementById('totalAssets').textContent = this.formatCurrency(totalAssets);
        document.getElementById('totalLiabilities').textContent = this.formatCurrency(totalLiabilities);
        document.getElementById('netWorth').textContent = this.formatCurrency(netWorth);
    }

    groupAccountsByInstitution() {
        this.institutions = this.accounts.reduce((groups, account) => {
            const institutionId = account.plaid_item_id;
            if (!groups[institutionId]) {
                groups[institutionId] = {
                    id: account.plaid_item_id,
                    name: account.institution_name,
                    accounts: []
                };
            }
            groups[institutionId].accounts.push(account);
            return groups;
        }, {});
        
        document.getElementById('institutionsCount').textContent = Object.keys(this.institutions).length;
    }

    renderInstitutions() {
        const container = document.getElementById('institutionsList');
        if (!container) return;

        const institutionIds = Object.keys(this.institutions);

        if (institutionIds.length === 0) {
            this.renderEmptyState();
            return;
        }

        container.innerHTML = institutionIds.map(id => {
            const inst = this.institutions[id];
            return `
                <div class="institution-card">
                    <div class="institution-header">
                        <div class="institution-info">
                            <h4>${inst.name}</h4>
                            <span>${inst.accounts.length} account(s)</span>
                        </div>
                        <div class="institution-actions">
                            <button class="btn btn-secondary btn-sm sync-btn" data-item-id="${inst.id}">
                                <i class="fas fa-sync-alt"></i> Sync
                            </button>
                            <button class="btn btn-danger btn-sm delete-btn" data-item-id="${inst.id}" data-institution-name="${inst.name}">
                                <i class="fas fa-trash"></i> Delete
                            </button>
                        </div>
                    </div>
                    <div class="accounts-table">
                        <table>
                            <thead>
                                <tr>
                                    <th>Account Name</th>
                                    <th>Type</th>
                                    <th class="text-right">Balance</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${inst.accounts.map(acc => this.renderAccountRow(acc)).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }).join('');
    }
    
    renderAccountRow(account) {
        return `
            <tr>
                <td>
                    <div class="account-name-cell">
                        <i class="fas ${this.getAccountIcon(account.type)}"></i>
                        <span>${account.name} (${account.mask})</span>
                    </div>
                </td>
                <td>${this.formatAccountType(account.type, account.subtype)}</td>
                <td class="text-right">${this.formatCurrency(account.balance_current)}</td>
            </tr>
        `;
    }

    renderEmptyState() {
        const container = document.getElementById('institutionsList');
        if (container) {
            container.innerHTML = `
                <div class="empty-state full-width">
                    <i class="fas fa-university"></i>
                    <h3>No accounts linked</h3>
                    <p>Connect your bank accounts, credit cards, and investments to get started.</p>
                    <button class="btn btn-primary" onclick="openPlaidLink()">
                        <i class="fas fa-plus"></i>
                        Link Your First Account
                    </button>
                </div>
            `;
        }
    }

    // ============================================
    // PLAID INTEGRATION
    // ============================================

    async initPlaidLink() {
        try {
            const response = await fetch('/api/plaid/create-link-token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (!response.ok) throw new Error('Failed to create link token');
            
            const data = await response.json();
            
            const isOauth = (new URLSearchParams(window.location.search)).get('oauth_state_id') !== null;

            this.plaidHandler = Plaid.create({
                token: data.link_token,
                onSuccess: (publicToken, metadata) => this.onPlaidSuccess(publicToken, metadata),
                onExit: (err, metadata) => this.onPlaidExit(err, metadata),
                receivedRedirectUri: isOauth ? window.location.href : null,
            });
            
            if (!isOauth) {
                this.plaidHandler.open();
            }
        } catch (error) {
            console.error('Plaid init error:', error);
            this.showToast('Failed to initialize Plaid Link', 'error');
        }
    }

    async onPlaidSuccess(publicToken, metadata) {
        try {
            this.showLoading();
            
            const response = await fetch('/api/plaid/exchange-token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    public_token: publicToken,
                    institution: metadata.institution
                })
            });
            
            if (!response.ok) throw new Error('Failed to link account');
            
            const data = await response.json();
            this.showToast(`Successfully linked ${data.institution_name}!`, 'success');
            
            await this.loadAccountsData();
        } catch (error) {
            console.error('Link account error:', error);
            this.showToast('Failed to link account', 'error');
        } finally {
            this.hideLoading();
        }
    }

    onPlaidExit(err, metadata) {
        if (err) {
            console.error('Plaid exit error:', err);
        }
    }

    // ============================================
    // ACTIONS
    // ============================================

    async syncInstitution(itemId) {
        const syncBtn = document.querySelector(`.sync-btn[data-item-id="${itemId}"]`);
        if (syncBtn) {
            syncBtn.disabled = true;
            syncBtn.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i> Syncing...';
        }

        try {
            const response = await fetch(`/api/plaid/items/${itemId}/sync`, {
                method: 'POST'
            });
            
            if (!response.ok) throw new Error('Sync failed');
            
            const data = await response.json();
            this.showToast(`Sync completed for ${data.institution_name}`, 'success');
            
            await this.loadAccountsData();
        } catch (error) {
            console.error('Sync error:', error);
            this.showToast('Failed to sync institution', 'error');
        } finally {
            if (syncBtn) {
                syncBtn.disabled = false;
                syncBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Sync';
            }
        }
    }

    async deleteInstitution(itemId) {
        this.showLoading();
        try {
            const response = await fetch(`/api/plaid/items/${itemId}`, {
                method: 'DELETE'
            });

            if (!response.ok) throw new Error('Failed to delete institution');

            this.showToast('Institution removed successfully', 'success');
            await this.loadAccountsData();

        } catch (error) {
            console.error('Delete error:', error);
            this.showToast('Failed to remove institution', 'error');
        } finally {
            this.hideLoading();
        }
    }

    // ============================================
    // UTILITIES
    // ============================================

    formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(amount);
    }

    formatAccountType(type, subtype) {
        const types = {
            'depository': subtype === 'checking' ? 'Checking' : subtype === 'savings' ? 'Savings' : 'Bank Account',
            'credit': 'Credit Card',
            'investment': 'Investment',
            'loan': 'Loan',
            'mortgage': 'Mortgage'
        };
        return types[type] || type.charAt(0).toUpperCase() + type.slice(1);
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

    showLoading() {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) overlay.classList.add('active');
    }

    hideLoading() {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) overlay.classList.remove('active');
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

// Global function for Plaid Link button
let accountsPage;
function openPlaidLink() {
    if (accountsPage) {
        accountsPage.initPlaidLink();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    accountsPage = new AccountsPage();
    accountsPage.init();
});
