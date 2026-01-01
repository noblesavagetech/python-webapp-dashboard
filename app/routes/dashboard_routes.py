# app/routes/dashboard_routes.py

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.services.analytics_engine import NetWorthTracker, CashFlowEngine, PortfolioManager
from app.models.financial_models import Account, Transaction, PlaidItem
from datetime import datetime, date, timedelta
from app import db

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')


@dashboard_bp.route('/overview', methods=['GET'])
@login_required
def get_overview():
    """
    Get complete dashboard overview data
    """
    net_worth_tracker = NetWorthTracker(current_user.id)
    cash_flow_engine = CashFlowEngine(current_user.id)
    portfolio_manager = PortfolioManager(current_user.id)
    
    # Get linked institutions count
    institutions_count = PlaidItem.query.filter_by(
        user_id=current_user.id,
        status='active'
    ).count()
    
    # Get accounts count
    accounts_count = Account.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).count()
    
    return jsonify({
        'net_worth': net_worth_tracker.calculate_current_net_worth(),
        'cash_flow': cash_flow_engine.analyze_cash_flow(),
        'portfolio': portfolio_manager.get_portfolio_summary(),
        'recent_transactions': get_recent_transactions_helper(current_user.id, limit=10),
        'summary': {
            'institutions_linked': institutions_count,
            'accounts_count': accounts_count,
            'last_sync': get_last_sync_time(current_user.id)
        }
    }), 200


@dashboard_bp.route('/net-worth', methods=['GET'])
@login_required
def get_net_worth():
    """
    Get detailed net worth information
    """
    tracker = NetWorthTracker(current_user.id)
    
    days = request.args.get('days', 365, type=int)
    
    return jsonify({
        'current': tracker.calculate_current_net_worth(),
        'history': tracker.get_net_worth_history(days=days),
        'metrics': tracker.calculate_wealth_metrics()
    }), 200


@dashboard_bp.route('/net-worth/snapshot', methods=['POST'])
@login_required
def create_net_worth_snapshot():
    """
    Create a net worth snapshot for today
    """
    tracker = NetWorthTracker(current_user.id)
    snapshot = tracker.save_daily_snapshot()
    
    return jsonify({
        'success': True,
        'snapshot': snapshot.to_dict()
    }), 200


@dashboard_bp.route('/cash-flow', methods=['GET'])
@login_required
def get_cash_flow():
    """
    Get cash flow analysis
    """
    engine = CashFlowEngine(current_user.id)
    
    # Parse date parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    else:
        start_date = date.today() - timedelta(days=30)
    
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    else:
        end_date = date.today()
    
    return jsonify({
        'analysis': engine.analyze_cash_flow(start_date, end_date),
        'forecast': engine.forecast_cash_flow(days=30),
        'insights': engine.get_spending_insights()
    }), 200


@dashboard_bp.route('/portfolio', methods=['GET'])
@login_required
def get_portfolio():
    """
    Get portfolio information
    """
    manager = PortfolioManager(current_user.id)
    
    days = request.args.get('days', 90, type=int)
    
    return jsonify({
        'summary': manager.get_portfolio_summary(),
        'transactions': manager.get_investment_transactions(days=days),
        'risk_analysis': manager.analyze_portfolio_risk(),
        'dividends': manager.get_dividend_income()
    }), 200


@dashboard_bp.route('/accounts', methods=['GET'])
@login_required
def get_accounts():
    """
    Get all accounts with balances
    """
    accounts = Account.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()
    
    # Group by institution
    institutions = {}
    for account in accounts:
        item = account.plaid_item
        if item.id not in institutions:
            institutions[item.id] = {
                'id': item.id,
                'name': item.institution_name,
                'status': item.status,
                'last_synced': item.last_synced_at.isoformat() if item.last_synced_at else None,
                'accounts': []
            }
        institutions[item.id]['accounts'].append(account.to_dict())
    
    return jsonify({
        'accounts': [a.to_dict() for a in accounts],
        'by_institution': list(institutions.values()),
        'totals': calculate_account_totals(accounts)
    }), 200


@dashboard_bp.route('/accounts/<account_id>', methods=['GET'])
@login_required
def get_account(account_id):
    """
    Get a specific account with details
    """
    account = Account.query.filter_by(
        id=account_id,
        user_id=current_user.id
    ).first_or_404()
    
    # Get recent transactions for this account
    recent_transactions = Transaction.query.filter_by(
        account_id=account_id
    ).order_by(Transaction.date.desc()).limit(20).all()
    
    return jsonify({
        'account': account.to_dict(),
        'institution': account.plaid_item.institution_name,
        'recent_transactions': [t.to_dict() for t in recent_transactions]
    }), 200


