# app/models/financial_models.py

from app import db
from datetime import datetime
from sqlalchemy import Index
import uuid


class PlaidItem(db.Model):
    """
    Represents a Plaid Item (connection to a financial institution)
    """
    __tablename__ = 'plaid_items'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    item_id = db.Column(db.String(255), unique=True, nullable=False)
    access_token = db.Column(db.Text, nullable=False)
    institution_id = db.Column(db.String(50))
    institution_name = db.Column(db.String(255))
    status = db.Column(db.String(20), default='active')  # active, error, pending_expiration
    consent_expiration_time = db.Column(db.DateTime)
    last_synced_at = db.Column(db.DateTime)
    error_code = db.Column(db.String(100))
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    accounts = db.relationship('Account', backref='plaid_item', lazy='dynamic', cascade='all, delete-orphan')
    
    __table_args__ = (
        Index('idx_plaid_items_user_id', 'user_id'),
        Index('idx_plaid_items_item_id', 'item_id'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'institution_id': self.institution_id,
            'institution_name': self.institution_name,
            'status': self.status,
            'last_synced_at': self.last_synced_at.isoformat() if self.last_synced_at else None,
            'account_count': self.accounts.count(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Account(db.Model):
    """
    Financial account linked through Plaid
    """
    __tablename__ = 'accounts'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plaid_item_id = db.Column(db.String(36), db.ForeignKey('plaid_items.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.String(255), unique=True, nullable=False)  # Plaid account_id
    
    # Account Details
    name = db.Column(db.String(255))
    official_name = db.Column(db.String(255))
    mask = db.Column(db.String(10))  # Last 4 digits
    type = db.Column(db.String(50))  # depository, investment, loan, credit
    subtype = db.Column(db.String(50))  # checking, savings, 401k, credit card, etc.
    
    # Balance Information (updated regularly)
    balance_available = db.Column(db.Numeric(15, 2))
    balance_current = db.Column(db.Numeric(15, 2))
    balance_limit = db.Column(db.Numeric(15, 2))
    iso_currency_code = db.Column(db.String(3), default='USD')
    
    # Classification for net worth calculation
    is_asset = db.Column(db.Boolean, default=True)
    is_liquid = db.Column(db.Boolean, default=False)
    include_in_net_worth = db.Column(db.Boolean, default=True)
    custom_category = db.Column(db.String(100))
    
    # Metadata
    is_active = db.Column(db.Boolean, default=True)
    last_balance_update = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='account', lazy='dynamic', cascade='all, delete-orphan')
    holdings = db.relationship('Holding', backref='account', lazy='dynamic', cascade='all, delete-orphan')
    balance_history = db.relationship('BalanceSnapshot', backref='account', lazy='dynamic', cascade='all, delete-orphan')
    
    __table_args__ = (
        Index('idx_accounts_user_id', 'user_id'),
        Index('idx_accounts_plaid_item_id', 'plaid_item_id'),
        Index('idx_accounts_account_id', 'account_id'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'official_name': self.official_name,
            'mask': self.mask,
            'type': self.type,
            'subtype': self.subtype,
            'balance_available': float(self.balance_available) if self.balance_available else None,
            'balance_current': float(self.balance_current) if self.balance_current else None,
            'balance_limit': float(self.balance_limit) if self.balance_limit else None,
            'is_asset': self.is_asset,
            'is_liquid': self.is_liquid,
            'include_in_net_worth': self.include_in_net_worth,
            'custom_category': self.custom_category,
            'last_updated': self.last_balance_update.isoformat() if self.last_balance_update else None
        }


class Transaction(db.Model):
    """
    Individual financial transactions
    """
    __tablename__ = 'transactions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('accounts.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    transaction_id = db.Column(db.String(255), unique=True, nullable=False)
    
    # Transaction Details
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    iso_currency_code = db.Column(db.String(3), default='USD')
    date = db.Column(db.Date, nullable=False)
    datetime_val = db.Column(db.DateTime)
    authorized_date = db.Column(db.Date)
    
    # Merchant/Description
    name = db.Column(db.String(500))
    merchant_name = db.Column(db.String(255))
    
    # Categorization
    category_primary = db.Column(db.String(100))
    category_detailed = db.Column(db.String(100))
    custom_category = db.Column(db.String(100))
    
    # Cash Flow Classification
    cash_flow_type = db.Column(db.String(20))  # income, expense, transfer, investment
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_stream_id = db.Column(db.String(36), db.ForeignKey('recurring_transactions.id'))
    
    # Status
    pending = db.Column(db.Boolean, default=False)
    
    # Location (optional)
    location_city = db.Column(db.String(100))
    location_region = db.Column(db.String(50))
    location_country = db.Column(db.String(50))
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_transactions_user_id', 'user_id'),
        Index('idx_transactions_account_id', 'account_id'),
        Index('idx_transactions_date', 'date'),
        Index('idx_transactions_category', 'category_primary'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'amount': float(self.amount) if self.amount else 0,
            'date': self.date.isoformat() if self.date else None,
            'name': self.name,
            'merchant_name': self.merchant_name,
            'category': self.category_primary,
            'category_detailed': self.category_detailed,
            'cash_flow_type': self.cash_flow_type,
            'is_recurring': self.is_recurring,
            'pending': self.pending
        }


class RecurringTransaction(db.Model):
    """
    Identified recurring transaction streams
    """
    __tablename__ = 'recurring_transactions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.String(36), db.ForeignKey('accounts.id'), nullable=False)
    
    # Stream Details
    stream_id = db.Column(db.String(255))
    description = db.Column(db.String(255))
    merchant_name = db.Column(db.String(255))
    
    # Recurrence Pattern
    frequency = db.Column(db.String(20))  # weekly, biweekly, monthly, annually
    average_amount = db.Column(db.Numeric(15, 2))
    last_amount = db.Column(db.Numeric(15, 2))
    
    # Classification
    is_income = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    
    # Dates
    first_date = db.Column(db.Date)
    last_date = db.Column(db.Date)
    next_expected_date = db.Column(db.Date)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='recurring_stream', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'merchant_name': self.merchant_name,
            'frequency': self.frequency,
            'average_amount': float(self.average_amount) if self.average_amount else 0,
            'is_income': self.is_income,
            'next_expected_date': self.next_expected_date.isoformat() if self.next_expected_date else None
        }


class Holding(db.Model):
    """
    Investment holdings (stocks, bonds, funds, etc.)
    """
    __tablename__ = 'holdings'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('accounts.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    security_id = db.Column(db.String(36), db.ForeignKey('securities.id'), nullable=False)
    
    # Position Details
    quantity = db.Column(db.Numeric(20, 10))
    cost_basis = db.Column(db.Numeric(15, 2))
    institution_price = db.Column(db.Numeric(15, 4))
    institution_value = db.Column(db.Numeric(15, 2))
    institution_price_as_of = db.Column(db.Date)
    iso_currency_code = db.Column(db.String(3), default='USD')
    
    # Calculated Fields
    unrealized_gain_loss = db.Column(db.Numeric(15, 2))
    unrealized_gain_loss_percent = db.Column(db.Numeric(10, 4))
    
    # Metadata
    last_updated = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_holdings_user_id', 'user_id'),
        Index('idx_holdings_account_id', 'account_id'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'account_id': self.account_id,
            'quantity': float(self.quantity) if self.quantity else 0,
            'cost_basis': float(self.cost_basis) if self.cost_basis else 0,
            'current_value': float(self.institution_value) if self.institution_value else 0,
            'unrealized_gain_loss': float(self.unrealized_gain_loss) if self.unrealized_gain_loss else 0,
            'unrealized_gain_loss_percent': float(self.unrealized_gain_loss_percent) if self.unrealized_gain_loss_percent else 0
        }


class Security(db.Model):
    """
    Security master data (stocks, ETFs, mutual funds, etc.)
    """
    __tablename__ = 'securities'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    security_id = db.Column(db.String(255), unique=True, nullable=False)
    
    # Identifiers
    ticker_symbol = db.Column(db.String(20))
    cusip = db.Column(db.String(12))
    isin = db.Column(db.String(20))
    
    # Details
    name = db.Column(db.String(255))
    type = db.Column(db.String(50))  # equity, etf, mutual fund, fixed income, cash
    
    # Pricing
    close_price = db.Column(db.Numeric(15, 4))
    close_price_as_of = db.Column(db.Date)
    iso_currency_code = db.Column(db.String(3), default='USD')
    
    # Classification
    is_cash_equivalent = db.Column(db.Boolean, default=False)
    sector = db.Column(db.String(100))
    industry = db.Column(db.String(100))
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    holdings = db.relationship('Holding', backref='security', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'ticker_symbol': self.ticker_symbol,
            'name': self.name,
            'type': self.type,
            'close_price': float(self.close_price) if self.close_price else 0,
            'sector': self.sector
        }


class InvestmentTransaction(db.Model):
    """
    Investment-specific transactions (buys, sells, dividends, etc.)
    """
    __tablename__ = 'investment_transactions'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('accounts.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    security_id = db.Column(db.String(36), db.ForeignKey('securities.id'))
    investment_transaction_id = db.Column(db.String(255), unique=True, nullable=False)
    
    # Transaction Details
    date = db.Column(db.Date, nullable=False)
    name = db.Column(db.String(500))
    type = db.Column(db.String(50))  # buy, sell, cancel, cash, fee, transfer
    subtype = db.Column(db.String(50))  # dividend, interest, etc.
    
    # Amounts
    amount = db.Column(db.Numeric(15, 2))
    price = db.Column(db.Numeric(15, 4))
    quantity = db.Column(db.Numeric(20, 10))
    fees = db.Column(db.Numeric(15, 2))
    iso_currency_code = db.Column(db.String(3), default='USD')
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_inv_transactions_user_id', 'user_id'),
        Index('idx_inv_transactions_date', 'date'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'name': self.name,
            'type': self.type,
            'subtype': self.subtype,
            'amount': float(self.amount) if self.amount else 0,
            'quantity': float(self.quantity) if self.quantity else 0
        }


class Liability(db.Model):
    """
    Liability/Debt information (credit cards, loans, mortgages)
    """
    __tablename__ = 'liabilities'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('accounts.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    # Liability Type
    type = db.Column(db.String(50))  # credit, student, mortgage
    
    # Credit Card Specific
    is_overdue = db.Column(db.Boolean)
    last_payment_amount = db.Column(db.Numeric(15, 2))
    last_payment_date = db.Column(db.Date)
    last_statement_balance = db.Column(db.Numeric(15, 2))
    minimum_payment_amount = db.Column(db.Numeric(15, 2))
    next_payment_due_date = db.Column(db.Date)
    
    # Loan Specific
    interest_rate_percentage = db.Column(db.Numeric(8, 4))
    interest_rate_type = db.Column(db.String(20))  # fixed, variable
    origination_date = db.Column(db.Date)
    origination_principal_amount = db.Column(db.Numeric(15, 2))
    
    # Metadata
    last_updated = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'is_overdue': self.is_overdue,
            'minimum_payment': float(self.minimum_payment_amount) if self.minimum_payment_amount else 0,
            'next_payment_due': self.next_payment_due_date.isoformat() if self.next_payment_due_date else None,
            'interest_rate': float(self.interest_rate_percentage) if self.interest_rate_percentage else 0
        }


class BalanceSnapshot(db.Model):
    """
    Historical balance snapshots for trend analysis
    """
    __tablename__ = 'balance_snapshots'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), db.ForeignKey('accounts.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    snapshot_date = db.Column(db.Date, nullable=False)
    balance_available = db.Column(db.Numeric(15, 2))
    balance_current = db.Column(db.Numeric(15, 2))
    balance_limit = db.Column(db.Numeric(15, 2))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_balance_snapshots_account_date', 'account_id', 'snapshot_date'),
    )


class NetWorthSnapshot(db.Model):
    """
    Daily net worth calculations for trend tracking
    """
    __tablename__ = 'net_worth_snapshots'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    snapshot_date = db.Column(db.Date, nullable=False)
    
    # Asset Breakdown
    total_assets = db.Column(db.Numeric(15, 2))
    liquid_assets = db.Column(db.Numeric(15, 2))
    investment_assets = db.Column(db.Numeric(15, 2))
    other_assets = db.Column(db.Numeric(15, 2))
    
    # Liability Breakdown
    total_liabilities = db.Column(db.Numeric(15, 2))
    credit_card_debt = db.Column(db.Numeric(15, 2))
    loan_debt = db.Column(db.Numeric(15, 2))
    mortgage_debt = db.Column(db.Numeric(15, 2))
    
    # Calculated
    net_worth = db.Column(db.Numeric(15, 2))
    
    # Change Tracking
    daily_change = db.Column(db.Numeric(15, 2))
    daily_change_percent = db.Column(db.Numeric(10, 4))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_net_worth_snapshots_user_date', 'user_id', 'snapshot_date'),
    )
    
    def to_dict(self):
        return {
            'date': self.snapshot_date.isoformat() if self.snapshot_date else None,
            'net_worth': float(self.net_worth) if self.net_worth else 0,
            'total_assets': float(self.total_assets) if self.total_assets else 0,
            'total_liabilities': float(self.total_liabilities) if self.total_liabilities else 0,
            'daily_change': float(self.daily_change) if self.daily_change else 0,
            'daily_change_percent': float(self.daily_change_percent) if self.daily_change_percent else 0
        }
