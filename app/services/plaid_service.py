# app/services/plaid_service.py

import plaid
from plaid.api import plaid_api
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from plaid.model.investments_holdings_get_request import InvestmentsHoldingsGetRequest
from plaid.model.investments_transactions_get_request import InvestmentsTransactionsGetRequest
from plaid.model.liabilities_get_request import LiabilitiesGetRequest
from plaid.model.item_remove_request import ItemRemoveRequest
from flask import current_app
from datetime import datetime, timedelta
import os


class PlaidService:
    """
    Core Plaid integration service handling all API communications
    """
    
    def __init__(self):
        """Initialize Plaid client with environment configuration"""
        self.client_id = os.environ.get('PLAID_CLIENT_ID')
        self.secret = os.environ.get('PLAID_SECRET')
        self.env = os.environ.get('PLAID_ENV', 'sandbox')
        
        # Configure Plaid environment
        if self.env == 'sandbox':
            host = plaid.Environment.Sandbox
        elif self.env == 'development':
            host = plaid.Environment.Development
        else:
            host = plaid.Environment.Production
        
        configuration = plaid.Configuration(
            host=host,
            api_key={
                'clientId': self.client_id,
                'secret': self.secret,
            }
        )
        
        api_client = plaid.ApiClient(configuration)
        self.client = plaid_api.PlaidApi(api_client)
    
    def create_link_token(self, user_id: str) -> dict:
        """
        Create a Link token for initializing Plaid Link
        
        For Sandbox testing:
        1. Select any test bank (e.g., "First Platypus Bank")
        2. Enter credentials: user_good / pass_good
        3. Phone number (if prompted): 415-555-0010
        4. OTP code (if prompted): 123456
        
        Args:
            user_id: The unique identifier for the user
            
        Returns:
            dict containing link_token and expiration
        """
        try:
            # For sandbox, use simple products that work with all test institutions
            # Only use 'auth' and 'transactions' for basic sandbox testing
            # 'investments' and 'liabilities' require specific test institutions
            request = LinkTokenCreateRequest(
                user=LinkTokenCreateRequestUser(client_user_id=user_id),
                client_name="Financial Dashboard",
                products=[
                    Products("auth"),
                    Products("transactions"),
                ],
                country_codes=[CountryCode("US")],
                language="en",
                # NOTE: Do NOT set redirect_uri for sandbox credential-based flow
                # Setting redirect_uri triggers OAuth flow which asks for phone first
            )
            
            response = self.client.link_token_create(request)
            
            current_app.logger.info(f"Link token created successfully for user {user_id}")
            return response.to_dict()
            
        except plaid.ApiException as e:
            current_app.logger.error(f"Plaid API error creating link token: {e.body}")
            raise Exception(f"Failed to create Plaid link token: {e.body}")
    
    def exchange_public_token(self, public_token: str) -> dict:
        """
        Exchange a public token for an access token
        
        Args:
            public_token: The public token from Plaid Link
            
        Returns:
            dict containing access_token and item_id
        """
        try:
            request = ItemPublicTokenExchangeRequest(public_token=public_token)
            response = self.client.item_public_token_exchange(request)
            
            return {
                'access_token': response['access_token'],
                'item_id': response['item_id'],
                'request_id': response['request_id']
            }
        except plaid.ApiException as e:
            current_app.logger.error(f"Plaid token exchange error: {e}")
            raise Exception(f"Failed to exchange token: {str(e)}")
    
    def get_accounts_balance(self, access_token: str) -> dict:
        """
        Get real-time account balances
        
        Args:
            access_token: The Plaid access token for the item
            
        Returns:
            dict containing accounts list with balance information
        """
        try:
            request = AccountsBalanceGetRequest(access_token=access_token)
            response = self.client.accounts_balance_get(request)
            
            return {
                'accounts': response['accounts'],
                'item': response['item'],
                'request_id': response['request_id']
            }
        except plaid.ApiException as e:
            current_app.logger.error(f"Plaid balance error: {e}")
            raise Exception(f"Failed to get balances: {str(e)}")
    
    def get_transactions(self, access_token: str, start_date: datetime = None, 
                         end_date: datetime = None, count: int = 500) -> dict:
        """
        Fetch transactions for an item
        
        Args:
            access_token: The Plaid access token
            start_date: Start date for transaction fetch (default: 30 days ago)
            end_date: End date for transaction fetch (default: today)
            count: Maximum number of transactions per request
            
        Returns:
            dict containing transactions, accounts, and pagination info
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.now()
        
        try:
            all_transactions = []
            has_more = True
            offset = 0
            
            while has_more:
                request = TransactionsGetRequest(
                    access_token=access_token,
                    start_date=start_date.date(),
                    end_date=end_date.date(),
                    options=TransactionsGetRequestOptions(
                        count=count,
                        offset=offset
                    )
                )
                
                response = self.client.transactions_get(request)
                all_transactions.extend(response['transactions'])
                
                has_more = len(all_transactions) < response['total_transactions']
                offset = len(all_transactions)
            
            return {
                'transactions': all_transactions,
                'accounts': response['accounts'],
                'total_transactions': response['total_transactions'],
                'request_id': response['request_id']
            }
        except plaid.ApiException as e:
            current_app.logger.error(f"Plaid transactions error: {e}")
            raise Exception(f"Failed to get transactions: {str(e)}")
    
    def get_investments_holdings(self, access_token: str) -> dict:
        """
        Get investment holdings for an item
        
        Args:
            access_token: The Plaid access token
            
        Returns:
            dict containing holdings, securities, and accounts
        """
        try:
            request = InvestmentsHoldingsGetRequest(access_token=access_token)
            response = self.client.investments_holdings_get(request)
            
            return {
                'holdings': response['holdings'],
                'securities': response['securities'],
                'accounts': response['accounts'],
                'request_id': response['request_id']
            }
        except plaid.ApiException as e:
            current_app.logger.error(f"Plaid investments holdings error: {e}")
            raise Exception(f"Failed to get investment holdings: {str(e)}")
    
    def get_investments_transactions(self, access_token: str, 
                                      start_date: datetime = None,
                                      end_date: datetime = None) -> dict:
        """
        Get investment transactions for an item
        
        Args:
            access_token: The Plaid access token
            start_date: Start date (default: 90 days ago)
            end_date: End date (default: today)
            
        Returns:
            dict containing investment transactions and securities
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=90)
        if end_date is None:
            end_date = datetime.now()
        
        try:
            request = InvestmentsTransactionsGetRequest(
                access_token=access_token,
                start_date=start_date.date(),
                end_date=end_date.date()
            )
            response = self.client.investments_transactions_get(request)
            
            return {
                'investment_transactions': response['investment_transactions'],
                'securities': response['securities'],
                'accounts': response['accounts'],
                'total_investment_transactions': response['total_investment_transactions'],
                'request_id': response['request_id']
            }
        except plaid.ApiException as e:
            current_app.logger.error(f"Plaid investment transactions error: {e}")
            raise Exception(f"Failed to get investment transactions: {str(e)}")
    
    def get_liabilities(self, access_token: str) -> dict:
        """
        Get liability information (credit cards, loans, mortgages)
        
        Args:
            access_token: The Plaid access token
            
        Returns:
            dict containing liabilities by type
        """
        try:
            request = LiabilitiesGetRequest(access_token=access_token)
            response = self.client.liabilities_get(request)
            
            return {
                'liabilities': response['liabilities'],
                'accounts': response['accounts'],
                'request_id': response['request_id']
            }
        except plaid.ApiException as e:
            current_app.logger.error(f"Plaid liabilities error: {e}")
            raise Exception(f"Failed to get liabilities: {str(e)}")
    
    def remove_item(self, access_token: str) -> dict:
        """
        Remove an item from Plaid (unlink institution)
        
        Args:
            access_token: The Plaid access token
            
        Returns:
            dict with removal confirmation
        """
        try:
            request = ItemRemoveRequest(access_token=access_token)
            response = self.client.item_remove(request)
            
            return {
                'removed': True,
                'request_id': response['request_id']
            }
        except plaid.ApiException as e:
            current_app.logger.error(f"Plaid item remove error: {e}")
            raise Exception(f"Failed to remove item: {str(e)}")
