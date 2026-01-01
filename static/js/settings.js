// static/js/settings.js

class SettingsPage {
    constructor() {
        this.plaidHandler = null;
    }

    init() {
        this.setupEventListeners();
        this.loadConnectedAccounts();
    }

    // ============================================
    // EVENT LISTENERS
    // ============================================

    setupEventListeners() {
        document.getElementById('sidebarToggle').addEventListener('click', () => {
            document.querySelector('.sidebar').classList.toggle('open');
        });

        document.getElementById('profileForm').addEventListener('submit', this.handleProfileUpdate.bind(this));
        document.getElementById('passwordForm').addEventListener('submit', this.handlePasswordUpdate.bind(this));

        // Event delegation for dynamic buttons
        const connectedAccounts = document.getElementById('connectedAccounts');
        connectedAccounts.addEventListener('click', (e) => {
            const syncBtn = e.target.closest('.sync-btn');
            const deleteBtn = e.target.closest('.delete-btn');

            if (syncBtn) {
                this.syncInstitution(syncBtn.dataset.itemId);
            }
            if (deleteBtn) {
                if (confirm('Are you sure you want to remove this institution? All associated data will be deleted.')) {
                    this.deleteInstitution(deleteBtn.dataset.itemId);
                }
            }
        });
        
        document.getElementById('deleteAccountBtn').addEventListener('click', this.handleDeleteAccount.bind(this));
    }

    // ============================================
    // DATA LOADING
    // ============================================

    async loadConnectedAccounts() {
        const container = document.getElementById('connectedAccounts');
        try {
            const response = await fetch('/api/plaid/items');
            if (!response.ok) throw new Error('Failed to load accounts');
            
            const items = await response.json();
            this.renderConnectedAccounts(items);
        } catch (error) {
            console.error('Error loading connected accounts:', error);
            container.innerHTML = '<p class="error-text">Could not load connected accounts.</p>';
        }
    }

    // ============================================
    // RENDERING
    // ============================================

    renderConnectedAccounts(items) {
        const container = document.getElementById('connectedAccounts');
        if (items.length === 0) {
            container.innerHTML = '<p>No accounts are connected yet.</p>';
            return;
        }

        container.innerHTML = items.map(item => `
            <div class="connected-account-item">
                <div class="account-info">
                    <i class="fas fa-university"></i>
                    <div class="account-details">
                        <strong>${item.institution_name}</strong>
                        <span>${item.account_count} account(s) &bull; Last synced: ${this.formatRelativeTime(item.last_synced_at)}</span>
                    </div>
                </div>
                <div class="account-actions">
                    <button class="btn btn-secondary btn-sm sync-btn" data-item-id="${item.id}">
                        <i class="fas fa-sync-alt"></i> Sync
                    </button>
                    <button class="btn btn-danger btn-sm delete-btn" data-item-id="${item.id}">
                        <i class="fas fa-trash"></i> Remove
                    </button>
                </div>
            </div>
        `).join('');
    }

    // ============================================
    // FORM HANDLERS
    // ============================================

    async handleProfileUpdate(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch('/api/user/profile', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update profile');
            }

            this.showToast('Profile updated successfully', 'success');
        } catch (error) {
            console.error('Profile update error:', error);
            this.showToast(error.message, 'error');
        }
    }

    async handlePasswordUpdate(e) {
        e.preventDefault();
        const form = e.target;
        const newPassword = form.elements.new_password.value;
        const confirmPassword = form.elements.confirm_password.value;

        if (newPassword !== confirmPassword) {
            this.showToast('New passwords do not match', 'error');
            return;
        }

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            const response = await fetch('/api/user/password', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update password');
            }

            this.showToast('Password updated successfully', 'success');
            form.reset();
        } catch (error) {
            console.error('Password update error:', error);
            this.showToast(error.message, 'error');
        }
    }
    
    async handleDeleteAccount() {
        const confirmation = prompt('This will permanently delete your account and all data. This action cannot be undone. Please type "DELETE" to confirm.');
        if (confirmation !== 'DELETE') {
            this.showToast('Account deletion cancelled.', 'info');
            return;
        }

        try {
            const response = await fetch('/api/user/account', {
                method: 'DELETE'
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to delete account');
            }
            
            this.showToast('Account deleted successfully. You will be logged out.', 'success');
            setTimeout(() => {
                window.location.href = '/';
            }, 3000);

        } catch (error) {
            console.error('Account deletion error:', error);
            this.showToast(error.message, 'error');
        }
    }

    // ============================================
    // PLAID & ACCOUNT ACTIONS
    // ============================================

    async initPlaidLink() {
        try {
            const response = await fetch('/api/plaid/create-link-token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (!response.ok) throw new Error('Failed to create link token');
            
            const data = await response.json();
            
            this.plaidHandler = Plaid.create({
                token: data.link_token,
                onSuccess: (publicToken, metadata) => this.onPlaidSuccess(publicToken, metadata),
            });
            
            this.plaidHandler.open();
        } catch (error) {
            console.error('Plaid init error:', error);
            this.showToast('Failed to initialize Plaid Link', 'error');
        }
    }

    async onPlaidSuccess(publicToken, metadata) {
        try {
            const response = await fetch('/api/plaid/exchange-token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    public_token: publicToken,
                    institution: metadata.institution
                })
            });
            
            if (!response.ok) throw new Error('Failed to link account');
            
            this.showToast(`Successfully linked ${metadata.institution.name}!`, 'success');
            this.loadConnectedAccounts();
        } catch (error) {
            console.error('Link account error:', error);
            this.showToast('Failed to link account', 'error');
        }
    }

    async syncInstitution(itemId) {
        const syncBtn = document.querySelector(`.sync-btn[data-item-id="${itemId}"]`);
        syncBtn.disabled = true;
        syncBtn.innerHTML = '<i class="fas fa-sync-alt fa-spin"></i>';

        try {
            const response = await fetch(`/api/plaid/items/${itemId}/sync`, {
                method: 'POST'
            });
            if (!response.ok) throw new Error('Sync failed');
            this.showToast('Sync successful!', 'success');
            this.loadConnectedAccounts();
        } catch (error) {
            this.showToast('Sync failed', 'error');
        } finally {
            syncBtn.disabled = false;
            syncBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Sync';
        }
    }

    async deleteInstitution(itemId) {
        try {
            const response = await fetch(`/api/plaid/items/${itemId}`, {
                method: 'DELETE'
            });
            if (!response.ok) throw new Error('Deletion failed');
            this.showToast('Institution removed', 'success');
            this.loadConnectedAccounts();
        } catch (error) {
            this.showToast('Failed to remove institution', 'error');
        }
    }

    // ============================================
    // UTILITIES
    // ============================================

    formatRelativeTime(dateStr) {
        if (!dateStr) return 'Never';
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.round(diffMs / 60000);

        if (diffMins < 1) return 'just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffMins < 1440) return `${Math.round(diffMins / 60)}h ago`;
        return date.toLocaleDateString();
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

// Global function for Plaid Link
let settingsPage;
function openPlaidLink() {
    if (settingsPage) {
        settingsPage.initPlaidLink();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    settingsPage = new SettingsPage();
    settingsPage.init();
});