@dashboard_bp.route('/accounts/<account_id>', methods=['PATCH'])
@login_required
def update_account(account_id):
    """
    Update account settings (classification, inclusion in net worth, etc.)
    """
    account = Account.query.filter_by(
        id=account_id,
        user_id=current_user.id
    ).first_or_404()
    
    data = request.get_json()
    
    if 'is_asset' in data:
        account.is_asset = data['is_asset']
    if 'is_liquid' in data:
        account.is_liquid = data['is_liquid']
    if 'include_in_net_worth' in data:
        account.include_in_net_worth = data['include_in_net_worth']
    if 'custom_category' in data:
        account.custom_category = data['custom_category']
    
    db.session.commit()
    
    return jsonify({'success': True, 'account': account.to_dict()}), 200


@dashboard_bp.route('/transactions', methods=['GET'])
@login_required
def get_transactions():
    """
    Get transactions with filtering and pagination
    """
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Filters
    account_id = request.args.get('account_id')
    category = request.args.get('category')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search = request.args.get('search')
    cash_flow_type = request.args.get('cash_flow_type')
    
    query = Transaction.query.filter_by(user_id=current_user.id)
    
    if account_id:
        query = query.filter(Transaction.account_id == account_id)
    
    if category:
        query = query.filter(Transaction.category_primary == category)
    
    if cash_flow_type:
        query = query.filter(Transaction.cash_flow_type == cash_flow_type)
    
    if start_date:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        query = query.filter(Transaction.date >= start)
    
    if end_date:
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        query = query.filter(Transaction.date <= end)
    
    if search:
        search_term = f'%{search}%'
        query = query.filter(
            db.or_(
                Transaction.name.ilike(search_term),
                Transaction.merchant_name.ilike(search_term)
            )
        )
    
    query = query.order_by(Transaction.date.desc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'transactions': [t.to_dict() for t in pagination.items],
        'pagination': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200


@dashboard_bp.route('/transactions/<transaction_id>', methods=['PATCH'])
@login_required
def update_transaction(transaction_id):
    """
    Update transaction (custom category, etc.)
    """
    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id
    ).first_or_404()
    
    data = request.get_json()
    
    if 'custom_category' in data:
        transaction.custom_category = data['custom_category']
    if 'cash_flow_type' in data:
        transaction.cash_flow_type = data['cash_flow_type']
    
    db.session.commit()
    
    return jsonify({'success': True, 'transaction': transaction.to_dict()}), 200


@dashboard_bp.route('/categories', methods=['GET'])
@login_required
def get_categories():
    """
    Get list of transaction categories with spending totals
    """
    # Get spending by category for current month
    today = date.today()
    month_start = today.replace(day=1)
    
    categories = db.session.query(
        Transaction.category_primary,
        db.func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.date >= month_start,
        Transaction.amount > 0  # Expenses only
    ).group_by(
        Transaction.category_primary
    ).order_by(
        db.desc('total')
    ).all()
    
    return jsonify({
        'categories': [
            {'name': c[0] or 'UNCATEGORIZED', 'total': float(c[1] or 0)}
            for c in categories
        ]
    }), 200


# Helper functions

def get_recent_transactions_helper(user_id: str, limit: int = 10):
    """Helper to get recent transactions"""
    transactions = Transaction.query.filter_by(
        user_id=user_id
    ).order_by(Transaction.date.desc()).limit(limit).all()
    
    return [t.to_dict() for t in transactions]


def get_last_sync_time(user_id: str):
    """Get the most recent sync time across all items"""
    item = PlaidItem.query.filter_by(
        user_id=user_id
    ).order_by(PlaidItem.last_synced_at.desc()).first()
    
    if item and item.last_synced_at:
        return item.last_synced_at.isoformat()
    return None


def calculate_account_totals(accounts):
    """Calculate total balances across accounts"""
    total_assets = 0
    total_liabilities = 0
    total_checking = 0
    total_savings = 0
    total_credit = 0
    total_investment = 0
    
    for account in accounts:
        balance = float(account.balance_current or 0)
        
        if account.is_asset:
            total_assets += balance
            
            if account.subtype == 'checking':
                total_checking += balance
            elif account.subtype == 'savings':
                total_savings += balance
            elif account.type == 'investment':
                total_investment += balance
        else:
            total_liabilities += abs(balance)
            if account.type == 'credit':
                total_credit += abs(balance)
    
    return {
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'net_worth': total_assets - total_liabilities,
        'checking': total_checking,
        'savings': total_savings,
        'credit': total_credit,
        'investment': total_investment
    }
