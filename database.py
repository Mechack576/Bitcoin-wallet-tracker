"""
Database access layer for CoinTracker prototype.
Handles all database operations with connection management.
"""

import sqlite3
from datetime import datetime
from contextlib import contextmanager
from typing import List, Dict, Optional, Tuple

DB_PATH = 'cointracker.db'

@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
    finally:
        conn.close()

# Wallet operations

def create_wallet(address: str) -> int:
    """Create a new wallet entry."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO wallets (address, sync_status) VALUES (?, ?)',
            (address, 'pending')
        )
        conn.commit()
        return cursor.lastrowid

def get_wallet_by_address(address: str) -> Optional[Dict]:
    """Get wallet by Bitcoin address."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM wallets WHERE address = ?', (address,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_all_wallets() -> List[Dict]:
    """Get all wallets."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM wallets ORDER BY created_at DESC')
        return [dict(row) for row in cursor.fetchall()]

def update_wallet_balance(wallet_id: int, balance: float):
    """Update wallet balance."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE wallets SET balance = ?, last_synced = ? WHERE id = ?',
            (balance, datetime.now(), wallet_id)
        )
        conn.commit()

def update_wallet_sync_status(wallet_id: int, status: str):
    """Update wallet sync status."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE wallets SET sync_status = ? WHERE id = ?',
            (status, wallet_id)
        )
        conn.commit()

def delete_wallet(address: str) -> bool:
    """Delete a wallet and its transactions (cascade)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM wallets WHERE address = ?', (address,))
        conn.commit()
        return cursor.rowcount > 0

# Transaction operations

def create_transaction(
    wallet_id: int,
    txid: str,
    block_height: int,
    timestamp: datetime,
    value: float,
    tx_type: str
) -> Optional[int]:
    """Create a new transaction (idempotent - ignores duplicates)."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO transactions 
                   (wallet_id, txid, block_height, timestamp, value, type)
                   VALUES ()''',
                (wallet_id, txid, block_height, timestamp, value, tx_type)
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        # Transaction already exists (duplicate txid for this wallet)
        return None

def get_transactions_by_wallet(
    wallet_id: int,
    limit: int = 50,
    offset: int = 0
) -> Tuple[List[Dict], int]:
    """Get transactions for a wallet with pagination."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute(
            'SELECT COUNT(*) FROM transactions WHERE wallet_id = ?',
            (wallet_id,)
        )
        total = cursor.fetchone()[0]
        
        # Get paginated results
        cursor.execute(
            '''SELECT * FROM transactions 
               WHERE wallet_id = ? 
               ORDER BY timestamp DESC 
               LIMIT ? OFFSET ?''',
            (wallet_id, limit, offset)
        )
        transactions = [dict(row) for row in cursor.fetchall()]
        
        return transactions, total

def get_transaction_count(wallet_id: int) -> int:
    """Get total transaction count for a wallet."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT COUNT(*) FROM transactions WHERE wallet_id = ?',
            (wallet_id,)
        )
        return cursor.fetchone()[0]

def calculate_wallet_balance(wallet_id: int) -> float:
    """Calculate total balance from transactions."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Sum received transactions
        cursor.execute(
            '''SELECT COALESCE(SUM(value), 0) FROM transactions 
               WHERE wallet_id = ? AND type = 'received' ''',
            (wallet_id,)
        )
        received = cursor.fetchone()[0]
        
        # Sum sent transactions
        cursor.execute(
            '''SELECT COALESCE(SUM(value), 0) FROM transactions 
               WHERE wallet_id = ? AND type = 'sent' ''',
            (wallet_id,)
        )
        sent = cursor.fetchone()[0]
        
        return received - sent

# Sync job operations

def create_sync_job(wallet_id: int) -> int:
    """Create a new sync job."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO sync_jobs (wallet_id, status) VALUES (?, ?)',
            (wallet_id, 'queued')
        )
        conn.commit()
        return cursor.lastrowid

def update_sync_job_status(
    job_id: int,
    status: str,
    error_message: Optional[str] = None
):
    """Update sync job status."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if status == 'running':
            cursor.execute(
                'UPDATE sync_jobs SET status = ?, started_at = ? WHERE id = ?',
                (status, datetime.now(), job_id)
            )
        elif status in ('completed', 'failed'):
            cursor.execute(
                '''UPDATE sync_jobs 
                   SET status = ?, completed_at = ?, error_message = ? 
                   WHERE id = ?''',
                (status, datetime.now(), error_message, job_id)
            )
        else:
            cursor.execute(
                'UPDATE sync_jobs SET status = ? WHERE id = ?',
                (status, job_id)
            )
        
        conn.commit()

def get_sync_job(job_id: int) -> Optional[Dict]:
    """Get sync job by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sync_jobs WHERE id = ?', (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_wallet_sync_jobs(wallet_id: int, limit: int = 10) -> List[Dict]:
    """Get recent sync jobs for a wallet."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''SELECT * FROM sync_jobs 
               WHERE wallet_id = ? 
               ORDER BY created_at DESC 
               LIMIT ?''',
            (wallet_id, limit)
        )
        return [dict(row) for row in cursor.fetchall()]