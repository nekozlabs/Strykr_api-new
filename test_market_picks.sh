#!/bin/bash

# Test script to access real-time market picks from Strykr AI
# Uses curl to test API endpoints

API_KEY="E9yGBPVF5aRukOVYT0Px4AwW"
BACKTESTING_KEY="BT_9KmN3PqX8vY2ZwA5fG7H1"
BASE_URL="https://api.strykr.ai"

echo "🚀 STRYKR AI - Real-Time Market Picks Test"
echo "🕐 Test started at: $(date)"
echo ""

echo "🔍 Testing market screener endpoint access..."

# Test 1: Get current market screener results
echo ""
echo "📊 Fetching current market picks..."
curl -X GET "${BASE_URL}/api/alerts/market-screener" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  --connect-timeout 30 \
  --max-time 60 \
  -w "\n📈 HTTP Status: %{http_code}\n" \
  -s | head -100

echo ""
echo "="*60

# Test 2: Check backtesting API access
echo ""
echo "🔬 Testing backtesting API access..."
curl -X GET "${BASE_URL}/api/backtesting/trading-signals?limit=3" \
  -H "X-API-Key: ${BACKTESTING_KEY}" \
  -H "Content-Type: application/json" \
  --connect-timeout 30 \
  --max-time 60 \
  -w "\n🎯 HTTP Status: %{http_code}\n" \
  -s | head -50

echo ""
echo "="*60

# Test 3: Check API key validity
echo ""
echo "🔐 Testing main API key with simple AI query..."
curl -X POST "${BASE_URL}/api/ai-response" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the current market sentiment?"}' \
  --connect-timeout 30 \
  --max-time 60 \
  -w "\n🤖 HTTP Status: %{http_code}\n" \
  -s | head -100

echo ""
echo "🏁 Test completed at: $(date)"
echo ""
echo "📋 Available Market Screener Endpoints:"
echo "   • GET ${BASE_URL}/api/alerts/market-screener"
echo "   • GET ${BASE_URL}/api/alerts/market-screener/{id}"
echo ""
echo "🎯 Backtesting Endpoints:"
echo "   • GET ${BASE_URL}/api/backtesting/trading-signals"
echo "   • GET ${BASE_URL}/api/backtesting/historical-data"
echo "   • GET ${BASE_URL}/api/backtesting/portfolio-snapshots"
echo ""
echo "🔑 Your API Keys:"
echo "   • Main API: ${API_KEY}"
echo "   • Backtesting: ${BACKTESTING_KEY}" 