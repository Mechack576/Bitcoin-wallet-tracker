"""
Blockchair API client for fetching Bitcoin blockchain data.
Implements error handling, retry logic, and rate limiting.
"""

import requests
import time
import random
from typing import Dict, List, Optional
from datetime import datetime

class BlockchairAPIError(Exception):
    """Custom exception for Blockchair API errors."""
    pass

class BlockchairClient:
    """Client for interacting with Blockchair Bitcoin API."""
    
    BASE_URL = "https://api.blockchair.com/bitcoin"
    MAX_RETRIES = 3
    INITIAL_BACKOFF = 1  # seconds
    MAX_BACKOFF = 10  # seconds
    REQUEST_TIMEOUT = 30  # seconds
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CoinTracker-Prototype/1.0'
        })
    
    def make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make HTTP request with exponential backoff retry logic.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            JSON response data
            
        Raises:
            BlockchairAPIError: On API errors or max retries exceeded
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.REQUEST_TIMEOUT
                )
                
                # Check for rate limiting
                if response.status_code == 429:
                    backoff = self.calculate_backoff(attempt)
                    print(f"Rate limited. Retrying in {backoff}s...")
                    time.sleep(backoff)
                    continue
                
                # Check for server errors
                if response.status_code >= 500:
                    if attempt < self.MAX_RETRIES - 1:
                        backoff = self.calculate_backoff(attempt)
                        print(f"Server error {response.status_code}. Retrying in {backoff}s...")
                        time.sleep(backoff)
                        continue
                    else:
                        raise BlockchairAPIError(
                            f"Server error after {self.MAX_RETRIES} attempts"
                        )
                
                # Raise for other HTTP errors
                response.raise_for_status()
                
                data = response.json()
                
                # Check Blockchair-specific error format
                if 'error' in data:
                    raise BlockchairAPIError(f"API error: {data['error']}")
                
                return data
                
            except requests.exceptions.Timeout:
                if attempt < self.MAX_RETRIES - 1:
                    backoff = self.calculate_backoff(attempt)
                    print(f"Request timeout. Retrying in {backoff}s...")
                    time.sleep(backoff)
                    continue
                else:
                    raise BlockchairAPIError(
                        f"Request timeout after {self.MAX_RETRIES} attempts"
                    )
                    
            except requests.exceptions.RequestException as e:
                if attempt < self.MAX_RETRIES - 1:
                    backoff = self.calculate_backoff(attempt)
                    print(f"Request error: {e}. Retrying in {backoff}s...")
                    time.sleep(backoff)
                    continue
                else:
                    raise BlockchairAPIError(
                        f"Request failed after {self.MAX_RETRIES} attempts: {e}"
                    )
        
        raise BlockchairAPIError(f"Max retries ({self.MAX_RETRIES}) exceeded")
    
    def calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff with jitter.
        
        Args:
            attempt: Current retry attempt number
            
        Returns:
            Backoff delay in seconds
        """
        backoff = min(
            self.INITIAL_BACKOFF * (2 ** attempt),
            self.MAX_BACKOFF
        )
        # Add jitter (±25%)
        jitter = backoff * 0.25 * random.uniform(-1, 1)
        return backoff + jitter
    
    def get_address_info(self, address: str) -> Dict:
        """
        Get basic information about a Bitcoin address.
        
        Args:
            address: Bitcoin address
            
        Returns:
            Address information including balance
        """
        endpoint = f"/dashboards/address/{address}"
        data = self.make_request(endpoint)
        
        if 'data' not in data or address not in data['data']:
            raise BlockchairAPIError(f"Invalid response format for address {address}")
        
        return data['data'][address]
    
    def get_address_transactions(
        self,
        address: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        Get transactions for a Bitcoin address.
        
        Args:
            address: Bitcoin address
            limit: Number of transactions to fetch (max 100)
            offset: Pagination offset
            
        Returns:
            List of transaction data
        """
        endpoint = f"/dashboards/address/{address}"
        params = {
            'limit': min(limit, 100),  # Blockchair max is 100
            'offset': offset,
            'transaction_details': 'true'
        }
        
        data = self.make_request(endpoint, params)
        
        if 'data' not in data or address not in data['data']:
            raise BlockchairAPIError(f"Invalid response format for address {address}")
        
        address_data = data['data'][address]
        transactions = address_data.get('transactions', [])
        
        return transactions
    
    def get_full_transaction_history(
        self,
        address: str,
        max_transactions: int = 10000
    ) -> List[Dict]:
        """
        Get full transaction history for an address with pagination.
        
        Args:
            address: Bitcoin address
            max_transactions: Maximum transactions to fetch (safety limit)
            
        Returns:
            List of all transactions
        """
        all_transactions = []
        offset = 0
        batch_size = 100  # Blockchair's max per request
        
        print(f"Fetching transactions for {address}...")
        
        while offset < max_transactions:
            try:
                transactions = self.get_address_transactions(
                    address,
                    limit=batch_size,
                    offset=offset
                )
                
                if not transactions:
                    break
                
                all_transactions.extend(transactions)
                offset += len(transactions)
                
                print(f"  Fetched {len(all_transactions)} transactions so far...")
                
                # If we got fewer than batch_size, we've reached the end
                if len(transactions) < batch_size:
                    break
                
                # Small delay to respect rate limits
                time.sleep(0.1)
                
            except BlockchairAPIError as e:
                print(f"Error fetching batch at offset {offset}: {e}")
                # Return what we have so far
                break
        
        print(f"Total transactions fetched: {len(all_transactions)}")
        return all_transactions
    
    def parse_transaction_for_address(
        self,
        tx: Dict,
        address: str
    ) -> Optional[Dict]:
        """
        Parse transaction data to determine value and type for a specific address.
        
        Args:
            tx: Transaction data from Blockchair
            address: The address we're tracking
            
        Returns:
            Parsed transaction dict or None if invalid
        """
        try:
            # Extract basic transaction info
            txid = tx.get('hash')
            block_height = tx.get('block_id')
            timestamp_str = tx.get('time')
            
            if not txid or not timestamp_str:
                return None
            
            # Parse timestamp
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
            # Determine transaction type and value
            balance_change = tx.get('balance_change', 0)
            
            if balance_change > 0:
                tx_type = 'received'
                value = balance_change / 100000000  # Convert satoshis to BTC
            elif balance_change < 0:
                tx_type = 'sent'
                value = abs(balance_change) / 100000000
            else:
                # No balance change for this address
                return None
            
            return {
                'txid': txid,
                'block_height': block_height,
                'timestamp': timestamp,
                'value': value,
                'type': tx_type
            }
            
        except Exception as e:
            print(f"Error parsing transaction: {e}")
            return None