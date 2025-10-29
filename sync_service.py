"""
Wallet synchronization service.
Handles async background jobs for fetching and storing blockchain data.
"""

from typing import Optional
import database as db
from blockchair_client import BlockchairClient, BlockchairAPIError
from datetime import datetime

class SyncService:
    """Service for synchronizing wallet transactions."""
    
    def __init__(self):
        self.client = BlockchairClient()
    
    def sync_wallet(self, wallet_address: str, job_id: Optional[int] = None):
        """
        Synchronize transactions for a wallet address.
        
        Args:
            wallet_address: Bitcoin address to sync
            job_id: Optional sync job ID for tracking
        """
        print(f"\n{'='*60}")
        print(f"Starting sync for wallet: {wallet_address}")
        print(f"Job ID: {job_id}")
        print(f"{'='*60}\n")
        
        # Get wallet from database
        wallet = db.get_wallet_by_address(wallet_address)
        if not wallet:
            error_msg = f"Wallet not found: {wallet_address}"
            print(f"ERROR: {error_msg}")
            if job_id:
                db.update_sync_job_status(job_id, 'failed', error_msg)
            return
        
        wallet_id = wallet['id']
        
        # Update job status to running
        if job_id:
            db.update_sync_job_status(job_id, 'running')
        
        # Update wallet sync status
        db.update_wallet_sync_status(wallet_id, 'syncing')
        
        try:
            # Fetch address info and transactions from Blockchair
            print(f"Fetching address info from Blockchair...")
            address_info = self.client.get_address_info(wallet_address)
            
            # Get current balance from API
            api_balance = address_info.get('address', {}).get('balance', 0) / 100000000  # satoshis to BTC
            print(f"Current balance from API: {api_balance} BTC")
            
            # Get transaction count
            tx_count = address_info.get('address', {}).get('transaction_count', 0)
            print(f"Total transactions: {tx_count}")
            
            # Determine how many transactions to fetch
            max_to_fetch = min(tx_count, 10000)  # Safety limit
            if tx_count > 10000:
                print(f"WARNING: Address has {tx_count} transactions. Fetching first {max_to_fetch} only.")
            
            # Fetch all transactions
            transactions = self.client.get_full_transaction_history(
                wallet_address,
                max_transactions=max_to_fetch
            )
            
            print(f"\nProcessing {len(transactions)} transactions...")
            
            # Store transactions in database
            stored_count = 0
            duplicate_count = 0
            error_count = 0
            
            for tx in transactions:
                parsed_tx = self.client.parse_transaction_for_address(tx, wallet_address)
                
                if parsed_tx:
                    result = db.create_transaction(
                        wallet_id=wallet_id,
                        txid=parsed_tx['txid'],
                        block_height=parsed_tx['block_height'],
                        timestamp=parsed_tx['timestamp'],
                        value=parsed_tx['value'],
                        tx_type=parsed_tx['type']
                    )
                    
                    if result:
                        stored_count += 1
                    else:
                        duplicate_count += 1
                else:
                    error_count += 1
            
            print(f"\nTransaction processing complete:")
            print(f"  - Stored: {stored_count}")
            print(f"  - Duplicates: {duplicate_count}")
            print(f"  - Errors: {error_count}")
            
            # Calculate balance from our stored transactions
            calculated_balance = db.calculate_wallet_balance(wallet_id)
            print(f"  - Calculated balance: {calculated_balance} BTC")
            
            # Update wallet with final balance
            db.update_wallet_balance(wallet_id, calculated_balance)
            db.update_wallet_sync_status(wallet_id, 'synced')
            
            # Mark job as completed
            if job_id:
                db.update_sync_job_status(job_id, 'completed')
            
            print(f"\n{'='*60}")
            print(f"Sync completed successfully for {wallet_address}")
            print(f"{'='*60}\n")
            
        except BlockchairAPIError as e:
            error_msg = f"Blockchair API error: {str(e)}"
            print(f"\nERROR: {error_msg}\n")
            
            db.update_wallet_sync_status(wallet_id, 'error')
            if job_id:
                db.update_sync_job_status(job_id, 'failed', error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"\nERROR: {error_msg}\n")
            
            db.update_wallet_sync_status(wallet_id, 'error')
            if job_id:
                db.update_sync_job_status(job_id, 'failed', error_msg)
    
    def quick_balance_check(self, wallet_address: str) -> float:
        """
        Quick balance check without full sync.
        
        Args:
            wallet_address: Bitcoin address
            
        Returns:
            Current balance in BTC
        """
        try:
            address_info = self.client.get_address_info(wallet_address)
            balance = address_info.get('address', {}).get('balance', 0) / 100000000
            return balance
        except BlockchairAPIError as e:
            print(f"Error checking balance: {e}")
            return 0.0