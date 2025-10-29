#!/bin/bash
# CoinTracker API Test Script
# This script demonstrates all the API endpoints using curl

echo "============================================"
echo "CoinTracker API Test Script"
echo "============================================"
echo ""

BASE_URL="http://localhost:5001"
TEST_ADDRESS="3E8ociqZa9mZUSwGdSmAEMAoAxBK3FNDcd"

echo "1. Health Check"
echo "----------------"
curl -s ${BASE_URL}/api/health | python3 -m json.tool
echo ""
echo ""

echo "2. Add a Bitcoin Wallet"
echo "----------------"
curl -s -X POST ${BASE_URL}/api/wallets \
  -H "Content-Type: application/json" \
  -d "{\"address\":\"${TEST_ADDRESS}\"}" | python3 -m json.tool
echo ""
echo ""

echo "3. List All Wallets"
echo "----------------"
curl -s ${BASE_URL}/api/wallets | python3 -m json.tool
echo ""
echo ""

echo "4. Get Specific Wallet"
echo "----------------"
curl -s ${BASE_URL}/api/wallets/${TEST_ADDRESS} | python3 -m json.tool
echo ""
echo ""

echo "5. Start Sync (Background Job)"
echo "----------------"
curl -s -X POST ${BASE_URL}/api/wallets/${TEST_ADDRESS}/sync | python3 -m json.tool
echo ""
echo ""

echo "Waiting 10 seconds for sync to complete..."
sleep 10
echo ""

echo "6. Get Balance"
echo "----------------"
curl -s ${BASE_URL}/api/wallets/${TEST_ADDRESS}/balance | python3 -m json.tool
echo ""
echo ""

echo "7. Get Transactions (first 10)"
echo "----------------"
curl -s "${BASE_URL}/api/wallets/${TEST_ADDRESS}/transactions?limit=10" | python3 -m json.tool
echo ""
echo ""

echo "8. Get Wallet Again (with updated data)"
echo "----------------"
curl -s ${BASE_URL}/api/wallets/${TEST_ADDRESS} | python3 -m json.tool
echo ""
echo ""

echo "============================================"
echo "Test Complete!"
echo "============================================"