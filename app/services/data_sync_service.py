# app/services/data_sync_service.py

from datetime import datetime, timedelta, date
from decimal import Decimal
from app import db
from app.services.plaid_service import PlaidService
from app.models.financial_models import (
    PlaidItem, Account, Transaction, Holding, Security,
    InvestmentTransaction, Liability, BalanceSnapshot
)
from flask import current_app


def safe_str(value):
    """
    Safely convert Plaid enum types to strings.
    Plaid SDK returns enum objects that need to be converted to strings for database storage.
    """
    if value is None:
        return None
    if hasattr(value, 'value'):
        return str(value.value)
    return str(value)


def safe_decimal(value):
    """Safely convert a value to Decimal"""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except:
        return Decimal('0')


class DataSyncService:
    """
    Service for synchronizing data from Plaid to local database
    """
    
    def __init__(self):
        self.plaid_service = PlaidService()
    
    def sync_item(self, plaid_item_id: str) -> dict:
        """
        Synchronize all data for a specific Plaid item
        
        Args:
            plaid_item_id: The internal PlaidItem ID
            
        Returns:
            dict with sync results summary
        """
        item = PlaidItem.query.get(plaid_item_id)
        if not item:
            raise Exception(f"Plaid item not found: {plaid_item_id}")
        
        results = {
            'item_id': plaid_item_id,
            'accounts_synced': 0,
            'transactions_synced': 0,
            'holdings_synced': 0,
            'securities_synced': 0,
            'liabilities_synced': 0,
            'errors': []
        }
        
        try:
            # Sync accounts and balances
            results['accounts_synced'] = self._sync_accounts(item)
        except Exception as e:
            results['errors'].append(f"Accounts sync error: {str(e)}")
            current_app.logger.error(f"Accounts sync error: {e}")
        
        try:
            # Sync transactions
            results['transactions_synced'] = self._sync_transactions(item)
        except Exception as e:
            results['errors'].append(f"Transactions sync error: {str(e)}")
            current_app.logger.error(f"Transactions sync error: {e}")
        
        try:
            # Sync investments
            holdings, securities = self._sync_investments(item)
            results['holdings_synced'] = holdings
            results['securities_synced'] = securities
        except Exception as e:
            results['errors'].append(f"Investments sync error: {str(e)}")
            current_app.logger.error(f"Investments sync error: {e}")
        
        try:
            # Sync liabilities
            results['liabilities_synced'] = self._sync_liabilities(item)
        except Exception as e:
            results['errors'].append(f"Liabilities sync error: {str(e)}")
            current_app.logger.error(f"Liabilities sync error: {e}")
        
        # Update last synced timestamp
        item.last_synced_at = datetime.utcnow()
        db.session.commit()
        
        return results
    
    def _sync_accounts(self, item: PlaidItem) -> int:
        """Sync accounts and balances from Plaid"""
        response = self.plaid_service.get_accounts_balance(item.access_token)
        synced_count = 0
        
        for acc_data in response['accounts']:
            # Find or create account
            account = Account.query.filter_by(
                account_id=acc_data['account_id']
            ).first()
            
            if not account:
                account = Account(
                    plaid_item_id=item.id,
                    user_id=item.user_id,
                    account_id=acc_data['account_id']
                )
                db.session.add(account)
            
            # Update account details - convert Plaid enums to strings
            account.name = acc_data.get('name')
            account.official_name = acc_data.get('official_name')
            account.mask = acc_data.get('mask')
            account.type = safe_str(acc_data.get('type'))
            account.subtype = safe_str(acc_data.get('subtype'))
            
            # Update balances
            balances = acc_data.get('balances', {})
            account.balance_available = safe_decimal(balances.get('available'))
            account.balance_current = safe_decimal(balances.get('current'))
            account.balance_limit = safe_decimal(balances.get('limit')) if balances.get('limit') else None
            account.iso_currency_code = balances.get('iso_currency_code') or 'USD'
            
            # Set classification based on account type
            account_type = safe_str(acc_data.get('type'))
            account.is_asset = account_type not in ['credit', 'loan']
            account.is_liquid = account_type == 'depository'
            
            account.last_balance_update = datetime.utcnow()
            
            # Create balance snapshot
            self._create_balance_snapshot(account)
            
            synced_count += 1
        
        db.session.commit()
        return synced_count
    
    def _sync_transactions(self, item: PlaidItem) -> int:
        """Sync transactions from Plaid"""
        # Get transactions for the last 90 days
        start_date = datetime.now() - timedelta(days=90)
        end_date = datetime.now()
        
        response = self.plaid_service.get_transactions(
            item.access_token,
            start_date=start_date,
            end_date=end_date
        )
        
        synced_count = 0
        
        for txn_data in response['transactions']:
            # Find or create transaction
            transaction = Transaction.query.filter_by(
                transaction_id=txn_data['transaction_id']
            ).first()
            
            if not transaction:
                # Find the account
                account = Account.query.filter_by(
                    account_id=txn_data['account_id']
                ).first()
                
                if not account:
                    continue
                
                transaction = Transaction(
                    account_id=account.id,
                    user_id=item.user_id,
                    transaction_id=txn_data['transaction_id']
                )
                db.session.add(transaction)
            
            # Update transaction details
            transaction.amount = safe_decimal(txn_data.get('amount', 0))
            transaction.iso_currency_code = txn_data.get('iso_currency_code') or 'USD'
            
            # Handle date - could be string or date object
            txn_date = txn_data.get('date')
            if isinstance(txn_date, str):
                transaction.date = datetime.strptime(txn_date, '%Y-%m-%d').date()
            elif hasattr(txn_date, 'date'):
                transaction.date = txn_date
            else:
                transaction.date = txn_date
                
            transaction.name = txn_data.get('name')
            transaction.merchant_name = txn_data.get('merchant_name')
            
            # Categorization - handle Plaid enum types
            personal_finance = txn_data.get('personal_finance_category', {}) or {}
            if personal_finance:
                transaction.category_primary = safe_str(personal_finance.get('primary')) or 'UNCATEGORIZED'
                transaction.category_detailed = safe_str(personal_finance.get('detailed'))
            
            # Cash flow classification
            amount = float(txn_data.get('amount', 0))
            primary_cat = safe_str(personal_finance.get('primary')) if personal_finance else ''
            if amount < 0:
                transaction.cash_flow_type = 'income'
            elif primary_cat in ['TRANSFER_IN', 'TRANSFER_OUT']:
                transaction.cash_flow_type = 'transfer'
            else:
                transaction.cash_flow_type = 'expense'
            
            transaction.pending = txn_data.get('pending', False)
            
            # Location
            location = txn_data.get('location', {}) or {}
            transaction.location_city = location.get('city')
            transaction.location_region = location.get('region')
            transaction.location_country = location.get('country')
            
            synced_count += 1
        
        db.session.commit()
        return synced_count
    
    def _sync_investments(self, item: PlaidItem) -> tuple:
        """Sync investment holdings and securities from Plaid"""
        response = self.plaid_service.get_investments_holdings(item.access_token)
        
        securities_synced = 0
        holdings_synced = 0
        
        # First, sync securities
        security_map = {}
        for sec_data in response.get('securities', []):
            security = self._sync_security(sec_data)
            security_map[sec_data['security_id']] = security
            securities_synced += 1
        
        # Then sync holdings
        for holding_data in response.get('holdings', []):
            account = Account.query.filter_by(
                account_id=holding_data['account_id']
            ).first()
            
            if not account:
                continue
            
            plaid_security_id = holding_data.get('security_id')
            security = security_map.get(plaid_security_id)
            
            if not security:
                continue
            
            # Find or create holding
            holding = Holding.query.filter_by(
                account_id=account.id,
                security_id=security.id
            ).first()
            
            if not holding:
                holding = Holding(
                    account_id=account.id,
                    user_id=item.user_id,
                    security_id=security.id
                )
                db.session.add(holding)
            
            # Update holding details
            holding.quantity = safe_decimal(holding_data.get('quantity', 0))
            holding.cost_basis = safe_decimal(holding_data.get('cost_basis'))
            holding.institution_price = safe_decimal(holding_data.get('institution_price', 0))
            holding.institution_value = safe_decimal(holding_data.get('institution_value', 0))
            holding.iso_currency_code = holding_data.get('iso_currency_code') or 'USD'
            
            # Calculate gain/loss
            if holding.cost_basis and holding.cost_basis > 0:
                holding.unrealized_gain_loss = holding.institution_value - holding.cost_basis
                holding.unrealized_gain_loss_percent = (
                    (holding.unrealized_gain_loss / holding.cost_basis) * 100
                )
            
            holding.last_updated = datetime.utcnow()
            holdings_synced += 1
        
        db.session.commit()
        return holdings_synced, securities_synced
    
    def _sync_security(self, sec_data: dict) -> Security:
        """Sync a single security record"""
        security = Security.query.filter_by(
            security_id=sec_data['security_id']
        ).first()
        
        if not security:
            security = Security(
                security_id=sec_data['security_id']
            )
            db.session.add(security)
        
        # Update security details
        security.ticker_symbol = sec_data.get('ticker_symbol')
        security.cusip = sec_data.get('cusip')
        security.isin = sec_data.get('isin')
        security.name = sec_data.get('name')
        security.type = safe_str(sec_data.get('type'))
        security.close_price = safe_decimal(sec_data.get('close_price'))
        security.iso_currency_code = sec_data.get('iso_currency_code') or 'USD'
        security.is_cash_equivalent = sec_data.get('is_cash_equivalent', False)
        
        return security
    
    def _sync_liabilities(self, item: PlaidItem) -> int:
        """Sync liabilities from Plaid"""
        response = self.plaid_service.get_liabilities(item.access_token)
        synced_count = 0
        
        liabilities_data = response.get('liabilities', {}) or {}
        
        # Process credit card liabilities
        for credit in liabilities_data.get('credit', []) or []:
            account = Account.query.filter_by(
                account_id=credit['account_id']
            ).first()
            
            if not account:
                continue
            
            liability = Liability.query.filter_by(
                account_id=account.id
            ).first()
            
            if not liability:
                liability = Liability(
                    account_id=account.id,
                    user_id=item.user_id,
                    type='credit'
                )
                db.session.add(liability)
            
            liability.is_overdue = credit.get('is_overdue', False)
            liability.last_payment_amount = safe_decimal(credit.get('last_payment_amount'))
            liability.last_statement_balance = safe_decimal(credit.get('last_statement_balance'))
            liability.minimum_payment_amount = safe_decimal(credit.get('minimum_payment_amount'))
            
            next_payment = credit.get('next_payment_due_date')
            if next_payment:
                if isinstance(next_payment, str):
                    liability.next_payment_due_date = datetime.strptime(next_payment, '%Y-%m-%d').date()
                else:
                    liability.next_payment_due_date = next_payment
            
            liability.last_updated = datetime.utcnow()
            synced_count += 1
        
        # Process student loan liabilities
        for loan in liabilities_data.get('student', []) or []:
            account = Account.query.filter_by(
                account_id=loan['account_id']
            ).first()
            
            if not account:
                continue
            
            liability = Liability.query.filter_by(
                account_id=account.id
            ).first()
            
            if not liability:
                liability = Liability(
                    account_id=account.id,
                    user_id=item.user_id,
                    type='student'
                )
                db.session.add(liability)
            
            liability.interest_rate_percentage = safe_decimal(loan.get('interest_rate_percentage'))
            liability.origination_principal_amount = safe_decimal(loan.get('origination_principal_amount'))
            
            orig_date = loan.get('origination_date')
            if orig_date:
                if isinstance(orig_date, str):
                    liability.origination_date = datetime.strptime(orig_date, '%Y-%m-%d').date()
                else:
                    liability.origination_date = orig_date
            
            liability.last_updated = datetime.utcnow()
            synced_count += 1
        
        # Process mortgage liabilities
        for mortgage in liabilities_data.get('mortgage', []) or []:
            account = Account.query.filter_by(
                account_id=mortgage['account_id']
            ).first()
            
            if not account:
                continue
            
            liability = Liability.query.filter_by(
                account_id=account.id
            ).first()
            
            if not liability:
                liability = Liability(
                    account_id=account.id,
                    user_id=item.user_id,
                    type='mortgage'
                )
                db.session.add(liability)
            
            liability.interest_rate_percentage = safe_decimal(mortgage.get('interest_rate_percentage'))
            liability.interest_rate_type = safe_str(mortgage.get('interest_rate_type'))
            liability.origination_principal_amount = safe_decimal(mortgage.get('origination_principal_amount'))
            
            orig_date = mortgage.get('origination_date')
            if orig_date:
                if isinstance(orig_date, str):
                    liability.origination_date = datetime.strptime(orig_date, '%Y-%m-%d').date()
                else:
                    liability.origination_date = orig_date
            
            liability.last_updated = datetime.utcnow()
            synced_count += 1
        
        db.session.commit()
        return synced_count
    
    def _create_balance_snapshot(self, account: Account):
        """Create a daily balance snapshot for an account"""
        today = date.today()
        
        # Check if we already have a snapshot for today
        existing = BalanceSnapshot.query.filter_by(
            account_id=account.id,
            snapshot_date=today
        ).first()
        
        if existing:
            # Update existing snapshot
            existing.balance_available = account.balance_available
            existing.balance_current = account.balance_current
            existing.balance_limit = account.balance_limit
        else:
            # Create new snapshot
            snapshot = BalanceSnapshot(
                account_id=account.id,
                user_id=account.user_id,
                snapshot_date=today,
                balance_available=account.balance_available,
                balance_current=account.balance_current,
                balance_limit=account.balance_limit
            )
            db.session.add(snapshot)
