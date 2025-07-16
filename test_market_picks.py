#!/usr/bin/env python3
"""
Test script to access real-time market picks from Strykr AI
Demonstrates how to get current trading recommendations from the market screener.
"""

import requests
import json
from datetime import datetime

# Your API configuration
API_KEY = "E9yGBPVF5aRukOVYT0Px4AwW"  # Your main API key
BASE_URL = "https://api.strykr.ai"

def get_current_market_picks():
    """Get the latest market screener picks."""
    
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        # Get all market screener results (most recent first)
        print("🔍 Fetching current market picks from Strykr AI...")
        response = requests.get(
            f"{BASE_URL}/api/alerts/market-screener",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            results = response.json()
            
            if results:
                # Get the most recent screener result
                latest_pick = results[0]
                print(f"✅ Successfully retrieved market picks!")
                return latest_pick
            else:
                print("📊 No market screener results found. You may need to generate them first.")
                return None
                
        elif response.status_code == 403:
            print("🔐 Authentication failed. Please check your API key.")
            return None
        else:
            print(f"❌ API request failed with status: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print("⏰ Request timed out. Please try again.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"🌐 Network error: {e}")
        return None

def display_market_picks(pick_data):
    """Display the market picks in a readable format."""
    
    if not pick_data:
        return
    
    print("\n" + "="*60)
    print("📈 STRYKR AI MARKET PICKS - REAL-TIME DATA")
    print("="*60)
    
    # Header information
    print(f"📅 Analysis Date: {pick_data['analysis_date']}")
    print(f"🕐 Generated: {pick_data['timestamp']}")
    print(f"📊 Market Sentiment: {pick_data['market_sentiment']} (Score: {pick_data['market_sentiment_score']:.2f})")
    print()
    
    # Top stocks to go LONG
    print("🟢 TOP STOCKS TO GO LONG:")
    print("-" * 40)
    if pick_data['top_stocks_long']:
        for i, stock in enumerate(pick_data['top_stocks_long'], 1):
            print(f"{i}. {stock.get('ticker', 'N/A')} - {stock.get('company_name', 'Unknown Company')}")
            print(f"   💰 Price: ${stock.get('price', 0):.2f}")
            print(f"   📈 Change: {stock.get('change_percent', 0):.2f}%")
            print(f"   🎯 Confidence: {stock.get('confidence_score', 0):.1f}%")
            print()
    else:
        print("   No long recommendations available")
    
    # Top stocks to go SHORT  
    print("🔴 TOP STOCKS TO GO SHORT:")
    print("-" * 40)
    if pick_data['top_stocks_short']:
        for i, stock in enumerate(pick_data['top_stocks_short'], 1):
            print(f"{i}. {stock.get('ticker', 'N/A')} - {stock.get('company_name', 'Unknown Company')}")
            print(f"   💰 Price: ${stock.get('price', 0):.2f}")
            print(f"   📉 Change: {stock.get('change_percent', 0):.2f}%")
            print(f"   🎯 Confidence: {stock.get('confidence_score', 0):.1f}%")
            print()
    else:
        print("   No short recommendations available")
    
    # Top cryptocurrencies to go LONG
    print("🚀 TOP CRYPTOS TO GO LONG:")
    print("-" * 40)
    if pick_data['top_cryptos_long']:
        for i, crypto in enumerate(pick_data['top_cryptos_long'], 1):
            print(f"{i}. {crypto.get('symbol', 'N/A')} - {crypto.get('name', 'Unknown Token')}")
            print(f"   💰 Price: ${crypto.get('price', 0):.4f}")
            print(f"   📈 Change: {crypto.get('change_percent', 0):.2f}%")
            if 'market_cap' in crypto:
                print(f"   🏪 Market Cap: ${crypto['market_cap']:,.0f}")
            print()
    else:
        print("   No crypto long recommendations available")
    
    # Top cryptocurrencies to go SHORT
    print("⬇️ TOP CRYPTOS TO GO SHORT:")
    print("-" * 40)
    if pick_data['top_cryptos_short']:
        for i, crypto in enumerate(pick_data['top_cryptos_short'], 1):
            print(f"{i}. {crypto.get('symbol', 'N/A')} - {crypto.get('name', 'Unknown Token')}")
            print(f"   💰 Price: ${crypto.get('price', 0):.4f}")
            print(f"   📉 Change: {crypto.get('change_percent', 0):.2f}%")
            if 'market_cap' in crypto:
                print(f"   🏪 Market Cap: ${crypto['market_cap']:,.0f}")
            print()
    else:
        print("   No crypto short recommendations available")
    
    # AI Explanation
    print("🤖 AI MARKET ANALYSIS:")
    print("-" * 40)
    print(pick_data.get('explanation', 'No explanation available'))
    print()
    
    print("="*60)

def test_backtesting_api_access():
    """Test access to backtesting API endpoints as well."""
    
    backtesting_key = "BT_9KmN3PqX8vY2ZwA5fG7H1"
    headers = {
        "X-API-Key": backtesting_key,
        "Content-Type": "application/json"
    }
    
    print("\n🔬 Testing backtesting API access...")
    
    try:
        # Test trading signals endpoint
        response = requests.get(
            f"{BASE_URL}/api/backtesting/trading-signals",
            headers=headers,
            params={"limit": 5},
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Backtesting API access confirmed!")
            signals = response.json()
            print(f"📊 Found {len(signals.get('results', []))} trading signals available")
        else:
            print(f"⚠️ Backtesting API returned status: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Backtesting API test failed: {e}")

def main():
    """Main function to run the market picks test."""
    
    print("🚀 STRYKR AI - Real-Time Market Picks Test")
    print(f"🕐 Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Get current market picks
    current_picks = get_current_market_picks()
    
    if current_picks:
        display_market_picks(current_picks)
        
        # Save to file for reference
        with open('latest_market_picks.json', 'w') as f:
            json.dump(current_picks, f, indent=2, default=str)
        print("💾 Market picks saved to 'latest_market_picks.json'")
        
    else:
        print("\n📋 No current market picks available.")
        print("To generate new picks, run:")
        print("python manage.py generate_market_screener")
    
    # Test backtesting API access
    test_backtesting_api_access()
    
    print(f"\n🏁 Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main() 