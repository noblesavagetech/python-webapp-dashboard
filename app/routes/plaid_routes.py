# app/routes/plaid_routes.py

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.services.plaid_service import PlaidService
from app.services.data_sync_service import DataSyncService
from app.models.financial_models import PlaidItem
from app import db

plaid_bp = Blueprint('plaid', __name__, url_prefix='/api/plaid')


@plaid_bp.route('/create-link-token', methods=['POST'])
@login_required
def create_link_token():
    """
    Create a Plaid Link token for the current user
    """
    try:
        plaid_service = PlaidService()
        response = plaid_service.create_link_token(current_user.id)
        return jsonify(response), 200
    except Exception as e:
        current_app.logger.error(f"Create link token error: {e}")
        return jsonify({'error': str(e)}), 500


@plaid_bp.route('/exchange-token', methods=['POST'])
@login_required
def exchange_token():
    """
    Exchange public token for access token after Link completion
    """
    data = request.get_json()
    public_token = data.get('public_token')
    institution = data.get('institution', {})
    
    if not public_token:
        return jsonify({'error': 'Missing public_token'}), 400
    
    try:
        plaid_service = PlaidService()
        exchange_response = plaid_service.exchange_public_token(public_token)
        
        # Create PlaidItem record
        plaid_item = PlaidItem(
            user_id=current_user.id,
            item_id=exchange_response['item_id'],
            access_token=exchange_response['access_token'],
            institution_id=institution.get('institution_id'),
            institution_name=institution.get('name'),
            status='active'
        )
        
        db.session.add(plaid_item)
        db.session.commit()
        
        # Trigger initial sync
        sync_service = DataSyncService()
        sync_result = sync_service.sync_item(plaid_item.id)
        
        return jsonify({
            'success': True,
            'item_id': plaid_item.id,
            'institution_name': plaid_item.institution_name,
            'sync_result': sync_result
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Token exchange error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@plaid_bp.route('/items', methods=['GET'])
@login_required
def get_items():
    """
    Get all linked financial institutions for current user
    """
    items = PlaidItem.query.filter_by(
        user_id=current_user.id
    ).all()
    
    return jsonify([item.to_dict() for item in items]), 200


@plaid_bp.route('/items/<item_id>', methods=['GET'])
@login_required
def get_item(item_id):
    """
    Get a specific linked institution
    """
    item = PlaidItem.query.filter_by(
        id=item_id,
        user_id=current_user.id
    ).first_or_404()
    
    return jsonify(item.to_dict()), 200


@plaid_bp.route('/items/<item_id>/sync', methods=['POST'])
@login_required
def sync_item(item_id):
    """
    Manually trigger a data sync for a specific item
    """
    item = PlaidItem.query.filter_by(
        id=item_id,
        user_id=current_user.id
    ).first_or_404()
    
    try:
        sync_service = DataSyncService()
        result = sync_service.sync_item(item.id)
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Sync error: {e}")
        return jsonify({'error': str(e)}), 500


@plaid_bp.route('/items/<item_id>', methods=['DELETE'])
@login_required
def remove_item(item_id):
    """
    Remove a linked institution
    """
    item = PlaidItem.query.filter_by(
        id=item_id,
        user_id=current_user.id
    ).first_or_404()
    
    try:
        # Remove from Plaid
        plaid_service = PlaidService()
        plaid_service.remove_item(item.access_token)
        
        # Delete from database (cascades to accounts, transactions, etc.)
        db.session.delete(item)
        db.session.commit()
        
        return jsonify({'success': True}), 200
    except Exception as e:
        current_app.logger.error(f"Remove item error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@plaid_bp.route('/sync-all', methods=['POST'])
@login_required
def sync_all_items():
    """
    Sync all linked institutions for the current user
    """
    items = PlaidItem.query.filter_by(
        user_id=current_user.id,
        status='active'
    ).all()
    
    results = []
    sync_service = DataSyncService()
    
    for item in items:
        try:
            result = sync_service.sync_item(item.id)
            results.append({
                'item_id': item.id,
                'institution_name': item.institution_name,
                'success': True,
                **result
            })
        except Exception as e:
            results.append({
                'item_id': item.id,
                'institution_name': item.institution_name,
                'success': False,
                'error': str(e)
            })
    
    return jsonify({
        'items_synced': len([r for r in results if r['success']]),
        'items_failed': len([r for r in results if not r['success']]),
        'results': results
    }), 200


@plaid_bp.route('/webhook', methods=['POST'])
def webhook():
    """
    Handle Plaid webhooks for real-time updates
    """
    data = request.get_json()
    webhook_type = data.get('webhook_type')
    webhook_code = data.get('webhook_code')
    item_id = data.get('item_id')
    
    current_app.logger.info(f"Received webhook: {webhook_type}/{webhook_code} for item {item_id}")
    
    try:
        # Find the PlaidItem
        item = PlaidItem.query.filter_by(item_id=item_id).first()
        
        if not item:
            current_app.logger.warning(f"Webhook received for unknown item: {item_id}")
            return jsonify({'received': True}), 200
        
        if webhook_type == 'TRANSACTIONS':
            if webhook_code in ['INITIAL_UPDATE', 'HISTORICAL_UPDATE', 'DEFAULT_UPDATE']:
                # Sync transactions
                sync_service = DataSyncService()
                sync_service.sync_item(item.id)
        
        elif webhook_type == 'ITEM':
            if webhook_code == 'ERROR':
                item.status = 'error'
                item.error_code = data.get('error', {}).get('error_code')
                item.error_message = data.get('error', {}).get('error_message')
                db.session.commit()
            elif webhook_code == 'PENDING_EXPIRATION':
                item.status = 'pending_expiration'
                db.session.commit()
        
        elif webhook_type == 'HOLDINGS':
            if webhook_code == 'DEFAULT_UPDATE':
                sync_service = DataSyncService()
                sync_service.sync_item(item.id)
        
        elif webhook_type == 'LIABILITIES':
            if webhook_code == 'DEFAULT_UPDATE':
                sync_service = DataSyncService()
                sync_service.sync_item(item.id)
        
        return jsonify({'received': True}), 200
        
    except Exception as e:
        current_app.logger.error(f"Webhook processing error: {e}")
        return jsonify({'received': True, 'error': str(e)}), 200
