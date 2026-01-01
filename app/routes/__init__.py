# app/routes/__init__.py

from app.routes.main_routes import main_bp
from app.routes.auth_routes import auth_bp
from app.routes.plaid_routes import plaid_bp
from app.routes.dashboard_routes import dashboard_bp

__all__ = ['main_bp', 'auth_bp', 'plaid_bp', 'dashboard_bp']
