# app/routes/main_routes.py

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Landing page"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard view"""
    return render_template('dashboard/index.html')


@main_bp.route('/accounts')
@login_required
def accounts():
    """Accounts management view"""
    return render_template('dashboard/accounts.html')


@main_bp.route('/transactions')
@login_required
def transactions():
    """Transactions view"""
    return render_template('dashboard/transactions.html')


@main_bp.route('/investments')
@login_required
def investments():
    """Investments/Portfolio view"""
    return render_template('dashboard/investments.html')


@main_bp.route('/settings')
@login_required
def settings():
    """User settings view"""
    return render_template('dashboard/settings.html')
