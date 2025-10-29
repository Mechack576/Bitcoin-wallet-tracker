"""
CoinTracker Flask Application
Main API server with endpoints for wallet management and transaction tracking.
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import database as db
from sync_service import SyncService
import os
import re

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize services
sync_service = SyncService()
scheduler = BackgroundScheduler()
scheduler.start()

#Could validae Bitcoin address here but I believe Blockchair already does

# API Routes

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'CoinTracker API',
        'version': '1.0.0'
    })

# Wallet Endpoints

@app.route('/api/wallets', methods=['POST'])
def add_wallet():
    """
    Add a new Bitcoin wallet address.
    
    Request body:
        {
            "address": "bc1q..."
        }
    
    Returns:
        201: Wallet created successfully
        409: Wallet already exists
    """
    data = request.get_json()
    
    if not data or 'address' not in data:
        return jsonify({'error': 'Address is required'}), 400
    
    address = data['address'].strip()
    
    # Check if wallet already exists
    existing_wallet = db.get_wallet_by_address(address)
    if existing_wallet:
        return jsonify({
            'error': 'Wallet already exists',
            'wallet': existing_wallet
        }), 409
    
    # Create wallet
    try:
        wallet_id = db.create_wallet(address)
        wallet = db.get_wallet_by_address(address)
        
        return jsonify({
            'message': 'Wallet added successfully',
            'wallet': wallet,
            'note': 'Use POST /api/wallets/{address}/sync to fetch transactions'
        }), 201
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to create wallet',
            'details': str(e)
        }), 500

@app.route('/api/wallets', methods=['GET'])
def get_wallets():
    """
    Get all tracked wallet addresses.
    
    Returns:
        200: List of wallets
    """
    try:
        wallets = db.get_all_wallets()
        
        # Add transaction count to each wallet
        for wallet in wallets:
            wallet['transaction_count'] = db.get_transaction_count(wallet['id'])
        
        return jsonify({
            'wallets': wallets,
            'count': len(wallets)
        })
        
    except Exception as e:
        return jsonify({
            'error': 'Failed to retrieve wallets',
            'details': str(e)
        }), 500

@app.route('/api/wallets/<address>', methods=['GET'])
def get_wallet(address):
    """
    Get specific wallet details.
    
    Returns:
        200: Wallet details
        404: Wallet not found
    """
    wallet = db.get_wallet_by_address(address)
    
    if not wallet:
        return jsonify({'error': 'Wallet not found'}), 404
    
    # Add transaction count
    wallet['transaction_count'] = db.get_transaction_count(wallet['id'])
    
    return jsonify({'wallet': wallet})

@app.route('/api/wallets/<address>', methods=['DELETE'])
def delete_wallet(address):
    """
    Remove a wallet and all its transactions.
    
    Returns:
        200: Wallet deleted successfully
        404: Wallet not found
    """
    success = db.delete_wallet(address)
    
    if not success:
        return jsonify({'error': 'Wallet not found'}), 404
    
    return jsonify({
        'message': 'Wallet deleted successfully',
        'address': address
    })


# Transaction Endpoints

@app.route('/api/wallets/<address>/transactions', methods=['GET'])
def get_transactions(address):
    """
    Get transactions for a wallet address.
    
    Query parameters:
        limit: Number of transactions per page (default: 50, max: 200)
        offset: Pagination offset (default: 0)
    
    Returns:
        200: List of transactions
        404: Wallet not found
    """
    wallet = db.get_wallet_by_address(address)
    
    if not wallet:
        return jsonify({'error': 'Wallet not found'}), 404
    
    # Parse pagination parameters
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except ValueError:
        return jsonify({'error': 'Invalid pagination parameters'}), 400
    
    # Get transactions
    transactions, total = db.get_transactions_by_wallet(
        wallet['id'],
        limit=limit,
        offset=offset
    )
    
    return jsonify({
        'transactions': transactions,
        'pagination': {
            'total': total,
            'limit': limit,
            'offset': offset,
            'has_more': (offset + limit) < total
        }
    })

@app.route('/api/wallets/<address>/balance', methods=['GET'])
def get_balance(address):
    """
    Get current balance for a wallet.
    
    Returns:
        200: Balance information
        404: Wallet not found
    """
    wallet = db.get_wallet_by_address(address)
    
    if not wallet:
        return jsonify({'error': 'Wallet not found'}), 404
    
    return jsonify({
        'address': address,
        'balance': wallet['balance'],
        'balance_btc': wallet['balance'],
        'last_synced': wallet['last_synced'],
        'sync_status': wallet['sync_status']
    })

# Sync Endpoints

@app.route('/api/wallets/<address>/sync', methods=['POST'])
def sync_wallet(address):
    """
    Trigger async transaction synchronization for a wallet.
    
    Returns:
        202: Sync job started
        404: Wallet not found
        409: Sync already in progress
    """
    wallet = db.get_wallet_by_address(address)
    
    if not wallet:
        return jsonify({'error': 'Wallet not found'}), 404
    
    # Check if sync is already running
    if wallet['sync_status'] == 'syncing':
        return jsonify({
            'error': 'Sync already in progress',
            'status': wallet['sync_status']
        }), 409
    
    # Create sync job
    job_id = db.create_sync_job(wallet['id'])
    
    # Schedule async job
    scheduler.add_job(
        func=sync_service.sync_wallet,
        args=[address, job_id],
        id=f"sync_{address}_{job_id}",
        replace_existing=True
    )
    
    return jsonify({
        'message': 'Sync job started',
        'job_id': job_id,
        'address': address,
        'note': 'Use GET /api/jobs/{job_id} to check status'
    }), 202

@app.route('/api/jobs/<int:job_id>', methods=['GET'])
def get_job_status(job_id):
    """
    Get sync job status.
    
    Returns:
        200: Job status
        404: Job not found
    """
    job = db.get_sync_job(job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({'job': job})

# Error Handlers

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors."""
    return jsonify({'error': 'Method not allowed'}), 405

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({'error': 'Internal server error'}), 500

# Application Entry Point

if __name__ == '__main__':
    # Check if database exists
    if not os.path.exists('cointracker.db'):
        print("="*60)
        print("ERROR: Database not initialized!")
        print("Please run: python init_db.py")
        print("="*60)
        exit(1)
    
    print("="*60)
    print("CoinTracker API Server Starting...")
    print("="*60)
    print("\nAPI Endpoints:")
    print("  POST   /api/wallets              - Add wallet")
    print("  GET    /api/wallets              - List wallets")
    print("  GET    /api/wallets/{address}    - Get wallet")
    print("  DELETE /api/wallets/{address}    - Delete wallet")
    print("  POST   /api/wallets/{address}/sync - Sync transactions")
    print("  GET    /api/wallets/{address}/transactions - Get transactions")
    print("  GET    /api/wallets/{address}/balance - Get balance")
    print("  GET    /api/jobs/{job_id}        - Get job status")
    print("\nTest with curl commands from README.md")
    print("\n" + "="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5001)