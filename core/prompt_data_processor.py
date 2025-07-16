"""
Prompt data processor module.
Handles the preparation of all data needed for AI prompt generation.
"""

import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Any

from django.utils import timezone

from .data_providers import fetch_crypto_by_symbol


async def prepare_prompt_data(
    query: str,
    ticker_quotes: List[Dict],
    bellwether_assets_qs: List,
    economic_calendar_data: Dict,
    news_data: List,
    query_intent: Dict,
    original_query: str
) -> Dict:
    """
    Prepare all data for the AI prompt.
    
    This function handles:
    - Module 1: Ticker data formatting
    - Module 2: Bellwether assets formatting
    - Module 3: Economic calendar formatting
    - Query context and limitations
    - Crypto fallbacks and special handling
    """
    # Prepare Module 1 data for the prompt
    ticker_data_for_prompt_list = []
    if ticker_quotes:
        for ticker in ticker_quotes:
            # Create a base dictionary with standard ticker data
            ticker_dict = {
                "name": ticker["name"],
                "symbol": ticker["symbol"],
                "price": ticker["price"],
                "change": ticker.get("changesPercentage", ticker.get("changePercentage", 0)),
                "market_cap": ticker["marketCap"],
                "volume": ticker["volume"],
                "average_volume": ticker.get("avgVolume", ticker["volume"]),  # Fallback to volume if avgVolume not present
                "pe_ratio": ticker.get("pe", None),  # Fallback to None if PE not available (common for crypto)
            }
            
            # Add enhanced data if available
            # Add company profile
            if "company_profile" in ticker:
                print(f"DEBUG: Adding company profile for {ticker['symbol']}")
                ticker_dict["company_profile"] = ticker["company_profile"]
            
            # Add key metrics
            if "key_metrics" in ticker:
                print(f"DEBUG: Adding key metrics for {ticker['symbol']}")
                ticker_dict["key_metrics"] = ticker["key_metrics"]
            
            # Add recent news
            if "recent_news" in ticker:
                print(f"DEBUG: Adding recent news for {ticker['symbol']}: {len(ticker['recent_news'])} articles")
                ticker_dict["recent_news"] = ticker["recent_news"]
            
            # Add earnings info
            if "earnings_info" in ticker:
                print(f"DEBUG: Adding earnings info for {ticker['symbol']}: {len(ticker['earnings_info'])} events")
                ticker_dict["earnings_info"] = ticker["earnings_info"]
                
            # Add technical indicators if they exist
            if "technical_indicators" in ticker:
                print(f"DEBUG: Adding technical indicators for {ticker['symbol']}: {list(ticker['technical_indicators'].keys()) if ticker['technical_indicators'] else 'empty'}")
                ticker_dict["technical_indicators"] = ticker["technical_indicators"]
                
            # Add market context data to the first ticker only (since it's global data)
            if ticker_quotes.index(ticker) == 0:
                if "sector_performance" in ticker:
                    print(f"DEBUG: Adding sector performance data")
                    ticker_dict["sector_performance"] = ticker["sector_performance"]
                    
                if "market_gainers" in ticker:
                    print(f"DEBUG: Adding market gainers: {len(ticker['market_gainers'])} stocks")
                    ticker_dict["market_gainers"] = ticker["market_gainers"]
                    
                if "market_losers" in ticker:
                    print(f"DEBUG: Adding market losers: {len(ticker['market_losers'])} stocks")
                    ticker_dict["market_losers"] = ticker["market_losers"]
            
            ticker_data_for_prompt_list.append(ticker_dict)
            print(f"DEBUG: Successfully processed ticker {ticker['symbol']} for prompt data structure.")

    # CRYPTO FALLBACK: If no ticker data found but we have crypto-related tickers, try crypto-specific lookup
    tickers = []  # This should be passed in or extracted from context
    if not ticker_data_for_prompt_list and tickers:
        print(f"DEBUG: Found {len(ticker_data_for_prompt_list)} ticker data but have {len(tickers)} tickers, trying crypto fallback for: {tickers}")
        
        # Try each ticker with crypto-specific lookup
        for ticker_symbol in tickers[:10]:  # Limit to first 10 tickers to avoid overloading
            print(f"DEBUG: Attempting crypto fallback for ticker: {ticker_symbol}")
            
            # Try the crypto-specific lookup with the original query
            crypto_data = await fetch_crypto_by_symbol(ticker_symbol, original_query=original_query)
            
            if crypto_data:
                ticker_data_for_prompt_list.append({
                    "name": crypto_data.get("name", ""),
                    "symbol": crypto_data.get("symbol", ""),
                    "price": crypto_data.get("price", 0),
                    "change": crypto_data.get("changesPercentage", 0),
                    "market_cap": crypto_data.get("marketCap", 0),
                    "volume": crypto_data.get("volume", 0),
                    "average_volume": crypto_data.get("volume", 0),
                    "pe_ratio": None,  # Not applicable for crypto
                    "data_source": crypto_data.get("data_source", "unknown")
                })
                print(f"DEBUG: Crypto fallback successful for {ticker_symbol}: found {crypto_data.get('name')}")
                # Continue to try other tickers instead of breaking

    # Prepare Module 2 data for the prompt
    bellwether_assets_dict_for_prompt = {}
    if bellwether_assets_qs:  # Ensure there are assets to process
        for asset in bellwether_assets_qs:
            # Ensure the symbol is in the dictionary before adding data type specific info
            if asset.symbol not in bellwether_assets_dict_for_prompt:
                bellwether_assets_dict_for_prompt[asset.symbol] = {
                    "name": asset.name,
                    "symbol": asset.symbol,
                    "descriptors": asset.descriptors
                }
            # Now that the base dict is created (or already existed), add type-specific data
            if asset.data_type == "RSI":
                bellwether_assets_dict_for_prompt[asset.symbol]["rsi_data"] = json.dumps(
                    [{k: d[k] for k in ["date", "rsi"]} for d in asset.data[:12]],
                    indent=2,
                )
            elif asset.data_type == "EMA":  # Use elif for EMA data, correct indentation
                if asset.symbol in bellwether_assets_dict_for_prompt:  # Check again in case of sparse data
                    bellwether_assets_dict_for_prompt[asset.symbol]["ema_data"] = json.dumps(
                        [{k: d[k] for k in ["date", "ema"]} for d in asset.data[:12]],
                        indent=2,
                    )
    
    # Prepare Module 3 data for the prompt
    economic_calendar_data_for_prompt = {}
    print(f">>> DEBUG: Economic calendar data: {economic_calendar_data.keys() if isinstance(economic_calendar_data, dict) else 'not a dict'}")
    # Simplified check - if economic_calendar_data exists and is a dict, use it
    if economic_calendar_data and isinstance(economic_calendar_data, dict):
        # Add current date context
        today = timezone.now()
        today_str = today.strftime("%Y-%m-%d")
        
        # Add proper date formatting and highlight today's events
        if "week" in economic_calendar_data:
            for date_str, data in economic_calendar_data["week"].items():
                try:
                    event_date = datetime.strptime(date_str, "%Y-%m-%d")
                    data["date_display"] = event_date.strftime("%A, %B %d")
                    data["is_today"] = date_str == today_str
                except ValueError:
                    # If date parsing fails, provide default formatting
                    data["date_display"] = date_str
                    data["is_today"] = False
                    
            economic_calendar_data_for_prompt = economic_calendar_data
            print(f">>> DEBUG: Added week data to economic_calendar_data_for_prompt: {economic_calendar_data_for_prompt['week'].keys() if 'week' in economic_calendar_data_for_prompt else 'no week key'}")
        else:
            print(f">>> DEBUG: No 'week' key in economic_calendar_data")
        
        # Add minimal date context to the prompt data
        economic_calendar_data_for_prompt = {
            "current_date": today_str,
            "current_month": today.strftime("%B"),
            "current_year": today.strftime("%Y")
        }
        
        # Add week data if available
        if "week" in economic_calendar_data:
            try:
                economic_calendar_data_for_prompt["week"] = json.dumps([{
                    "date_display": data.get("date_display", ""),
                    "volatility_score": data["volatility_score"],
                    "volatility": data["volatility"],
                    "top_10_events": json.dumps(data["top_10_events"], indent=2),
                    "number_of_events": data["number_of_events"],
                    "is_today": data.get("is_today", False)
                } for date_str, data in economic_calendar_data["week"].items()], indent=2)
                print(f">>> DEBUG: Successfully added week data to prompt")
            except Exception as e:
                print(f">>> DEBUG: Error processing week data: {str(e)}")

        # Add thresholds if available
        if "thresholds" in economic_calendar_data:
            try:
                economic_calendar_data_for_prompt["thresholds"] = json.dumps([{k: v} for k, v in economic_calendar_data["thresholds"].items()], indent=2)
                print(f">>> DEBUG: Successfully added thresholds data to prompt")
            except Exception as e:
                print(f">>> DEBUG: Error processing thresholds data: {str(e)}")
        
        # Add current date context
        economic_calendar_data_for_prompt["current_date"] = today.strftime("%Y-%m-%d")
        economic_calendar_data_for_prompt["current_month"] = today.strftime("%B")
        economic_calendar_data_for_prompt["current_year"] = today.strftime("%Y")

    # Initialize query_context to track data limitations
    query_context = {}
    
    # Check if we have a ticker-related query with no valid ticker data
    ticker_terms = ['price', 'stock', 'ticker', 'coin', 'crypto', 'eth', 'btc', 'technical', 'rsi', 'ema', 'sma', 'dema']
    has_ticker_terms = any(term in query.lower() for term in ticker_terms)
    
    # Check if this is a cryptocurrency-specific query
    crypto_terms = ['crypto', 'coin', 'token', 'eth', 'btc', 'blockchain', 'memecoin', 'bitcoin', 'ethereum']
    contract_pattern = re.compile(r'0x[a-fA-F0-9]{40}')
    has_contract_address = bool(contract_pattern.search(query))
    
    # Extract potential token names/symbols for detection
    potential_token_words = re.findall(r'\b([A-Za-z0-9]{2,8})\b', query)
    
    # Always consider queries with short words (2-8 chars) as potentially crypto-related
    # This helps catch cases like "Pengu" without requiring "token" or other keywords
    is_crypto_query = any(term in query.lower() for term in crypto_terms) or has_contract_address or any(len(word) >= 2 and len(word) <= 8 for word in potential_token_words)
    
    # Check if this is a memecoin query
    memecoin_terms = ['memecoin', 'meme coin', 'meme token', 'doge', 'shib', 'pepe']
    is_memecoin_query = any(term in query.lower() for term in memecoin_terms)
    
    # Return the prepared data
    return {
        "ticker_data": ticker_data_for_prompt_list,
        "bellwether_assets": list(bellwether_assets_dict_for_prompt.values()),
        "economic_calendar": economic_calendar_data_for_prompt,
        "news_data": news_data,
        "query_context": query_context,
        "is_crypto_query": is_crypto_query,
        "is_memecoin_query": is_memecoin_query,
        "has_contract_address": has_contract_address,
        "has_ticker_terms": has_ticker_terms
    } 