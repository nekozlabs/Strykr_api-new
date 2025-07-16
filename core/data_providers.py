import logging
import json
import requests
import re
import asyncio
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, timedelta
from asgiref.sync import sync_to_async
from typing import Dict, List, Optional, Union, Any
from .api_utils import http_client

async def fetch_company_profile(ticker):
    """Fetch company profile data from FMP API."""
    cache_key = f"company_profile_{ticker}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    url = f"https://financialmodelingprep.com/stable/profile?symbol={ticker}&apikey={settings.FMP_API_KEY}"
    try:
        @sync_to_async
        def make_request():
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            return None
            
        data = await make_request()
        if data and isinstance(data, list) and len(data) > 0:
            # Extract the key fields we want for the AI chat
            profile_data = {
                "symbol": data[0].get("symbol"),
                "price": data[0].get("price"),
                "marketCap": data[0].get("marketCap"),
                "beta": data[0].get("beta"),
                "companyName": data[0].get("companyName"),
                "exchange": data[0].get("exchange"),
                "industry": data[0].get("industry"),
                "description": data[0].get("description"),
                "sector": data[0].get("sector"),
                "country": data[0].get("country"),
                "isEtf": data[0].get("isEtf", False),
                "isFund": data[0].get("isFund", False)
            }
            # Cache for 24 hours - company profiles don't change often
            cache.set(cache_key, profile_data, 86400)
            return profile_data
        return None
    except Exception as e:
        logging.error(f"Error fetching company profile for {ticker}: {str(e)}")
        return None

async def fetch_key_metrics(ticker):
    """Fetch key financial metrics from FMP API."""
    cache_key = f"key_metrics_{ticker}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    url = f"https://financialmodelingprep.com/stable/key-metrics-ttm?symbol={ticker}&apikey={settings.FMP_API_KEY}"
    try:
        @sync_to_async
        def make_request():
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            return None
            
        data = await make_request()
        if data and isinstance(data, list) and len(data) > 0:
            # Extract the most important metrics for the AI chat
            important_metrics = {
                'marketCap': data[0].get('marketCap'),
                'peRatio': data[0].get('earningsYieldTTM'),  # This is more reliable in the TTM endpoint
                'returnOnEquityTTM': data[0].get('returnOnEquityTTM'),
                'returnOnAssetsTTM': data[0].get('returnOnAssetsTTM'), 
                'debtToEquity': data[0].get('netDebtToEBITDATTM'),
                'currentRatioTTM': data[0].get('currentRatioTTM'),
                'freeCashFlowYieldTTM': data[0].get('freeCashFlowYieldTTM'),
                'researchAndDevelopementToRevenueTTM': data[0].get('researchAndDevelopementToRevenueTTM')
            }
            # Cache for 24 hours
            cache.set(cache_key, important_metrics, 86400)
            return important_metrics
        return None
    except Exception as e:
        logging.error(f"Error fetching key metrics for {ticker}: {str(e)}")
        return None

async def fetch_ticker_news(ticker):
    """Fetch news specific to a ticker from FMP API."""
    cache_key = f"ticker_news_{ticker}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    url = f"https://financialmodelingprep.com/stable/news/stock?symbols={ticker}&limit=5&apikey={settings.FMP_API_KEY}"
    try:
        @sync_to_async
        def make_request():
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            return None
            
        data = await make_request()
        if data:
            # Match the exact format in the example
            processed_news = []
            for item in data:
                processed_news.append({
                    "symbol": item.get("symbol", ""),
                    "publishedDate": item.get("publishedDate", ""),
                    "publisher": item.get("publisher", ""),
                    "title": item.get("title", ""),
                    "site": item.get("site", ""),
                    "text": item.get("text", ""),
                    "url": item.get("url", "")
                })
            # Cache for 1 hour
            cache.set(cache_key, processed_news, 3600)
            return processed_news
        return []
    except Exception as e:
        logging.error(f"Error fetching news for {ticker}: {str(e)}")
        return []

def filter_relevant_earnings(earnings_data, ticker):
    """
    Filter earnings data to only include the most relevant companies.
    
    Args:
        earnings_data: List of earnings calendar entries
        ticker: The main ticker symbol the user is querying
        
    Returns:
        Filtered list containing only relevant earnings entries
    """
    if not earnings_data:
        return []
        
    # List of major companies we always want to include if present
    MAJOR_COMPANIES = [
        "AAPL", "MSFT", "GOOG", "GOOGL", "AMZN", "META", "NVDA", "TSLA", 
        "JPM", "V", "WMT", "PG", "XOM", "JNJ", "UNH", "HD", "CVX", "LLY",
        "AVGO", "MA", "BAC", "ADBE", "ORCL", "COST", "CRM", "MRK", "AMD"
    ]
    
    # First, keep entries for the ticker being queried
    ticker_entries = [entry for entry in earnings_data if entry.get("symbol") == ticker]
    
    # Then, keep entries for major companies
    major_entries = [
        entry for entry in earnings_data 
        if entry.get("symbol") in MAJOR_COMPANIES and entry.get("symbol") != ticker
    ]
    
    # Combine and limit to 15 total entries
    filtered = ticker_entries + major_entries
    
    # Sort by date (ascending)
    filtered.sort(key=lambda x: x.get("date", ""))
    
    # Log what we're filtering
    logging.info(f"Filtered earnings data from {len(earnings_data)} to {len(filtered[:15])} entries")
    
    return filtered[:15]  # Limit to 15 entries max

