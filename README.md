# bitcoin-wallet-tracker

# Bitcoin Wallet Tracker

A prototype system for tracking Bitcoin wallet addresses, synchronizing transactions, and viewing balances.

### High-Level Components

1. **Flask REST API Server**
   - Manages wallet addresses (add/remove)
   - Provides transaction and balance data
   - Handles async job creation for wallet synchronization

2. **Background Job Queue (APScheduler)**
   - Asynchronously syncs wallet transactions
   - Prevents blocking API requests
   - Handles rate limiting and retries

3. **SQLite Database**
   - Persists wallet addresses
   - Stores synchronized transactions
   - Tracks sync status and metadata

4. **Web UI**
   - Simple, functional interface for wallet management
   - Real-time balance and transaction viewing
   - Status indicators for sync operations

5. **External API Integration (Blockchair)**
   - Fetches Bitcoin blockchain data
   - Handles large wallets efficiently
   - Implements fallback strategies
### Database Schema

```sql
-- Wallet Addresses
CREATE TABLE wallets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT UNIQUE NOT NULL,
    balance REAL DEFAULT 0,
    last_synced TIMESTAMP,
    sync_status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Transactions
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id INTEGER NOT NULL,
    txid TEXT NOT NULL,
    block_height INTEGER,
    timestamp TIMESTAMP,
    value REAL NOT NULL,
    type TEXT NOT NULL, -- 'received' or 'sent'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_id) REFERENCES wallets(id) ON DELETE CASCADE,
    UNIQUE(wallet_id, txid)
);

-- Sync Jobs (for tracking async operations)
CREATE TABLE sync_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id INTEGER NOT NULL,
    status TEXT DEFAULT 'queued',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (wallet_id) REFERENCES wallets(id) ON DELETE CASCADE
);
```

### Data Relationships

- One wallet → Many transactions (1:N)
- One wallet → Many sync jobs (1:N)
- Transactions are idempotent (unique constraint on wallet_id + txid)

## Setup Instructions

### Prerequisites

- Python 3.8+ (tested with 3.10)
- pip
- Git

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd  CoinTrackerAssessment

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  

# Install dependencies
pip install -r requirements.txt

# Initialize database
python init_db.py

# Run the application
python app.py
```

```
Sample BTC addresses:
- [3E8ociqZa9mZUSwGdSmAEMAoAxBK3FNDcd](https://www.blockchain.com/btc/address/3E8ociqZa9mZUSwGdSmAEMAoAxBK3FNDcd)

- [bc1q0sg9rdst255gtldsmcf8rk0764avqy2h2ksqs5](https://www.blockchain.com/btc/address/bc1q0sg9rdst255gtldsmcf8rk0764avqy2h2ksqs5)

- bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h   (156,000+ transactions)

- 12xQ9k5ousS8MqNsMBqHKtjAtCuKezm2Ju (900+ transactions) belong to the same user.
```
The application will start on `http://localhost:5001`

### Quick Start (Using curl)

```bash
# 1. Add a Bitcoin address
curl -X POST http://localhost:5001/api/wallets \
  -H "Content-Type: application/json" \
  -d '{"address":"3E8ociqZa9mZUSwGdSmAEMAoAxBK3FNDcd"}'

# 2. Sync transactions (this runs in background)
curl -X POST http://localhost:5001/api/wallets/3E8ociqZa9mZUSwGdSmAEMAoAxBK3FNDcd/sync

# 2.1. Check statuc
curl http://localhost:5001/api/jobs/6


# 3. Check balance
curl http://localhost:5001/api/wallets/3E8ociqZa9mZUSwGdSmAEMAoAxBK3FNDcd/balance

# 4. View transactions
curl http://localhost:5001/api/wallets/3E8ociqZa9mZUSwGdSmAEMAoAxBK3FNDcd/transactions
```

## 📡 API Endpoints

### Wallets

**POST /api/wallets**
- Add a new Bitcoin address
- Body: `{"address": "bc1q..."}`
- Returns: Wallet object with sync status

**GET /api/wallets**
- List all tracked wallets
- Returns: Array of wallet objects

**DELETE /api/wallets/{address}**
- Remove a wallet and its transactions
- Returns: Success message

**GET /api/wallets/{address}**
- Get specific wallet details
- Returns: Wallet object with balance

### Transactions

**POST /api/wallets/{address}/sync**
- Trigger async transaction sync
- Returns: Job ID for tracking

**GET /api/wallets/{address}/transactions**
- Get all transactions for a wallet
- Query params: `?limit=50&offset=0`
- Returns: Paginated transaction list

**GET /api/wallets/{address}/balance**
- Get current wallet balance
- Returns: Balance object with BTC amount

### Jobs

**GET /api/jobs/{job_id}**
- Check sync job status
- Returns: Job status and completion info

## 🔧 Testing

### Manual API Testing (curl)

```bash
# Add a wallet
curl -X POST http://localhost:5000/api/wallets \
  -H "Content-Type: application/json" \
  -d '{"address":"3E8ociqZa9mZUSwGdSmAEMAoAxBK3FNDcd"}'

# Sync transactions
curl -X POST http://localhost:5000/api/wallets/3E8ociqZa9mZUSwGdSmAEMAoAxBK3FNDcd/sync

# Get balance
curl http://localhost:5000/api/wallets/3E8ociqZa9mZUSwGdSmAEMAoAxBK3FNDcd/balance

# Get transactions
curl http://localhost:5000/api/wallets/3E8ociqZa9mZUSwGdSmAEMAoAxBK3FNDcd/transactions

# List all wallets
curl http://localhost:5000/api/wallets

# Delete wallet
curl -X DELETE http://localhost:5000/api/wallets/3E8ociqZa9mZUSwGdSmAEMAoAxBK3FNDcd
```


## 🛡️ Error Handling & Provider API Failure Strategies

### Current Implementation

**Exponential Backoff with Jitter**
   - Retries failed API calls with increasing delays
   - Adds randomness to prevent thundering herd
   - Max retries: 3 attempts

**Rate Limiting Awareness**
   - Respects provider's rate limits (10 req/sec for Blockchair)


