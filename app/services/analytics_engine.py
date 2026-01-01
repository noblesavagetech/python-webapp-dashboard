# app/services/analytics_engine.py

from decimal import Decimal
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, and_, or_, case, desc
from collections import defaultdict
import statistics

from app import db
from app.models.financial_models import (
    Account, Transaction, Holding, Security, Liability,
    BalanceSnapshot, NetWorthSnapshot, RecurringTransaction,
    InvestmentTransaction
)


class NetWorthTracker:
    """
    Comprehensive Net Worth & Liquidity Tracking Engine
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
    
    def calculate_current_net_worth(self) -> Dict:
        """
        Calculate the current net worth with detailed breakdown
        
        Returns:
            Dict with total assets, liabilities, and net worth breakdown
        """
        # Get all active accounts included in net worth
        accounts = Account.query.filter_by(
            user_id=self.user_id,
            is_active=True,
            include_in_net_worth=True
        ).all()
        
        # Initialize totals
        total_assets = Decimal('0')
        total_liabilities = Decimal('0')
        liquid_assets = Decimal('0')
        investment_assets = Decimal('0')
        credit_card_debt = Decimal('0')
        loan_debt = Decimal('0')
        
        assets_breakdown = []
        liabilities_breakdown = []
        
        for account in accounts:
            balance = account.balance_current or Decimal('0')
            
            if account.is_asset:
                total_assets += balance
                
                if account.is_liquid:
                    liquid_assets += balance
                elif account.type == 'investment':
                    investment_assets += balance
                
                assets_breakdown.append({
                    'id': account.id,
                    'name': account.name,
                    'type': account.type,
                    'subtype': account.subtype,
                    'balance': float(balance),
                    'is_liquid': account.is_liquid
                })
            else:
                # For credit/loan accounts, balance represents debt
                debt_amount = abs(balance)
                total_liabilities += debt_amount
                
                if account.type == 'credit':
                    credit_card_debt += debt_amount
                else:
                    loan_debt += debt_amount
                
                liabilities_breakdown.append({
                    'id': account.id,
                    'name': account.name,
                    'type': account.type,
                    'subtype': account.subtype,
                    'balance': float(debt_amount)
                })
        
        # Add investment holdings value
        holdings_value = self._calculate_holdings_value()
        investment_assets += holdings_value
        total_assets += holdings_value
        
        net_worth = total_assets - total_liabilities
        
        # Calculate changes
        yesterday_snapshot = self._get_previous_snapshot(days_ago=1)
        week_ago_snapshot = self._get_previous_snapshot(days_ago=7)
        month_ago_snapshot = self._get_previous_snapshot(days_ago=30)
        
        return {
            'net_worth': float(net_worth),
            'total_assets': float(total_assets),
            'total_liabilities': float(total_liabilities),
            'liquid_assets': float(liquid_assets),
            'investment_assets': float(investment_assets),
            'credit_card_debt': float(credit_card_debt),
            'loan_debt': float(loan_debt),
            'assets_breakdown': assets_breakdown,
            'liabilities_breakdown': liabilities_breakdown,
            'changes': {
                'daily': self._calculate_change(net_worth, yesterday_snapshot),
                'weekly': self._calculate_change(net_worth, week_ago_snapshot),
                'monthly': self._calculate_change(net_worth, month_ago_snapshot)
            }
        }
    
    def _calculate_holdings_value(self) -> Decimal:
        """Calculate total value of investment holdings"""
        result = db.session.query(
            func.sum(Holding.institution_value)
        ).filter(
            Holding.user_id == self.user_id
        ).scalar()
        
        return result or Decimal('0')
    
    def _get_previous_snapshot(self, days_ago: int) -> Optional[NetWorthSnapshot]:
        """Get net worth snapshot from X days ago"""
        target_date = date.today() - timedelta(days=days_ago)
        return NetWorthSnapshot.query.filter(
            NetWorthSnapshot.user_id == self.user_id,
            NetWorthSnapshot.snapshot_date <= target_date
        ).order_by(desc(NetWorthSnapshot.snapshot_date)).first()
    
    def _calculate_change(self, current: Decimal, snapshot: Optional[NetWorthSnapshot]) -> Dict:
        """Calculate change from snapshot"""
        if not snapshot or not snapshot.net_worth:
            return {'amount': 0, 'percent': 0}
        
        previous = snapshot.net_worth
        change = current - previous
        percent = (change / abs(previous) * 100) if previous != 0 else 0
        
        return {
            'amount': float(change),
            'percent': float(percent)
        }
    
    def get_net_worth_history(self, days: int = 365) -> List[Dict]:
        """
        Get historical net worth data for charts
        
        Args:
            days: Number of days of history to retrieve
            
        Returns:
            List of daily net worth snapshots
        """
        start_date = date.today() - timedelta(days=days)
        
        snapshots = NetWorthSnapshot.query.filter(
            NetWorthSnapshot.user_id == self.user_id,
            NetWorthSnapshot.snapshot_date >= start_date
        ).order_by(NetWorthSnapshot.snapshot_date).all()
        
        return [s.to_dict() for s in snapshots]
    
    def calculate_wealth_metrics(self) -> Dict:
        """
        Calculate key wealth metrics and ratios
        
        Returns:
            Dict with various financial health metrics
        """
        current = self.calculate_current_net_worth()
        
        # Calculate key ratios
        debt_to_asset_ratio = 0
        if current['total_assets'] > 0:
            debt_to_asset_ratio = current['total_liabilities'] / current['total_assets']
        
        liquidity_ratio = 0
        if current['total_liabilities'] > 0:
            liquidity_ratio = current['liquid_assets'] / current['total_liabilities']
        
        # Investment allocation
        investment_percent = 0
        if current['total_assets'] > 0:
            investment_percent = (current['investment_assets'] / current['total_assets']) * 100
        
        return {
            'debt_to_asset_ratio': round(debt_to_asset_ratio, 3),
            'liquidity_ratio': round(liquidity_ratio, 3),
            'investment_allocation_percent': round(investment_percent, 1),
            'liquid_months': self._calculate_runway(current['liquid_assets']),
            'net_worth_trend': self._calculate_trend()
        }
    
    def _calculate_runway(self, liquid_assets: float) -> float:
        """Calculate months of runway based on average spending"""
        # Get average monthly spending
        thirty_days_ago = date.today() - timedelta(days=30)
        
        monthly_spending = db.session.query(
            func.sum(Transaction.amount)
        ).filter(
            Transaction.user_id == self.user_id,
            Transaction.date >= thirty_days_ago,
            Transaction.amount > 0,  # Expenses are positive in Plaid
            Transaction.cash_flow_type == 'expense'
        ).scalar() or 0
        
        if monthly_spending > 0:
            return round(liquid_assets / float(monthly_spending), 1)
        return 0
    
    def _calculate_trend(self) -> str:
        """Calculate net worth trend direction"""
        history = self.get_net_worth_history(days=90)
        
        if len(history) < 7:
            return 'insufficient_data'
        
        # Compare last week average to previous month average
        recent = [h['net_worth'] for h in history[-7:]]
        previous = [h['net_worth'] for h in history[-30:-7]] if len(history) > 7 else []
        
        if not previous:
            return 'stable'
        
        recent_avg = sum(recent) / len(recent)
        previous_avg = sum(previous) / len(previous)
        
        change_percent = ((recent_avg - previous_avg) / abs(previous_avg)) * 100 if previous_avg != 0 else 0
        
        if change_percent > 3:
            return 'increasing'
        elif change_percent < -3:
            return 'decreasing'
        return 'stable'
    
    def save_daily_snapshot(self) -> NetWorthSnapshot:
        """Save a daily net worth snapshot"""
        current = self.calculate_current_net_worth()
        today = date.today()
        
        # Check for existing snapshot
        existing = NetWorthSnapshot.query.filter_by(
            user_id=self.user_id,
            snapshot_date=today
        ).first()
        
        if existing:
            snapshot = existing
        else:
            snapshot = NetWorthSnapshot(
                user_id=self.user_id,
                snapshot_date=today
            )
            db.session.add(snapshot)
        
        # Update snapshot values
        snapshot.total_assets = Decimal(str(current['total_assets']))
        snapshot.liquid_assets = Decimal(str(current['liquid_assets']))
        snapshot.investment_assets = Decimal(str(current['investment_assets']))
        snapshot.total_liabilities = Decimal(str(current['total_liabilities']))
        snapshot.credit_card_debt = Decimal(str(current['credit_card_debt']))
        snapshot.loan_debt = Decimal(str(current['loan_debt']))
        snapshot.net_worth = Decimal(str(current['net_worth']))
        
        # Calculate daily change
        yesterday = self._get_previous_snapshot(days_ago=1)
        if yesterday:
            snapshot.daily_change = snapshot.net_worth - yesterday.net_worth
            if yesterday.net_worth != 0:
                snapshot.daily_change_percent = (snapshot.daily_change / abs(yesterday.net_worth)) * 100
        
        db.session.commit()
        return snapshot


class CashFlowEngine:
    """
    Operational Cash Flow Automation Engine
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
    
    def analyze_cash_flow(self, start_date: date = None, end_date: date = None) -> Dict:
        """
        Analyze cash flow for a given period
        
        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            
        Returns:
            Dict with income, expenses, and net cash flow
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()
        
        # Get all transactions in period
        transactions = Transaction.query.filter(
            Transaction.user_id == self.user_id,
            Transaction.date >= start_date,
            Transaction.date <= end_date,
            Transaction.pending == False
        ).all()
        
        total_income = Decimal('0')
        total_expenses = Decimal('0')
        income_by_category = defaultdict(Decimal)
        expenses_by_category = defaultdict(Decimal)
        daily_flow = defaultdict(lambda: {'income': Decimal('0'), 'expenses': Decimal('0')})
        
        for txn in transactions:
            amount = txn.amount or Decimal('0')
            category = txn.category_primary or 'UNCATEGORIZED'
            date_key = txn.date.isoformat()
            
            if amount < 0:  # Income (negative in Plaid)
                income_amount = abs(amount)
                total_income += income_amount
                income_by_category[category] += income_amount
                daily_flow[date_key]['income'] += income_amount
            else:  # Expense
                total_expenses += amount
                expenses_by_category[category] += amount
                daily_flow[date_key]['expenses'] += amount
        
        net_cash_flow = total_income - total_expenses
        savings_rate = 0
        if total_income > 0:
            savings_rate = float((net_cash_flow / total_income) * 100)
        
        # Convert to sorted lists for charts
        daily_data = [
            {
                'date': k,
                'income': float(v['income']),
                'expenses': float(v['expenses']),
                'net': float(v['income'] - v['expenses'])
            }
            for k, v in sorted(daily_flow.items())
        ]
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': (end_date - start_date).days + 1
            },
            'total_income': float(total_income),
            'total_expenses': float(total_expenses),
            'net_cash_flow': float(net_cash_flow),
            'savings_rate': round(savings_rate, 1),
            'income_by_category': {k: float(v) for k, v in sorted(income_by_category.items(), key=lambda x: x[1], reverse=True)},
            'expenses_by_category': {k: float(v) for k, v in sorted(expenses_by_category.items(), key=lambda x: x[1], reverse=True)},
            'daily_data': daily_data,
            'averages': {
                'daily_income': float(total_income / max((end_date - start_date).days, 1)),
                'daily_expenses': float(total_expenses / max((end_date - start_date).days, 1))
            }
        }
    
    def get_spending_insights(self) -> Dict:
        """
        Generate spending insights and recommendations
        
        Returns:
            Dict with spending insights
        """
        # Current month analysis
        today = date.today()
        month_start = today.replace(day=1)
        current_analysis = self.analyze_cash_flow(month_start, today)
        
        # Previous month for comparison
        prev_month_end = month_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        prev_analysis = self.analyze_cash_flow(prev_month_start, prev_month_end)
        
        # Find top spending categories
        top_categories = list(current_analysis['expenses_by_category'].items())[:5]
        
        # Find categories with significant increases
        increases = []
        for category, amount in current_analysis['expenses_by_category'].items():
            prev_amount = prev_analysis['expenses_by_category'].get(category, 0)
            if prev_amount > 0:
                change_percent = ((amount - prev_amount) / prev_amount) * 100
                if change_percent > 20:  # 20% increase threshold
                    increases.append({
                        'category': category,
                        'current': amount,
                        'previous': prev_amount,
                        'change_percent': round(change_percent, 1)
                    })
        
        # Calculate month-over-month changes
        expense_change = 0
        if prev_analysis['total_expenses'] > 0:
            expense_change = ((current_analysis['total_expenses'] - prev_analysis['total_expenses']) 
                            / prev_analysis['total_expenses']) * 100
        
        return {
            'top_spending_categories': [{'category': k, 'amount': v} for k, v in top_categories],
            'spending_increases': sorted(increases, key=lambda x: x['change_percent'], reverse=True)[:3],
            'month_over_month': {
                'expense_change_percent': round(expense_change, 1),
                'income_change_percent': round(
                    ((current_analysis['total_income'] - prev_analysis['total_income']) 
                     / max(prev_analysis['total_income'], 1)) * 100, 1
                ) if prev_analysis['total_income'] > 0 else 0
            },
            'current_savings_rate': current_analysis['savings_rate'],
            'recommendations': self._generate_recommendations(current_analysis, increases)
        }
    
    def _generate_recommendations(self, analysis: Dict, increases: List) -> List[str]:
        """Generate personalized spending recommendations"""
        recommendations = []
        
        if analysis['savings_rate'] < 10:
            recommendations.append("Your savings rate is below 10%. Consider reviewing discretionary spending.")
        
        if analysis['savings_rate'] >= 20:
            recommendations.append("Great job! You're saving over 20% of your income.")
        
        for increase in increases[:2]:
            recommendations.append(
                f"Spending in {increase['category']} increased by {increase['change_percent']}% this month."
            )
        
        if not recommendations:
            recommendations.append("Your spending patterns look stable this month.")
        
        return recommendations
    
    def forecast_cash_flow(self, days: int = 30) -> Dict:
        """
        Forecast future cash flow based on recurring transactions
        
        Args:
            days: Number of days to forecast
            
        Returns:
            Dict with forecasted income and expenses
        """
        recurring = RecurringTransaction.query.filter_by(
            user_id=self.user_id,
            is_active=True
        ).all()
        
        forecast_end = date.today() + timedelta(days=days)
        expected_income = Decimal('0')
        expected_expenses = Decimal('0')
        upcoming_transactions = []
        
        for stream in recurring:
            if not stream.next_expected_date:
                continue
            
            if stream.next_expected_date <= forecast_end:
                amount = stream.average_amount or Decimal('0')
                
                if stream.is_income:
                    expected_income += abs(amount)
                else:
                    expected_expenses += abs(amount)
                
                upcoming_transactions.append({
                    'description': stream.description or stream.merchant_name,
                    'amount': float(amount),
                    'is_income': stream.is_income,
                    'expected_date': stream.next_expected_date.isoformat(),
                    'frequency': stream.frequency
                })
        
        return {
            'forecast_period_days': days,
            'expected_income': float(expected_income),
            'expected_expenses': float(expected_expenses),
            'expected_net': float(expected_income - expected_expenses),
            'upcoming_transactions': sorted(
                upcoming_transactions, 
                key=lambda x: x['expected_date']
            )
        }


class PortfolioManager:
    """
    Active Portfolio Management Engine
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
    
    def get_portfolio_summary(self) -> Dict:
        """
        Get comprehensive portfolio summary
        
        Returns:
            Dict with portfolio value, allocation, and performance
        """
        holdings = db.session.query(
            Holding, Security
        ).join(
            Security, Holding.security_id == Security.id
        ).filter(
            Holding.user_id == self.user_id
        ).all()
        
        if not holdings:
            return {
                'total_value': 0,
                'total_cost_basis': 0,
                'total_gain_loss': 0,
                'total_gain_loss_percent': 0,
                'holdings': [],
                'allocation': {}
            }
        
        total_value = Decimal('0')
        total_cost = Decimal('0')
        allocation_by_type = defaultdict(Decimal)
        holdings_list = []
        
        for holding, security in holdings:
            value = holding.institution_value or Decimal('0')
            cost = holding.cost_basis or Decimal('0')
            gain_loss = value - cost
            
            total_value += value
            total_cost += cost
            
            sec_type = security.type or 'other'
            allocation_by_type[sec_type] += value
            
            holdings_list.append({
                'id': holding.id,
                'security_id': security.id,
                'ticker': security.ticker_symbol,
                'name': security.name,
                'type': security.type,
                'sector': security.sector,
                'quantity': float(holding.quantity or 0),
                'price': float(security.close_price or 0),
                'value': float(value),
                'cost_basis': float(cost),
                'gain_loss': float(gain_loss),
                'gain_loss_percent': float(holding.unrealized_gain_loss_percent or 0)
            })
        
        total_gain_loss = total_value - total_cost
        total_gain_loss_percent = (total_gain_loss / total_cost * 100) if total_cost > 0 else 0
        
        # Calculate allocation percentages
        allocation = {}
        for sec_type, value in allocation_by_type.items():
            allocation[sec_type] = {
                'value': float(value),
                'percent': float((value / total_value * 100) if total_value > 0 else 0)
            }
        
        return {
            'total_value': float(total_value),
            'total_cost_basis': float(total_cost),
            'total_gain_loss': float(total_gain_loss),
            'total_gain_loss_percent': float(total_gain_loss_percent),
            'holdings': sorted(holdings_list, key=lambda x: x['value'], reverse=True),
            'allocation': allocation,
            'holdings_count': len(holdings_list)
        }
    
    def get_investment_transactions(self, days: int = 90) -> List[Dict]:
        """
        Get recent investment transactions
        
        Args:
            days: Number of days of history
            
        Returns:
            List of investment transactions
        """
        start_date = date.today() - timedelta(days=days)
        
        transactions = db.session.query(
            InvestmentTransaction, Security
        ).outerjoin(
            Security, InvestmentTransaction.security_id == Security.id
        ).filter(
            InvestmentTransaction.user_id == self.user_id,
            InvestmentTransaction.date >= start_date
        ).order_by(desc(InvestmentTransaction.date)).all()
        
        return [{
            'id': txn.id,
            'date': txn.date.isoformat(),
            'type': txn.type,
            'subtype': txn.subtype,
            'name': txn.name,
            'ticker': security.ticker_symbol if security else None,
            'amount': float(txn.amount or 0),
            'quantity': float(txn.quantity or 0),
            'price': float(txn.price or 0)
        } for txn, security in transactions]
    
    def get_dividend_income(self, days: int = 365) -> Dict:
        """
        Calculate dividend income
        
        Args:
            days: Period for dividend calculation
            
        Returns:
            Dict with dividend income summary
        """
        start_date = date.today() - timedelta(days=days)
        
        dividends = InvestmentTransaction.query.filter(
            InvestmentTransaction.user_id == self.user_id,
            InvestmentTransaction.date >= start_date,
            InvestmentTransaction.subtype.in_(['dividend', 'qualified dividend', 'interest'])
        ).all()
        
        total_dividends = sum(abs(float(d.amount or 0)) for d in dividends)
        monthly_dividends = defaultdict(float)
        
        for div in dividends:
            month_key = div.date.strftime('%Y-%m')
            monthly_dividends[month_key] += abs(float(div.amount or 0))
        
        return {
            'total_dividend_income': total_dividends,
            'average_monthly': total_dividends / 12 if days >= 365 else total_dividends / max(days / 30, 1),
            'dividend_count': len(dividends),
            'monthly_breakdown': dict(sorted(monthly_dividends.items()))
        }
    
    def analyze_portfolio_risk(self) -> Dict:
        """
        Analyze portfolio risk and diversification
        
        Returns:
            Dict with risk metrics
        """
        summary = self.get_portfolio_summary()
        
        if not summary['holdings']:
            return {
                'diversification_score': 0,
                'concentration_risk': 'N/A',
                'sector_distribution': {},
                'recommendations': ['Add investments to begin tracking']
            }
        
        holdings = summary['holdings']
        total_value = summary['total_value']
        
        # Check concentration (top holding percentage)
        top_holding_percent = (holdings[0]['value'] / total_value * 100) if total_value > 0 else 0
        
        # Sector distribution
        sector_distribution = defaultdict(float)
        for h in holdings:
            sector = h.get('sector') or 'Unknown'
            sector_distribution[sector] += h['value']
        
        sector_percentages = {
            k: round(v / total_value * 100, 1) 
            for k, v in sector_distribution.items()
        } if total_value > 0 else {}
        
        # Calculate diversification score (simple heuristic)
        num_holdings = len(holdings)
        num_sectors = len(sector_percentages)
        
        diversification_score = min(100, (num_holdings * 5) + (num_sectors * 10))
        
        # Concentration risk assessment
        if top_holding_percent > 50:
            concentration_risk = 'High'
        elif top_holding_percent > 25:
            concentration_risk = 'Medium'
        else:
            concentration_risk = 'Low'
        
        # Generate recommendations
        recommendations = []
        if top_holding_percent > 30:
            recommendations.append(f"Consider reducing position in {holdings[0]['ticker']} (currently {round(top_holding_percent, 1)}% of portfolio)")
        
        if num_sectors < 3 and num_holdings >= 5:
            recommendations.append("Consider diversifying across more sectors")
        
        if num_holdings < 10:
            recommendations.append("Consider adding more positions for better diversification")
        
        return {
            'diversification_score': diversification_score,
            'concentration_risk': concentration_risk,
            'top_holding_percent': round(top_holding_percent, 1),
            'num_holdings': num_holdings,
            'num_sectors': num_sectors,
            'sector_distribution': sector_percentages,
            'recommendations': recommendations if recommendations else ['Portfolio diversification looks healthy']
        }