async def fetch_earnings_info(ticker):
    """Fetch earnings information for a ticker."""
    cache_key = f"earnings_info_{ticker}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    # Get upcoming earnings
    from_date = timezone.now().strftime('%Y-%m-%d')
    to_date = (timezone.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    url = f"https://financialmodelingprep.com/stable/earnings-calendar?from={from_date}&to={to_date}&apikey={settings.FMP_API_KEY}"
    
    try:
        @sync_to_async
        def make_request():
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            return None
            
        data = await make_request()
        if data:
            # Process the data to match the exact format in the example
            earnings_data = []
            for item in data:
                earnings_data.append({
                    "symbol": item.get("symbol"),
                    "date": item.get("date"),
                    "epsActual": item.get("epsActual"),
                    "epsEstimated": item.get("epsEstimated"),
                    "revenueActual": item.get("revenueActual"),
                    "revenueEstimated": item.get("revenueEstimated"),
                    "lastUpdated": item.get("lastUpdated")
                })
                
            # Filter to only include relevant companies
            filtered_earnings = filter_relevant_earnings(earnings_data, ticker)
            
            # Cache for 6 hours
            cache.set(cache_key, filtered_earnings, 21600)
            return filtered_earnings
        return []
    except Exception as e:
        logging.error(f"Error fetching earnings info for {ticker}: {str(e)}")
        return []

async def fetch_sector_performance():
    """Fetch sector performance data from FMP API."""
    cache_key = "sector_performance_data"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    url = f"https://financialmodelingprep.com/stable/sector-performance?apikey={settings.FMP_API_KEY}"
    try:
        @sync_to_async
        def make_request():
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            return None
            
        data = await make_request()
        if data:
            # Cache for 3 hours - sector performance changes throughout the day
            cache.set(cache_key, data, 10800)
            return data
        return []
    except Exception as e:
        logging.error(f"Error fetching sector performance: {str(e)}")
        return []

async def fetch_market_gainers():
    """Fetch biggest market gainers from FMP API."""
    cache_key = "market_gainers_data"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    url = f"https://financialmodelingprep.com/stable/biggest-gainers?apikey={settings.FMP_API_KEY}"
    try:
        @sync_to_async
        def make_request():
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            return None
            
        data = await make_request()
        if data:
            # Process the data to match the exact format in the example
            gainers = []
            for item in data:
                gainers.append({
                    "symbol": item.get("symbol"),
                    "price": item.get("price"),
                    "name": item.get("name"),
                    "change": item.get("change"),
                    "changesPercentage": item.get("changesPercentage"),
                    "exchange": item.get("exchange")
                })
            # Cache for 1 hour - gainers can change frequently
            cache.set(cache_key, gainers[:10], 3600)  # Top 10 gainers
            return gainers[:10]
        return []
    except Exception as e:
        logging.error(f"Error fetching market gainers: {str(e)}")
        return []

async def fetch_market_losers():
    """Fetch biggest market losers from FMP API."""
    cache_key = "market_losers_data"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    url = f"https://financialmodelingprep.com/stable/biggest-losers?apikey={settings.FMP_API_KEY}"
    try:
        @sync_to_async
        def make_request():
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            return None
            
        data = await make_request()
        if data:
            # Process the data to match the exact format in the example
            losers = []
            for item in data:
                losers.append({
                    "symbol": item.get("symbol"),
                    "price": item.get("price"),
                    "name": item.get("name"),
                    "change": item.get("change"),
                    "changesPercentage": item.get("changesPercentage"),
                    "exchange": item.get("exchange")
                })
            # Cache for 1 hour - losers can change frequently
            cache.set(cache_key, losers[:10], 3600)  # Top 10 losers
            return losers[:10]
        return []
    except Exception as e:
        logging.error(f"Error fetching market losers: {str(e)}")
        return []


# ----- CoinGecko API Integration Functions -----

async def fetch_crypto_by_symbol(symbol: str, original_query: str = None) -> Optional[Dict[str, Any]]:
    """Fetch cryptocurrency data from FMP API first, then fallback to CoinGecko if not found.
    
    This is the main entrypoint for cryptocurrency lookups, trying FMP first for
    backwards compatibility, then falling back to CoinGecko for expanded coverage.
    If the original user query is provided, will also try searching CoinGecko by name.
    
    Args:
        symbol: The cryptocurrency symbol (e.g., 'BTC', 'ETH', 'DOGE')
        original_query: The original user query if available (e.g., 'magnify cash token')
        
    Returns:
        Dictionary with cryptocurrency data or None if not found
    """
    # Try FMP first for backward compatibility
    fmp_url = f"https://financialmodelingprep.com/stable/crypto?symbol={symbol}USD&apikey={settings.FMP_API_KEY}"
    cache_key = f"crypto_{symbol}"
    cached_data = cache.get(cache_key)
    
    if cached_data:
        # Add data source indicator if not present
        if "data_source" not in cached_data:
            cached_data["data_source"] = "fmp"  # Default to FMP for cached data
        return cached_data
    
    try:
        # Initialize variables
        data = None
        source = "unknown"
        
        # Try individual symbol search first, then fall back to original query
        search_results = None
        
        # First, try searching for the specific symbol
        print(f"DEBUG: Trying direct symbol search for '{symbol}'")
        try:
            search_results = await search_coins_markets(symbol)
            if search_results and search_results.get('coins'):
                print(f"DEBUG: Direct symbol search found {len(search_results.get('coins', []))} results for '{symbol}'")
                
                # Process direct symbol search results
                if 'coins' in search_results and search_results['coins']:
                    # FIXED: CoinGecko results are already sorted by market cap (highest first)
                    # Trust this sorting and take the first result for highest market cap token
                    best_match = search_results['coins'][0]
                    
                    # Log if we're skipping lower market cap tokens with same symbol
                    same_symbol_coins = [coin for coin in search_results['coins'] 
                                       if coin.get('symbol', '').upper() == symbol.upper()]
                    if len(same_symbol_coins) > 1:
                        print(f"DEBUG: Found {len(same_symbol_coins)} tokens with symbol '{symbol}', selecting highest market cap: {best_match.get('name')}")
                    
                    print(f"DEBUG: Best match for direct symbol search '{symbol}': {best_match.get('name')} ({best_match.get('symbol')}) - ID: {best_match.get('id')}")
                    
                    # Fetch full data for this coin
                    coin_data = await fetch_coingecko_crypto_data(crypto_id=best_match.get('id'))
                    if coin_data:
                        print(f"DEBUG: Successfully fetched full data for {best_match.get('name')} via direct symbol search")
                        data = coin_data
                        source = "coingecko_direct"
                        
                        # Cache results
                        cache.set(cache_key, data, 300)  # 5 minutes cache
                        logging.info(f"Fetched crypto data for '{symbol}' from direct CoinGecko search (ID: {best_match.get('id')})")
                        return data
        except Exception as e:
            print(f"DEBUG: Direct symbol search failed for '{symbol}': {str(e)}")
        
        # If direct symbol search didn't work and we have original query, try enhanced query search
        if (not search_results or not search_results.get('coins')) and original_query:
            # Clean the original query to remove conversation context
            clean_original_query = original_query.strip()
            print(f"DEBUG: Direct symbol search failed, trying enhanced CoinGecko search flow with query: '{clean_original_query}'")
            try:
                # Our enhanced search function will try multiple variations including removing "token"
                search_results = await search_coins_markets(clean_original_query)
                
                # Detailed debug output of search results
                if search_results:
                    coin_count = len(search_results.get('coins', []))
                    print(f"DEBUG: Search returned {coin_count} possible matches for '{clean_original_query}'")
                    
                    if 'coins' in search_results and search_results['coins']:
                        # Get the top matching coin
                        top_match = search_results['coins'][0]
                        print(f"DEBUG: Top match for '{clean_original_query}' via CoinGecko search: {top_match.get('name')} ({top_match.get('symbol')}) - ID: {top_match.get('id')}")
                        
                        # Additional match evaluation
                        match_score = 0
                        query_terms = set(clean_original_query.lower().split())
                        name_terms = set(top_match.get('name', '').lower().split())
                        # Remove common filler words
                        filler_words = {"token", "coin", "cryptocurrency", "crypto"}
                        query_terms = query_terms - filler_words
                        
                        # Calculate how many terms from the query appear in the coin name
                        matching_terms = query_terms.intersection(name_terms)
                        match_score = len(matching_terms) / len(query_terms) if query_terms else 0
                        print(f"DEBUG: Match score: {match_score:.2f} ({len(matching_terms)}/{len(query_terms)} terms matched)")
                        
                        # Fetch full data for this coin
                        coin_data = await fetch_coingecko_crypto_data(crypto_id=top_match.get('id'))
                        if coin_data:
                            print(f"DEBUG: Successfully fetched full data for {top_match.get('name')} via CoinGecko search")
                            data = coin_data
                            source = "coingecko_search"
                            
                            # Enhanced cache - also cache under the original symbol if it's different
                            # This helps future lookups for the same token
                            cache.set(cache_key, data, 300)  # 5 minutes cache
                            
                            # Create additional cache entry for the symbol if needed
                            symbol_cache_key = f"crypto_{top_match.get('symbol', '').upper()}"
                            if symbol_cache_key != cache_key:
                                cache.set(symbol_cache_key, data, 300)  # 5 minutes cache
                                print(f"DEBUG: Also cached data under symbol: {top_match.get('symbol', '').upper()}")
                            
                            logging.info(f"Fetched crypto data for '{clean_original_query}' from CoinGecko search (ID: {top_match.get('id')})")
                            return data
                    else:
                        print(f"DEBUG: No coins found in search results for '{clean_original_query}'")
                else:
                    print(f"DEBUG: No search results returned for '{clean_original_query}'")
            except Exception as e:
                logging.error(f"Error using CoinGecko search for '{clean_original_query}': {str(e)}")
                print(f"DEBUG: Exception when using CoinGecko search API: {type(e).__name__}: {str(e)}")
                # Continue to standard resolution flow...
        
        # Standard resolution flow: First try Financial Modeling Prep API
        response = requests.get(fmp_url)
        
        if response.status_code == 200 and response.json():
            # Process FMP data
            fmp_data = response.json()
            source = "fmp"
            try:
                data = {
                    "symbol": fmp_data[0].get("symbol", ""),
                    "name": fmp_data[0].get("name", ""),
                    "price": fmp_data[0].get("price", 0),
                    "changesPercentage": fmp_data[0].get("changesPercentage", 0),
                    "change": fmp_data[0].get("change", 0),
                    "dayLow": fmp_data[0].get("dayLow", 0),
                    "dayHigh": fmp_data[0].get("dayHigh", 0),
                    "yearHigh": fmp_data[0].get("yearHigh", 0),
                    "yearLow": fmp_data[0].get("yearLow", 0),
                    "volume": fmp_data[0].get("volume", 0),
                    "avgVolume": fmp_data[0].get("avgVolume", 0),
                    "marketCap": fmp_data[0].get("marketCap", 0),
                    "data_source": "fmp"
                }
                print(f"DEBUG: Successfully processed FMP data for {symbol}")
                
                # If we have the original query and it's multi-word, verify FMP result is relevant
                if original_query and len(original_query.split()) > 1:
                    # Use the original query directly
                    clean_original_query = original_query.strip()
                    
                    query_words = [w.lower() for w in clean_original_query.split() if len(w) > 3]  # Ignore short words
                    token_name = data.get('name', '').lower()
                    
                    # Check if any significant words from the query are in the token name
                    name_match = any(word in token_name for word in query_words)
                    if not name_match:
                        print(f"DEBUG: FMP returned '{token_name}' for '{clean_original_query}' but doesn't seem related, trying CoinGecko...")
                        # Reset data to try CoinGecko
                        data = None
            except Exception as e:
                logging.error(f"Error processing FMP data for {symbol}: {str(e)}")
                data = None
        
        # If we don't have data from FMP or it's not relevant, try CoinGecko
        if not data:
            print(f"DEBUG: FMP data not found for {symbol}, trying CoinGecko")
            try:
                # Try to use symbol-to-ID resolution in CoinGecko
                # If we have the original query, it can help with name matching
                # Normalize symbol for CoinGecko (remove USD suffix if present)
                coingecko_symbol = symbol[:-3] if symbol.endswith('USD') and len(symbol) > 3 else symbol
                print(f"DEBUG: CoinGecko fallback - normalized '{symbol}' to '{coingecko_symbol}'")
                
                # First try the symbol-based lookup
                coingecko_data = await fetch_coingecko_crypto_data(symbol=coingecko_symbol, original_query=clean_original_query if 'clean_original_query' in locals() else original_query)
                
                # If symbol lookup fails, try search API directly
                if not coingecko_data:
                    print(f"DEBUG: Symbol lookup failed for '{coingecko_symbol}', trying search API")
                    search_results = await search_coins_markets(coingecko_symbol)
                    
                    if search_results and search_results.get('coins'):
                        # Take the first search result that matches our symbol
                        for coin in search_results['coins']:
                            if coin.get('symbol', '').lower() == coingecko_symbol.lower():
                                print(f"DEBUG: Found exact symbol match in search: {coin['name']} ({coin['symbol']})")
                                coingecko_data = await fetch_coingecko_crypto_data(crypto_id=coin['id'])
                                break
                        
                        # If no exact symbol match, try the first result
                        if not coingecko_data and search_results['coins']:
                            first_result = search_results['coins'][0]
                            print(f"DEBUG: Using first search result: {first_result['name']} ({first_result['symbol']})")
                            coingecko_data = await fetch_coingecko_crypto_data(crypto_id=first_result['id'])
                
                if coingecko_data:
                    print(f"DEBUG: Found data for {symbol} via CoinGecko")
                    data = coingecko_data
                    source = "coingecko"
                else:
                    print(f"DEBUG: No data found for {symbol} via CoinGecko either")
            except Exception as e:
                logging.error(f"Error fetching CoinGecko data for {symbol}: {str(e)}")
                print(f"DEBUG: Exception when fetching CoinGecko data for {symbol}: {str(e)}")
        
        if data:
            # Cache for 5 minutes - crypto prices can change rapidly
            cache.set(cache_key, data, 300)
            logging.info(f"Fetched crypto data for {symbol} from {source}")
            return data
            
        return None
    except Exception as e:
        logging.error(f"Error fetching crypto data for {symbol}: {str(e)}")
        return None


async def fetch_coingecko_crypto_data(crypto_id: Optional[str] = None, symbol: Optional[str] = None, original_query: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fetch cryptocurrency data from CoinGecko Pro API by ID or symbol.
    
    Args:
        crypto_id: CoinGecko's internal ID for the crypto (e.g., 'bitcoin')
        symbol: Crypto symbol (e.g., 'btc')
        original_query: Original user query to help with token matching
        
    Returns:
        Dictionary with crypto data or None if not found
    """
    if not settings.COINGECKO_API_KEY:
        logging.warning("CoinGecko API key not configured")
        return None
        
    cache_key = f"coingecko_crypto_{crypto_id or symbol}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    try:
        @sync_to_async
        def make_request():
            # Set up authentication headers - support both Demo and Pro keys
            api_key = settings.COINGECKO_API_KEY
            headers = {"x-cg-pro-api-key": api_key}
            base_url = settings.COINGECKO_BASE_URL
            
            # For ID-based lookup
            if crypto_id:
                # FIXED: Try markets endpoint first (has reliable volume data)
                try:
                    markets_response = requests.get(
                        f"{base_url}/coins/markets?vs_currency=usd&ids={crypto_id}&price_change_percentage=24h", 
                        headers=headers
                    )
                    if markets_response.status_code == 200:
                        markets_data = markets_response.json()
                        if markets_data and len(markets_data) > 0:
                            # Markets endpoint has volume data - use it as primary
                            market_coin = markets_data[0]
                            
                            # Get additional metadata from coins endpoint if needed
                            try:
                                coins_response = requests.get(
                                    f"{base_url}/coins/{crypto_id}", 
                                    headers=headers
                                )
                                coins_data = coins_response.json() if coins_response.status_code == 200 else {}
                            except Exception:
                                coins_data = {}
                            
                            # Merge markets data (primary) with coins metadata
                            combined_data = {
                                'id': market_coin.get('id'),
                                'symbol': market_coin.get('symbol'),
                                'name': market_coin.get('name'),
                                'market_data': {
                                    'current_price': {'usd': market_coin.get('current_price', 0)},
                                    'price_change_percentage_24h': market_coin.get('price_change_percentage_24h', 0),
                                    'price_change_24h_in_currency': {'usd': market_coin.get('price_change_24h', 0)},
                                    'market_cap': {'usd': market_coin.get('market_cap', 0)},
                                    'total_volume': {'usd': market_coin.get('total_volume', 0)},  # This is the key fix!
                                    'ath': {'usd': market_coin.get('ath', 0)},
                                    'ath_change_percentage': {'usd': market_coin.get('ath_change_percentage', 0)},
                                    'ath_date': {'usd': market_coin.get('ath_date')},
                                    'total_supply': market_coin.get('total_supply'),
                                    'circulating_supply': market_coin.get('circulating_supply'),
                                },
                                # Add any additional metadata from coins endpoint
                                'categories': coins_data.get('categories', []),
                                'sentiment_votes_up_percentage': coins_data.get('sentiment_votes_up_percentage'),
                                'sentiment_votes_down_percentage': coins_data.get('sentiment_votes_down_percentage'),
                            }
                            volume_debug = market_coin.get('total_volume', 0)
                            logging.info(f"✅ MARKETS ENDPOINT SUCCESS: {crypto_id} - volume={volume_debug}")
                            print(f"✅ MARKETS ENDPOINT SUCCESS: {crypto_id} - volume={volume_debug}")
                            return combined_data
                except Exception as e:
                    logging.warning(f"Markets endpoint failed for {crypto_id}: {str(e)}")
                
                # Fallback to original coins endpoint
                response = requests.get(
                    f"{base_url}/coins/{crypto_id}", 
                    headers=headers
                )
            # For symbol-based lookup (needs mapping)
            elif symbol:
                # First get all coins list to find the ID
                coins_list_cache = cache.get("coingecko_coins_list")
                if coins_list_cache:
                    coins = coins_list_cache
                else:
                    coins_list = requests.get(
                        f"{base_url}/coins/list", 
                        headers=headers
                    )
                    if coins_list.status_code != 200:
                        return None
                    
                    coins = coins_list.json()
                    # Cache for 24 hours - the list rarely changes
                    cache.set("coingecko_coins_list", coins, 86400)
                
                # Find the coin ID from symbol
                # First try exact symbol match
                matching_coins = [coin for coin in coins if coin['symbol'].lower() == symbol.lower()]
                print(f"DEBUG: Exact symbol matches for '{symbol}': {len(matching_coins)}")
                
                # If we have an original query and not too many matches, use it for better matching
                if original_query and len(original_query.split()) > 1:
                    # Use the original query directly
                    clean_original_query = original_query.strip()
                    
                    # Extract significant words from the clean query
                    query_words = [w.lower() for w in clean_original_query.split() if len(w) > 3]  # Ignore short words
                    
                    # Find coins that match the query words
                    query_matches = [coin for coin in coins if any(word in coin['name'].lower() for word in query_words)]
                    
                    if query_matches:
                        print(f"DEBUG: Found {len(query_matches)} matches based on clean query '{clean_original_query}'")
                        matching_coins = query_matches
                
                # Note: We previously had a special case for 'pengu' here, but it's no longer needed
                # since our general query-based matching approach handles this and similar cases
                
                # If no exact symbol match, try partial name match
                if not matching_coins:
                    # Try to find coins where the symbol is a substring of the name
                    # Try partial name matching as a fallback option
                    print(f"DEBUG: No exact symbol match for '{symbol}', trying partial name match")
                    matching_coins = [coin for coin in coins if symbol.lower() in coin['name'].lower()]
                    print(f"DEBUG: Found {len(matching_coins)} partial name matches for '{symbol}'")
                
                if not matching_coins:
                    logging.warning(f"No matches found for symbol '{symbol}' in either symbols or names")
                    return None
                
                logging.info(f"Found {len(matching_coins)} potential matches for '{symbol}': {[coin['name'] for coin in matching_coins[:3]]}")
                
                # Try to get market data for each matching coin until we find one with data
                for match in matching_coins[:3]:  # Try top 3 matches only
                    try:
                        match_id = match['id']
                        logging.info(f"Trying to fetch market data for '{match['name']}' with ID '{match_id}'")
                        
                        response = requests.get(
                            f"{base_url}/coins/{match_id}",
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            logging.info(f"Successfully fetched data for '{match['name']}' with ID '{match_id}'")
                            return response.json()
                    except Exception as e:
                        logging.error(f"Error fetching data for match '{match['name']}': {str(e)}")
                        continue
                
                # If we tried all matches and none worked, return None
                logging.warning(f"None of the {len(matching_coins[:3])} matches for '{symbol}' returned valid market data")
                return None
            else:
                return None
                
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logging.warning(f"CoinGecko API rate limit exceeded")
                return None
            else:
                logging.warning(f"CoinGecko API returned status code {response.status_code}")
                return None
            
        data = await make_request()
        if data:
            # Transform to a consistent format that matches FMP structure for seamless integration
            formatted_data = {
                "symbol": data.get('symbol', '').upper(),
                "name": data.get('name', ''),
                "price": data.get('market_data', {}).get('current_price', {}).get('usd', 0),
                "changesPercentage": data.get('market_data', {}).get('price_change_percentage_24h', 0),
                "change": data.get('market_data', {}).get('price_change_24h_in_currency', {}).get('usd', 0),
                "marketCap": data.get('market_data', {}).get('market_cap', {}).get('usd', 0),
                "volume": data.get('market_data', {}).get('total_volume', {}).get('usd', 0),
                # Add CoinGecko-specific fields
                "data_source": "coingecko",
                "coingecko_id": data.get('id'),
                "coingecko_data": {
                    "ath": data.get('market_data', {}).get('ath', {}).get('usd', 0),
                    "ath_change_percentage": data.get('market_data', {}).get('ath_change_percentage', {}).get('usd', 0),
                    "ath_date": data.get('market_data', {}).get('ath_date', {}).get('usd'),
                    "total_supply": data.get('market_data', {}).get('total_supply'),
                    "circulating_supply": data.get('market_data', {}).get('circulating_supply'),
                    "sentiment_votes_up_percentage": data.get('sentiment_votes_up_percentage'),
                    "sentiment_votes_down_percentage": data.get('sentiment_votes_down_percentage'),
                    "categories": data.get('categories')
                }
            }
            
            # Cache for 5 minutes (CoinGecko updates frequently)
            cache.set(cache_key, formatted_data, 300)
            return formatted_data
        return None
    except Exception as e:
        logging.error(f"Error fetching CoinGecko data for {crypto_id or symbol}: {str(e)}")
        return None
        

async def search_coins_markets(query: str, limit: int = 10) -> Optional[Dict]:
    """
    Search for cryptocurrencies by name/symbol using CoinGecko API.
    
    Args:
        query: Search term (token name or symbol)
        limit: Maximum number of results to return
        
    Returns:
        Dictionary with search results or None if failed
    """
    # Clean and prepare the query
    clean_query = query.strip()
    if not clean_query:
        return None
    
    # CoinGecko-specific preprocessing: Strip USD/USDT suffixes for better matching
    # FMP uses BTCUSD format, but CoinGecko expects just BTC
    coingecko_query = clean_query
    if coingecko_query.upper().endswith('USD') and len(coingecko_query) > 3:
        # Strip USD suffix: KTAUSD -> KTA, BTCUSD -> BTC
        coingecko_query = coingecko_query[:-3]
        print(f"DEBUG: Stripped USD suffix for CoinGecko: '{clean_query}' → '{coingecko_query}'")
    elif coingecko_query.upper().endswith('USDT') and len(coingecko_query) > 4:
        # Strip USDT suffix: BTCUSDT -> BTC  
        coingecko_query = coingecko_query[:-4]
        print(f"DEBUG: Stripped USDT suffix for CoinGecko: '{clean_query}' → '{coingecko_query}'")
    
    print(f"DEBUG: CoinGecko search - original: '{query}' → processed: '{coingecko_query}'")
    
    # Smart filler removal that preserves meaningful content
    filler_words = ['token', 'coin', 'crypto', 'currency', 'the', 'a', 'an']
    query_words = coingecko_query.lower().split()
    significant_words = [word for word in query_words if word not in filler_words and len(word) > 1]
    
    if significant_words:
        refined_query = ' '.join(significant_words)
        print(f"DEBUG: Smart filler removal: '{coingecko_query}' → '{refined_query}'")
    else:
        refined_query = coingecko_query
        print(f"DEBUG: No filler words removed, keeping original: '{refined_query}'")
    
    # Try multiple query variations for better matching
    query_variations = [coingecko_query]
    if refined_query != coingecko_query:
        query_variations.append(refined_query)
    
    # Add single significant word if multi-word query
    if len(significant_words) > 1:
        query_variations.append(significant_words[0])
        print(f"DEBUG: Added single word variation: '{significant_words[0]}'")
    
    print(f"DEBUG: Will try these query variations in parallel: {query_variations}")
    
    cache_key = f"coingecko_search_{hash(query)}"
    cached_result = cache.get(cache_key)
    if cached_result:
        print(f"DEBUG: Returning cached result for '{query}' ({len(cached_result.get('coins', []))} coins)")
        return cached_result
    
    async def try_search_variation(search_term: str) -> Optional[Dict]:
        """Try a single search variation."""
        try:
            print(f"DEBUG: Trying CoinGecko API search for variation: '{search_term}'")
            
            # Use appropriate API endpoint with authentication
            api_key = settings.COINGECKO_API_KEY
            url = f"{settings.COINGECKO_BASE_URL}/search"
            headers = {
                "accept": "application/json",
                "x-cg-pro-api-key": api_key
            }
            params = {"query": search_term}
            
            # Add timeout and proper error handling
            async with asyncio.timeout(5.0):  # 5 second timeout
                response = await http_client.get(url, headers=headers, params=params)
                
                print(f"DEBUG: CoinGecko API response status: {response.status_code} for '{search_term}'")
                
                if response.status_code == 200:
                    data = response.json()
                    coins = data.get('coins', [])
                    
                    print(f"DEBUG: CoinGecko API returned {len(coins)} coins for '{search_term}'")
                    print(f"DEBUG: Full API response keys: {list(data.keys())}")
                    
                    if coins:
                        # Log first few results for debugging
                        for i, coin in enumerate(coins[:3]):
                            print(f"DEBUG: Result #{i+1}: {coin.get('name')} ({coin.get('symbol')}) - ID: {coin.get('id')} - Rank: {coin.get('market_cap_rank')}")
                        
                        return {"coins": coins[:limit]}
                    else:
                        print(f"DEBUG: No coins found in response for '{search_term}'")
                        print(f"DEBUG: Raw response: {data}")
                        return None
                elif response.status_code == 429:
                    print(f"DEBUG: Rate limited by CoinGecko API for '{search_term}'")
                    return None
                else:
                    print(f"DEBUG: CoinGecko API error {response.status_code} for '{search_term}': {response.text[:200]}")
                    return None
                    
        except asyncio.TimeoutError:
            print(f"DEBUG: CoinGecko API timeout for search term: '{search_term}'")
            return None
        except Exception as e:
            print(f"DEBUG: CoinGecko API exception for '{search_term}': {type(e).__name__}: {str(e)}")
            return None
    
    print(f"DEBUG: Starting parallel search for {len(query_variations)} variations")
    
    # Try variations in parallel, return first successful result
    tasks = [try_search_variation(variation) for variation in query_variations]
    
    try:
        # Wait for first successful result or all to complete
        for completed_task in asyncio.as_completed(tasks):
            result = await completed_task
            if result and result.get('coins'):
                print(f"DEBUG: Got successful result with {len(result.get('coins', []))} coins")
                # Cache the successful result
                cache.set(cache_key, result, 300)  # Cache for 5 minutes
                print(f"DEBUG: Cached successful result for '{query}'")
                return result
            else:
                print(f"DEBUG: Variation returned no results")
        
        print(f"DEBUG: All search variations failed for '{query}'")
        return None
        
    except Exception as e:
        print(f"DEBUG: Error in parallel search for '{query}': {type(e).__name__}: {str(e)}")
        return None


async def fetch_coin_categories() -> Optional[Dict[str, Any]]:
    """Fetch all supported cryptocurrency categories including memecoins.
    
    Returns categories with market data like volume, reserve and transaction count.
    
    Returns:
        Dictionary containing category data or None on error
    """
    if not settings.COINGECKO_API_KEY:
        logging.warning("CoinGecko API key not configured")
        return None
        
    cache_key = "coingecko_categories"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
        
    try:
        @sync_to_async
        def make_request():
            headers = {"x-cg-pro-api-key": settings.COINGECKO_API_KEY}
            
            response = requests.get(
                f"{settings.COINGECKO_BASE_URL}/onchain/categories",
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logging.warning(f"CoinGecko API rate limit exceeded")
                return None
            else:
                logging.warning(f"CoinGecko API returned status code {response.status_code}")
                return None
            
        data = await make_request()
        if data and 'data' in data:
            # Cache for 15 minutes - categories don't change often
            cache.set(cache_key, data, 900)
            return data
        return None
    except Exception as e:
        logging.error(f"Error fetching CoinGecko categories: {str(e)}")
        return None
        

async def fetch_memecoin_data() -> Optional[Dict[str, Any]]:
    """Specifically fetch memecoin category data.
    
    Returns:
        Dictionary with memecoin category information or None if not found
    """
    categories = await fetch_coin_categories()
    if not categories or 'data' not in categories:
        return None
        
    # Find the memecoin category
    memecoin_category = None
    for category in categories['data']:
        if category['id'] == 'memecoin':
            memecoin_category = category
            break
            
    return memecoin_category


async def fetch_market_data(vs_currency: str = 'usd', category: Optional[str] = None, 
                        ids: Optional[str] = None, page: int = 1, 
                        per_page: int = 50) -> Optional[List[Dict[str, Any]]]:
    """Fetch market data for coins with price, volume, market cap, etc.
    
    Args:
        vs_currency: The target currency (default: usd)
        category: Filter by category (e.g., 'memecoin')
        ids: Specific coin IDs to fetch (comma-separated)
        page: Page number for pagination
        per_page: Items per page (max 250)
        
    Returns:
        List of coins with market data or None on error
    """
    if not settings.COINGECKO_API_KEY:
        logging.warning("CoinGecko API key not configured")
        return None
        
    # Create a cache key based on parameters
    params_str = f"{vs_currency}_{category}_{ids}_{page}_{per_page}"
    cache_key = f"coingecko_markets_{params_str}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
        
    try:
        @sync_to_async
        def make_request():
            api_key = settings.COINGECKO_API_KEY
            headers = {"x-cg-pro-api-key": api_key}
            base_url = settings.COINGECKO_BASE_URL
            
            params = {
                'vs_currency': vs_currency,
                'page': page,
                'per_page': per_page,
                'price_change_percentage': '1h,24h,7d',
                'sparkline': 'true'
            }
            
            if category:
                params['category'] = category
                
            if ids:
                params['ids'] = ids
                
            response = requests.get(
                f"{base_url}/coins/markets",
                headers=headers, 
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logging.warning(f"CoinGecko API rate limit exceeded")
                return None
            else:
                logging.warning(f"CoinGecko API returned status code {response.status_code}")
                return None
            
        data = await make_request()
        if data:
            # Add data source indicator for integration
            for item in data:
                item['data_source'] = 'coingecko'
                
            # Cache for 5 minutes for market data
            cache.set(cache_key, data, 300)
            return data
        return None
    except Exception as e:
        logging.error(f"Error fetching CoinGecko market data: {str(e)}")
        return None
        

async def fetch_top_memecoins() -> Optional[List[Dict[str, Any]]]:
    """Fetch top performing memecoins.
    
    Returns:
        List of memecoin data or None on error
    """
    return await fetch_market_data(category='memecoin', per_page=20)


async def fetch_top_gainers_losers(vs_currency: str = 'usd', duration: str = '24h', 
                                top_coins: str = '1000') -> Optional[Dict[str, Any]]:
    """Fetch top gaining and losing cryptocurrencies based on price movement.
    
    Args:
        vs_currency: The target currency (default: usd)
        duration: Time period for price change (default: 24h)
        top_coins: Filter by market cap ranking (default: 1000)
        
    Returns:
        Dictionary with top_gainers and top_losers lists or None on error
    """
    if not settings.COINGECKO_API_KEY:
        logging.warning("CoinGecko API key not configured")
        return None
        
    # Create a cache key based on parameters
    cache_key = f"coingecko_gainers_losers_{vs_currency}_{duration}_{top_coins}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
        
    try:
        @sync_to_async
        def make_request():
            headers = {"x-cg-pro-api-key": settings.COINGECKO_API_KEY}
            
            params = {
                'vs_currency': vs_currency,
                'duration': duration,
                'top_coins': top_coins
            }
            
            response = requests.get(
                f"{settings.COINGECKO_BASE_URL}/coins/top_gainers_losers",
                headers=headers, 
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logging.warning(f"CoinGecko API rate limit exceeded")
                return None
            else:
                logging.warning(f"CoinGecko API returned status code {response.status_code}")
                return None
            
        data = await make_request()
        if data:
            # Add data source indicator for integration
            result = data
            if 'top_gainers' in result:
                for item in result['top_gainers']:
                    item['data_source'] = 'coingecko'
            if 'top_losers' in result:
                for item in result['top_losers']:
                    item['data_source'] = 'coingecko'
                    
            # Cache for 5 minutes (matching CoinGecko's update frequency)
            cache.set(cache_key, result, 300)
            return result
        return None
    except Exception as e:
        logging.error(f"Error fetching top gainers/losers: {str(e)}")
        return None


async def fetch_token_by_contract(asset_platform_id: str, contract_address: str) -> Optional[Dict[str, Any]]:
    """Look up a token by its contract address on a specific blockchain.
    
    Args:
        asset_platform_id: The blockchain ID (e.g., 'ethereum' for Ethereum)
        contract_address: The token's contract address
        
    Returns:
        Token data including price, market cap, etc. or None on error
    """
    if not settings.COINGECKO_API_KEY:
        logging.warning("CoinGecko API key not configured")
        return None
        
    # Sanitize the contract address
    if not re.match(r'^0x[a-fA-F0-9]{40}$', contract_address):
        logging.warning(f"Invalid contract address format: {contract_address}")
        return None
        
    cache_key = f"coingecko_contract_{asset_platform_id}_{contract_address}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
        
    try:
        @sync_to_async
        def make_request():
            headers = {"x-cg-pro-api-key": settings.COINGECKO_API_KEY}
            
            response = requests.get(
                f"{settings.COINGECKO_BASE_URL}/coins/{asset_platform_id}/contract/{contract_address}",
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logging.warning(f"CoinGecko API rate limit exceeded")
                return None
            else:
                logging.warning(f"CoinGecko API returned status code {response.status_code}")
                return None
            
        data = await make_request()
        if data:
            # Transform to consistent format
            formatted_data = {
                "symbol": data.get('symbol', '').upper(),
                "name": data.get('name', ''),
                "price": data.get('market_data', {}).get('current_price', {}).get('usd', 0),
                "changesPercentage": data.get('market_data', {}).get('price_change_percentage_24h', 0),
                "change": data.get('market_data', {}).get('price_change_24h_in_currency', {}).get('usd', 0),
                "marketCap": data.get('market_data', {}).get('market_cap', {}).get('usd', 0),
                "volume": data.get('market_data', {}).get('total_volume', {}).get('usd', 0),
                # Token-specific fields
                "data_source": "coingecko",
                "coingecko_id": data.get('id'),
                "contract_address": contract_address,
                "asset_platform": asset_platform_id,
                "token_data": {
                    "total_supply": data.get('market_data', {}).get('total_supply'),
                    "circulating_supply": data.get('market_data', {}).get('circulating_supply'),
                    "categories": data.get('categories')
                }
            }
            
            # Cache for 5 minutes
            cache.set(cache_key, formatted_data, 300)
            return formatted_data
        return None
    except Exception as e:
        logging.error(f"Error fetching token by contract: {str(e)}")
        return None


async def fetch_coin_price_by_id(coin_id: str) -> Optional[Dict[str, Any]]:
    """Fetch simple price data for a coin by CoinGecko ID.
    
    Args:
        coin_id: CoinGecko's internal ID for the coin (e.g., 'bitcoin', 'keeta')
        
    Returns:
        Dictionary with price data or None if not found
    """
    if not settings.COINGECKO_API_KEY:
        logging.warning("CoinGecko API key not configured")
        return None
        
    cache_key = f"coingecko_simple_price_{coin_id}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    try:
        @sync_to_async
        def make_request():
            headers = {"x-cg-pro-api-key": settings.COINGECKO_API_KEY}
            
            response = requests.get(
                f"{settings.COINGECKO_BASE_URL}/simple/price",
                headers=headers,
                params={
                    'ids': coin_id,
                    'vs_currencies': 'usd',
                    'include_market_cap': 'true',
                    'include_24hr_vol': 'true',
                    'include_24hr_change': 'true'
                }
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logging.warning(f"CoinGecko simple price API returned status code {response.status_code}")
                return None
        
        data = await make_request()
        if data and coin_id in data:
            price_data = data[coin_id]
            formatted_data = {
                "id": coin_id,
                "price": price_data.get('usd', 0),
                "market_cap": price_data.get('usd_market_cap', 0),
                "volume_24h": price_data.get('usd_24h_vol', 0),
                "price_change_24h_percent": price_data.get('usd_24h_change', 0),
                "data_source": "coingecko_simple"
            }
            
            # Cache for 2 minutes (simple price endpoint is lighter)
            cache.set(cache_key, formatted_data, 120)
            return formatted_data
        return None
    except Exception as e:
        logging.error(f"Error fetching simple price for {coin_id}: {str(e)}")
        return None


async def fetch_global_market_data() -> Optional[Dict[str, Any]]:
    """Fetch global cryptocurrency market data including total market cap,
    trading volume, and market dominance percentages.
    
    Returns:
        Dictionary with global market data or None on error
    """
    if not settings.COINGECKO_API_KEY:
        logging.warning("CoinGecko API key not configured")
        return None
        
    cache_key = "coingecko_global_data"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
        
    try:
        @sync_to_async
        def make_request():
            headers = {"x-cg-pro-api-key": settings.COINGECKO_API_KEY}
            
            response = requests.get(
                f"{settings.COINGECKO_BASE_URL}/global",
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logging.warning(f"CoinGecko API rate limit exceeded")
                return None
            else:
                logging.warning(f"CoinGecko API returned status code {response.status_code}")
                return None
            
        data = await make_request()
        if data and 'data' in data:
            # Add data source indicator
            data['data']['data_source'] = 'coingecko'
            
            # Cache for 10 minutes (matching CoinGecko's update frequency)
            cache.set(cache_key, data['data'], 600)
            return data['data']
        return None
    except Exception as e:
        logging.error(f"Error fetching global market data: {str(e)}")
        return None
