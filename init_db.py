"""
Database initialization script for CoinTracker prototype.
Creates the SQLite database and all necessary tables.
"""

import sqlite3
import os

DB_PATH = 'cointracker.db'

def init_database():
    """Initialize the database with schema."""
    
    # Remove existing database if present
    if os.path.exists(DB_PATH):
        print(f"Removing existing database at {DB_PATH}")
        os.remove(DB_PATH)
    
    print(f"Creating new database at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create wallets table
    cursor.execute('''
        CREATE TABLE wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT UNIQUE NOT NULL,
            balance REAL DEFAULT 0,
            last_synced TIMESTAMP,
            sync_status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create transactions table
    cursor.execute('''
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_id INTEGER NOT NULL,
            txid TEXT NOT NULL,
            block_height INTEGER,
            timestamp TIMESTAMP,
            value REAL NOT NULL,
            type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (wallet_id) REFERENCES wallets(id) ON DELETE CASCADE,
            UNIQUE(wallet_id, txid)
        )
    ''')
    
    # Create sync_jobs table
    cursor.execute('''
        CREATE TABLE sync_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet_id INTEGER NOT NULL,
            status TEXT DEFAULT 'queued',
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (wallet_id) REFERENCES wallets(id) ON DELETE CASCADE
        )
    ''')
    
    # Create indexes for performance
    cursor.execute('CREATE INDEX idx_wallet_address ON wallets(address)')
    cursor.execute('CREATE INDEX idx_transaction_wallet ON transactions(wallet_id)')
    cursor.execute('CREATE INDEX idx_transaction_txid ON transactions(txid)')
    cursor.execute('CREATE INDEX idx_sync_jobs_wallet ON sync_jobs(wallet_id)')
    cursor.execute('CREATE INDEX idx_sync_jobs_status ON sync_jobs(status)')
    
    conn.commit()
    conn.close()
    
    print("Database initialized successfully!")
    print("\nTables created:")
    print("  - wallets")
    print("  - transactions")
    print("  - sync_jobs")
    print("\nIndexes created for optimal query performance")

if __name__ == '__main__':
    init_database()