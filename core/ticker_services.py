"""
Ticker-related services for fetching and processing asset data.
This module handles all ticker operations including validation, quotes, and technical indicators.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from difflib import SequenceMatcher

from django.conf import settings
from django.core.cache import cache

from .api_utils import http_client
from .data_providers import (
    fetch_company_profile,
    fetch_key_metrics,
    fetch_ticker_news,
    fetch_earnings_info,
    fetch_sector_performance,
    fetch_market_gainers,
    fetch_market_losers,
    fetch_crypto_by_symbol,
)

# StrykrScreener-inspired network mappings and optimizations
NETWORK_CHAIN_MAPPING = {
    # Input variations → standardized chain name
    'eth': 'ethereum',
    'ethereum': 'ethereum',
    'mainnet': 'ethereum',
    'bsc': 'binance-smart-chain',
    'bnb': 'binance-smart-chain',
    'binance': 'binance-smart-chain',
    'polygon': 'polygon-pos',
    'matic': 'polygon-pos',
    'arbitrum': 'arbitrum-one',
    'arb': 'arbitrum-one',
    'optimism': 'optimistic-ethereum',
    'op': 'optimistic-ethereum',
    'base': 'base',
    'solana': 'solana',
    'sol': 'solana',
    'avalanche': 'avalanche',
    'avax': 'avalanche'
}

# Network-specific timeout settings (inspired by StrykrScreener)
NETWORK_TIMEOUT_SETTINGS = {
    'ethereum': {'timeout': 5.0, 'priority': 1},
    'binance-smart-chain': {'timeout': 4.0, 'priority': 2},
    'polygon-pos': {'timeout': 4.0, 'priority': 3},
    'arbitrum-one': {'timeout': 6.0, 'priority': 4},
    'optimistic-ethereum': {'timeout': 6.0, 'priority': 5},
    'base': {'timeout': 5.0, 'priority': 2},
    'solana': {'timeout': 7.0, 'priority': 3},  # Solana can be slower
    'avalanche': {'timeout': 5.0, 'priority': 4}
}

def get_network_priority(network: str) -> int:
    """Get network priority for asset resolution (lower = higher priority)."""
    standardized = NETWORK_CHAIN_MAPPING.get(network.lower(), network.lower())
    return NETWORK_TIMEOUT_SETTINGS.get(standardized, {'priority': 99})['priority']

def get_network_timeout(network: str) -> float:
    """Get optimal timeout for network-specific operations."""
    standardized = NETWORK_CHAIN_MAPPING.get(network.lower(), network.lower())
    return NETWORK_TIMEOUT_SETTINGS.get(standardized, {'timeout': 5.0})['timeout']

async def enhanced_asset_search_with_network_optimization(query: str, networks: List[str] = None) -> List[Dict]:
    """
    StrykrScreener-inspired asset search with network-specific optimizations.

    Args:
        query: Search query
        networks: Optional list of networks to focus on

    Returns:
        List of optimized asset results
    """
    if not networks:
        # Default to high-priority networks
        networks = ['ethereum', 'binance-smart-chain', 'polygon-pos', 'base']

    # Sort networks by priority
    sorted_networks = sorted(networks, key=get_network_priority)

    # Try simple token lookup first (fastest)
    quick_results = await simple_token_lookup(query)
    if quick_results and quick_results[0].get('confidence', 0) > 0.9:
        logging.info(f"⚡ QUICK HIT: {query} resolved via simple cache")
        return [convert_token_to_asset(quick_results[0])]

    # Progressive network search with timeouts
    all_results = []

    for network in sorted_networks:
        timeout = get_network_timeout(network)

        try:
            logging.info(f"🔍 Searching {network} (timeout: {timeout}s)")

            # Network-specific search logic would go here
            # For now, using our existing enhanced search
            from .data_fetchers import enhanced_parallel_asset_search

            network_results = await asyncio.wait_for(
                enhanced_parallel_asset_search([query], f"{query} on {network}"),
                timeout=timeout
            )

            # Tag results with network info
            for result in network_results:
                result['detected_network'] = network
                result['network_priority'] = get_network_priority(network)

            all_results.extend(network_results)

            # If we found high-confidence results, we can stop early
            if any(r.get('confidence', 0) > 0.85 for r in network_results):
                logging.info(f"✅ High-confidence match found on {network}, stopping search")
                break

        except asyncio.TimeoutError:
            logging.warning(f"⏰ {network} search timed out after {timeout}s")
            continue
        except Exception as e:
            logging.warning(f"💥 {network} search failed: {e}")
            continue

    # Sort by confidence and network priority
    all_results.sort(key=lambda x: (x.get('confidence', 0), -x.get('network_priority', 99)), reverse=True)

    return all_results[:5]  # Return top 5 results


def is_valid_ticker(ticker):
    """
    Checks if a ticker symbol is valid.

    Args:
        ticker: The ticker symbol to check.

    Returns:
        True if valid, False otherwise.
    """
    STOCK_REGEX = re.compile(r"^[A-Z]{1,5}(\.[A-Z])?$")  # Stocks & ETFs (e.g., AAPL, SPY, BRK.B)
    CRYPTO_REGEX = re.compile(r"^[A-Z]{3,6}(/?[A-Z]{3,6})?$")  # Crypto (BTCUSD, ETH/USDT)
    FOREX_REGEX = re.compile(r"^[A-Z]{3}/?[A-Z]{3}$")  # Forex (EUR/USD, USDJPY)
    FUTURES_REGEX = re.compile(r"^[A-Z]{1,3}[FGHJKMNQUVXZ]\d{2}$")  # Futures (ESM24, CLZ23)

    if STOCK_REGEX.match(ticker) or CRYPTO_REGEX.match(ticker) or FOREX_REGEX.match(ticker) or FUTURES_REGEX.match(ticker):
        return True
    return False


async def fetch_asset_technical_indicators(ticker):
    """
    Fetches technical indicators (RSI, EMA, SMA, DEMA) for a given ticker.
    Uses FMP Stable API with date limiting to fetch only recent 10-day data.

    Args:
        ticker: The ticker symbol to fetch indicators for.

    Returns:
        Dictionary with technical indicators or empty dict if fetch fails.
    """
    logging.debug(f"Starting fetch_asset_technical_indicators for ticker: {ticker}")

    # Dictionary to store technical indicators
    technical_indicators = {}

    # Calculate date range for stable API (last 10 days)
    today = datetime.now()
    from_date = (today - timedelta(days=10)).strftime('%Y-%m-%d')
    to_date = today.strftime('%Y-%m-%d')

    # Define metadata about technical indicators
    indicator_metadata = {
        "RSI": {"timeframe": "4-hour", "period": 28},
        "EMA": {"timeframe": "4-hour", "period": 50},
        "DEMA": {"timeframe": "4-hour", "period": 20},
        "SMA": {"timeframe": "4-hour", "period": 200},
    }

    # Define functions to fetch each indicator
    async def fetch_rsi():
        try:
            rsi_url = f"https://financialmodelingprep.com/stable/technical-indicators/rsi?symbol={ticker}&periodLength=28&timeframe=4hour&from={from_date}&to={to_date}&apikey={settings.FMP_API_KEY}"
            print(f"DEBUG: Fetching RSI from Stable API: {rsi_url[0:rsi_url.find('apikey')]}[API_KEY]")
            rsi_response = await http_client.get(rsi_url)
            rsi_data = rsi_response.json()
            print(f"DEBUG: RSI response type: {type(rsi_data)}, length: {len(rsi_data) if isinstance(rsi_data, list) else 'not a list'}")
            if isinstance(rsi_data, list) and len(rsi_data) > 0:
                print(f"DEBUG: First RSI data item: {rsi_data[0]}")
                for item in rsi_data:
                    item["metadata"] = indicator_metadata["RSI"]
                return ("RSI", rsi_data)
            else:
                print(f"DEBUG: No valid RSI data received for {ticker}")
                return ("RSI", None)
        except Exception as e:
            print(f"DEBUG ERROR: Error fetching RSI for {ticker}: {str(e)}")
            logging.error(f"Error fetching RSI for {ticker}: {str(e)}")
            return ("RSI", None)

    async def fetch_ema():
        try:
            ema_url = f"https://financialmodelingprep.com/stable/technical-indicators/ema?symbol={ticker}&periodLength=50&timeframe=4hour&from={from_date}&to={to_date}&apikey={settings.FMP_API_KEY}"
            ema_response = await http_client.get(ema_url)
            ema_data = ema_response.json()
            if isinstance(ema_data, list) and len(ema_data) > 0:
                for item in ema_data:
                    item["metadata"] = indicator_metadata["EMA"]
                return ("EMA", ema_data)
            else:
                return ("EMA", None)
        except Exception as e:
            logging.error(f"Error fetching EMA for {ticker}: {str(e)}")
            return ("EMA", None)

    async def fetch_sma():
        try:
            sma_url = f"https://financialmodelingprep.com/stable/technical-indicators/sma?symbol={ticker}&periodLength=200&timeframe=4hour&from={from_date}&to={to_date}&apikey={settings.FMP_API_KEY}"
            sma_response = await http_client.get(sma_url)
            sma_data = sma_response.json()
            if isinstance(sma_data, list) and len(sma_data) > 0:
                for item in sma_data:
                    item["metadata"] = indicator_metadata["SMA"]
                return ("SMA", sma_data)
            else:
                return ("SMA", None)
        except Exception as e:
            logging.error(f"Error fetching SMA for {ticker}: {str(e)}")
            return ("SMA", None)

    async def fetch_dema():
        try:
            dema_url = f"https://financialmodelingprep.com/stable/technical-indicators/dema?symbol={ticker}&periodLength=20&timeframe=4hour&from={from_date}&to={to_date}&apikey={settings.FMP_API_KEY}"
            dema_response = await http_client.get(dema_url)
            dema_data = dema_response.json()
            if isinstance(dema_data, list) and len(dema_data) > 0:
                for item in dema_data:
                    item["metadata"] = indicator_metadata["DEMA"]
                return ("DEMA", dema_data)
            else:
                return ("DEMA", None)
        except Exception as e:
            logging.error(f"Error fetching DEMA for {ticker}: {str(e)}")
            return ("DEMA", None)

    # Note: No truncation needed - Stable API returns date-limited data automatically

    try:
        start_time = datetime.now()
        print(f"DEBUG: Starting parallel indicator fetch for {ticker} at {start_time}")

        # Fetch all indicators in parallel using shared http_client
        indicator_results = await asyncio.gather(
            fetch_rsi(),
            fetch_ema(),
            fetch_sma(),
            fetch_dema()
        )

        # Process results (no truncation needed - Stable API returns limited data)
        for indicator_name, indicator_data in indicator_results:
            if indicator_data:
                technical_indicators[indicator_name] = indicator_data
                print(f"DEBUG: Added {indicator_name} ({len(indicator_data)} entries) to technical_indicators")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"DEBUG: Completed parallel indicator fetch in {duration:.2f} seconds")

    except Exception as e:
        print(f"DEBUG ERROR: Error fetching technical indicators for {ticker}: {str(e)}")
        logging.error(f"Error fetching technical indicators for {ticker}: {str(e)}")

    print(f"DEBUG: Final technical_indicators for {ticker}: {list(technical_indicators.keys()) if technical_indicators else 'empty'}")
    return technical_indicators


async def get_ticker_quotes(ticker):
    """
    Fetches the latest quote data for a given ticker symbol. Redis cached for 1 hour.

    Args:
        ticker: The ticker symbol to fetch data for.

    Returns:
        List containing ticker data dict, or None if not found
    """
    try:
        # Check if the ticker is valid
        if is_valid_ticker(ticker):
            cache_key = f"ticker_quotes_{ticker}"
            cached_data = cache.get(cache_key)
            if cached_data:
                return [cached_data]
        else:
            return None

        # Fetch the data from the API(only done when ticker is valid)
        api_response = await http_client.get(
            f"https://financialmodelingprep.com/api/v3/quote/{ticker}?apikey={settings.FMP_API_KEY}"
        )
        api_data = api_response.json()

        # Check if we got any data back
        if not api_data or len(api_data) == 0:
            print(f"DEBUG: No data returned from FMP for ticker {ticker}")
            return None

        data = api_data[0]  # Now safe to access first element
        print(f"DEBUG: Initial ticker data fetched for {ticker}: {data.keys()}")
        if not data:
            return None

        # Debug FMP API key (partial for security)
        api_key = settings.FMP_API_KEY
        masked_key = api_key[:4] + "*****" + api_key[-4:] if api_key else "None"
        logging.debug(f"Using FMP API Key: {masked_key}")

        # Fetch technical indicators
        logging.debug(f"About to fetch technical indicators for {ticker}")
        technical_indicators = await fetch_asset_technical_indicators(ticker)
        logging.debug(f"Technical indicators for {ticker}: {technical_indicators}")
        if technical_indicators:
            # Add technical indicators to the data
            data["technical_indicators"] = technical_indicators
            logging.debug(f"Added technical indicators to {ticker} data")
        else:
            logging.warning(f"No technical indicators returned for {ticker}")

        # Cache the data
        cache.set(cache_key, data, timeout=1800)  # 30 minutes cache for ticker data
        return [data]  # Return the modified data with technical indicators

    except Exception as e:
        logging.error(f"Error fetching Asset Data: {str(e)}")
        return None


async def get_enhanced_ticker_quotes(ticker):
    """
    Enhanced version of get_ticker_quotes that includes additional fundamental data.

    Args:
        ticker: The ticker symbol to fetch enhanced data for.

    Returns:
        List containing enhanced ticker data dict, or None if not found
    """
    # Define a helper function to fetch base ticker data without blocking
    async def fetch_base_ticker_data():
        try:
            # First check if valid ticker
            if not is_valid_ticker(ticker):
                print(f"DEBUG: Invalid ticker format: {ticker}")
                return None

            # Check cache first
            cache_key = f"ticker_quotes_{ticker}"
            cached_data = cache.get(cache_key)
            if cached_data:
                print(f"DEBUG: Using cached base ticker data for {ticker}")
                return cached_data

            # Fetch fresh data if not in cache
            api_response = await http_client.get(
                f"https://financialmodelingprep.com/api/v3/quote/{ticker}?apikey={settings.FMP_API_KEY}"
            )

            data = api_response.json()
            if not data or len(data) == 0:
                print(f"DEBUG: No data returned from FMP for ticker {ticker}")
                return None

            base_data = data[0]
            print(f"DEBUG: Successfully fetched base ticker data for {ticker}")
            return base_data

        except Exception as e:
            logging.error(f"Error in fetch_base_ticker_data for {ticker}: {str(e)}")
            return None

    # Define a helper function to fetch technical indicators independently
    async def fetch_tech_indicators():
        try:
            technical_indicators = await fetch_asset_technical_indicators(ticker)
            return technical_indicators
        except Exception as e:
            logging.error(f"Error fetching technical indicators for {ticker}: {str(e)}")
            return None

    try:
        # Start measuring performance
        start_time = datetime.now()
        print(f"DEBUG: Starting parallel data fetch for {ticker} at {start_time}")

        # Fetch ALL data in parallel (including base ticker data and technical indicators)
        base_data_task = fetch_base_ticker_data()
        tech_indicators_task = fetch_tech_indicators()
        profile_task = fetch_company_profile(ticker)
        metrics_task = fetch_key_metrics(ticker)
        news_task = fetch_ticker_news(ticker)
        earnings_task = fetch_earnings_info(ticker)
        sector_task = fetch_sector_performance()
        gainers_task = fetch_market_gainers()
        losers_task = fetch_market_losers()

        # Gather all results at once
        base_data, tech_indicators, profile, metrics, news, earnings, sector, gainers, losers = await asyncio.gather(
            base_data_task,
            tech_indicators_task,
            profile_task,
            metrics_task,
            news_task,
            earnings_task,
            sector_task,
            gainers_task,
            losers_task
        )

        # Measure fetch duration
        mid_time = datetime.now()
        fetch_duration = (mid_time - start_time).total_seconds()
        print(f"DEBUG: Completed parallel data fetch in {fetch_duration:.2f} seconds")

        # First check if we got the base data
        if not base_data:
            return None

        # Combine all data into final output
        quote_data = base_data

        # Add technical indicators if available
        if tech_indicators:
            quote_data["technical_indicators"] = tech_indicators

        # Add company profile if available
        if profile:
            quote_data["company_profile"] = profile

        # Add key financial metrics if available
        if metrics:
            quote_data["key_metrics"] = metrics

        # Add recent news if available
        if news:
            quote_data["recent_news"] = news

        # Add earnings information if available
        if earnings:
            quote_data["earnings_info"] = earnings

        # Add sector performance data
        if sector:
            quote_data["sector_performance"] = sector

        # Add market gainers and losers for context
        if gainers:
            quote_data["market_gainers"] = gainers

        if losers:
            quote_data["market_losers"] = losers

        # Cache the complete enhanced data
        cache_key = f"ticker_quotes_{ticker}"
        cache.set(cache_key, quote_data, timeout=3600)  # 1 hour cache

        # Measure total duration
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()
        print(f"DEBUG: Total enhanced ticker processing completed in {total_duration:.2f} seconds")

        return [quote_data]  # Return as a list to match the original format

    except Exception as e:
        logging.error(f"Error fetching enhanced ticker data for {ticker}: {str(e)}")
        return None


async def get_batched_ticker_quotes(tickers):
    """
    Fetch ticker quotes for multiple tickers in a single FMP API call.
    
    Args:
        tickers: List of ticker symbols
        
    Returns:
        List of ticker data dicts, or None if batch call fails
    """
    if not tickers:
        return []
    
    try:
        # Join tickers with commas for FMP batch API
        batch_query = ",".join(tickers)
        print(f"DEBUG: Batching FMP quote request for {len(tickers)} tickers: {batch_query}")
        
        # Single API call for all tickers
        api_response = await http_client.get(
            f"https://financialmodelingprep.com/api/v3/quote/{batch_query}?apikey={settings.FMP_API_KEY}"
        )
        api_data = api_response.json()
        
        if not api_data or len(api_data) == 0:
            print(f"DEBUG: No data returned from FMP batch call for {batch_query}")
            return None
        
        print(f"DEBUG: FMP batch call returned {len(api_data)} results for {len(tickers)} tickers")
        return api_data
        
    except Exception as e:
        print(f"DEBUG: FMP batch call failed: {str(e)}")
        return None


async def fetch_ticker_data(tickers):
    """
    Fetches the latest quote data for a list of ticker symbols.
    Uses FMP batching for efficiency, with fallback to individual calls.

    Args:
        tickers: List of ticker symbols

    Returns:
        List of ticker data dicts
    """
    # Filter out invalid tickers BEFORE making API calls - key performance improvement
    valid_tickers = []
    for ticker in tickers:
        if is_valid_ticker(ticker):
            valid_tickers.append(ticker)
        else:
            logging.info(f"Skipping invalid ticker: {ticker}")
    
    if not valid_tickers:
        logging.info("No valid tickers found after filtering")
        return []
    
    logging.info(f"Processing {len(valid_tickers)} valid tickers out of {len(tickers)} total: {valid_tickers}")
    
    # Try FMP batching first for multiple tickers (40% faster)
    if len(valid_tickers) > 1:
        print(f"DEBUG: Attempting FMP batch call for {len(valid_tickers)} tickers")
        batch_results = await get_batched_ticker_quotes(valid_tickers)
        
        if batch_results and len(batch_results) > 0:
            print(f"DEBUG: FMP batch call succeeded, got {len(batch_results)} results")
            return batch_results
        else:
            print(f"DEBUG: FMP batch call failed, falling back to individual calls")
    
    # Fallback to individual calls (original behavior)
    print(f"DEBUG: Using individual FMP calls for {len(valid_tickers)} tickers")
    tasks = [get_ticker_quotes(ticker) for ticker in valid_tickers]
    results = await asyncio.gather(*tasks)

    return [quote[0] for quote in results if quote and isinstance(quote, list) and quote]


async def get_batched_enhanced_ticker_quotes(tickers):
    """
    Fetch enhanced ticker quotes for multiple tickers using FMP batching for base data.
    Still fetches technical indicators individually as they don't support batching.
    
    Args:
        tickers: List of ticker symbols
        
    Returns:
        List of enhanced ticker data dicts, or None if batch call fails
    """
    if not tickers:
        return []
    
    try:
        # Try to get base ticker data in one batch call
        base_data = await get_batched_ticker_quotes(tickers)
        
        if not base_data:
            return None
            
        # Convert base data to a dict for easy lookup
        base_data_dict = {item['symbol']: item for item in base_data}
        
        # Fetch technical indicators for each ticker (these don't support batching)
        enhanced_results = []
        for ticker in tickers:
            if ticker in base_data_dict:
                base_ticker_data = base_data_dict[ticker]
                
                # Fetch technical indicators for this ticker
                technical_indicators = await fetch_asset_technical_indicators(ticker)
                
                # Combine base data with technical indicators
                enhanced_data = {
                    **base_ticker_data,
                    'technical_indicators': technical_indicators or {}
                }
                
                enhanced_results.append(enhanced_data)
        
        return enhanced_results
        
    except Exception as e:
        print(f"DEBUG: Batched enhanced ticker quotes failed: {str(e)}")
        return None


async def fetch_enhanced_ticker_data(tickers):
    """
    Fetches enhanced ticker data with additional fundamentals and market context.
    Uses FMP batching for base data, with fallback to individual calls.
    
    ENHANCED: Added fallback to enhanced_parallel_asset_search for tickers not found via FMP.

    Args:
        tickers: List of ticker symbols

    Returns:
        List of enhanced ticker data dicts
    """
    # Filter out invalid tickers BEFORE making API calls - this is the key performance improvement
    valid_tickers = []
    for ticker in tickers:
        if is_valid_ticker(ticker):
            valid_tickers.append(ticker)
        else:
            logging.info(f"Skipping invalid ticker: {ticker}")
    
    if not valid_tickers:
        logging.info("No valid tickers found after filtering")
        return []
    
    logging.info(f"Processing {len(valid_tickers)} valid tickers out of {len(tickers)} total: {valid_tickers}")
    
    # Try FMP batching first for multiple tickers (enhanced version)
    if len(valid_tickers) > 1:
        print(f"DEBUG: Attempting FMP enhanced batch call for {len(valid_tickers)} tickers")
        batch_results = await get_batched_enhanced_ticker_quotes(valid_tickers)
        
        if batch_results and len(batch_results) > 0:
            print(f"DEBUG: FMP enhanced batch call succeeded, got {len(batch_results)} results")
            results = batch_results
        else:
            print(f"DEBUG: FMP enhanced batch call failed, falling back to individual calls")
            results = None
    else:
        results = None
    
    # Fallback to individual enhanced calls (original behavior)
    if results is None:
        print(f"DEBUG: Using individual enhanced FMP calls for {len(valid_tickers)} tickers")
        # Use the enhanced ticker quotes function with crypto fallback
        # Process up to 5 tickers in parallel for speed
        semaphore = asyncio.Semaphore(5)
        
        async def limited_fetch(ticker):
            async with semaphore:
                return await get_enhanced_ticker_quotes(ticker)
        
        tasks = [limited_fetch(ticker) for ticker in valid_tickers]
        individual_results = await asyncio.gather(*tasks)
        
        # Convert individual results to the same format as batch results
        results = [result[0] if result and isinstance(result, list) and result else None 
                  for result in individual_results]

    # Extract successful results and track failed tickers
    successful_results = []
    failed_tickers = []
    
    for i, result in enumerate(results):
        if result:
            successful_results.append(result)
        else:
            failed_tickers.append(valid_tickers[i])
    
    # ENHANCED: Try enhanced search for failed tickers
    if failed_tickers:
        logging.info(f"💫 FMP failed for {len(failed_tickers)} tickers: {failed_tickers}")
        logging.info(f"🔄 Trying enhanced search fallback...")
        print(f"💫 FMP failed for {len(failed_tickers)} tickers: {failed_tickers}")
        print(f"🔄 Trying enhanced search fallback...")
        
        try:
            from .data_fetchers import enhanced_parallel_asset_search
            
            # Use enhanced search for failed tickers
            for ticker in failed_tickers:
                try:
                    enhanced_results = await enhanced_parallel_asset_search([ticker], f"fetch data for {ticker}")
                    
                    if enhanced_results:
                        # Convert enhanced search result to ticker data format
                        best_result = enhanced_results[0]  # Take the first/best result
                        
                        if best_result.get('price') and best_result.get('symbol'):
                            ticker_data = {
                                'symbol': best_result.get('symbol', ticker),
                                'name': best_result.get('name', ''),
                                'price': best_result.get('price', 0),
                                'changesPercentage': best_result.get('change', 0),
                                'change': best_result.get('change', 0),
                                'volume': best_result.get('volume', 0),
                                'marketCap': best_result.get('market_cap', 0),
                                'data_source': best_result.get('source', 'enhanced_search'),
                                'enrichment_strategy': best_result.get('enrichment_strategy', 'enhanced_search_fallback'),
                                'confidence': best_result.get('confidence', 0.8),
                                'enhanced_search_fallback': True
                            }
                            
                            successful_results.append(ticker_data)
                            logging.info(f"✅ Enhanced search found {ticker}: {best_result.get('name')} - ${best_result.get('price')} - Vol: {best_result.get('volume', 0)}")
                            print(f"✅ Enhanced search found {ticker}: {best_result.get('name')} - ${best_result.get('price')} - Vol: {best_result.get('volume', 0)}")
                        else:
                            logging.warning(f"⚠️ Enhanced search result for {ticker} missing price/symbol data")
                    else:
                        logging.warning(f"❌ Enhanced search also failed for {ticker}")
                        
                except Exception as e:
                    logging.error(f"💥 Enhanced search error for {ticker}: {str(e)}")
                    
        except Exception as e:
            logging.error(f"💥 Enhanced search fallback failed: {str(e)}")
    
    logging.info(f"🎯 Final results: {len(successful_results)} tickers found")
    return successful_results


async def fetch_smart_ticker_data(tickers, query_intent):
    """
    Smart ticker data fetching based on query intent.
    Only fetches the data that's actually needed for the query.

    Args:
        tickers: List of ticker symbols
        query_intent: Query intent classification dict

    Returns:
        List of ticker data dicts
    """
    if not tickers:
        return []

    # For simple price queries, just get basic data
    if query_intent["type"] == "simple_price":
        return await fetch_ticker_data(tickers)

    # For technical analysis, we need indicators but not necessarily fundamentals
    if query_intent["type"] == "technical_analysis":
        # Create a custom fetch that only gets price + technicals
        async def get_technical_ticker_data(ticker):
            try:
                # Get base data
                base_data = await get_ticker_quotes(ticker)
                if not base_data:
                    return None

                # Only add technical indicators
                tech_indicators = await fetch_asset_technical_indicators(ticker)
                if tech_indicators:
                    base_data[0]["technical_indicators"] = tech_indicators

                return base_data
            except Exception as e:
                logging.error(f"Error in get_technical_ticker_data for {ticker}: {str(e)}")
                return None

        tasks = [get_technical_ticker_data(ticker) for ticker in tickers]
        results = await asyncio.gather(*tasks)
        return [quote[0] for quote in results if quote and isinstance(quote, list) and quote]

    # For market overview or when we need everything
    if query_intent["type"] in ["market_overview", "economic_analysis", "bellwether_analysis"]:
        # Use the full enhanced data
        return await fetch_enhanced_ticker_data(tickers)

    # For crypto lookups, prioritize crypto-specific data sources
    if query_intent["type"] == "crypto_lookup":
        # Try crypto-specific lookup first
        crypto_results = []
        for ticker in tickers:
            crypto_data = await fetch_crypto_by_symbol(ticker, original_query=query_intent.get("original_query", ""))
            if crypto_data:
                crypto_results.append(crypto_data)

        # If we found crypto data, return it
        if crypto_results:
            return crypto_results

        # Otherwise fall back to regular ticker data
        return await fetch_ticker_data(tickers)

    # Default: fetch enhanced data
    return await fetch_enhanced_ticker_data(tickers)


async def detect_ticker_conflicts(ticker_data_list, original_query):
    """
    Detect potential ticker conflicts between crypto and traditional assets by checking multiple data sources.

    Args:
        ticker_data_list: List of ticker data dicts
        original_query: Original user query

    Returns:
        Enhanced ticker list with conflict information
    """
    if not ticker_data_list:
        return ticker_data_list

    enhanced_ticker_list = []

    for ticker in ticker_data_list:
        symbol = ticker.get('symbol', '').upper()
        data_source = ticker.get('data_source', 'unknown')

        # For each ticker, try to find it in other data sources
        alternative_assets = []

        try:
            # If we got this from crypto (CoinGecko), check if it exists as a stock (FMP)
            if data_source == 'coingecko':
                print(f"DEBUG: Checking if crypto symbol '{symbol}' also exists as stock")
                stock_quotes = await get_ticker_quotes(symbol)
                if stock_quotes and len(stock_quotes) > 0:
                    stock_data = stock_quotes[0]
                    # Verify this is actually a different asset (not just the same data)
                    if stock_data.get('name', '').lower() != ticker.get('name', '').lower():
                        alternative_assets.append({
                            'type': 'stock',
                            'name': stock_data.get('name', ''),
                            'symbol': symbol,
                            'price': stock_data.get('price', 0),
                            'market_cap': stock_data.get('marketCap', 0),
                            'data_source': 'fmp',
                            'ticker_data': stock_data
                        })
                        print(f"DEBUG: Found stock alternative for {symbol}: {stock_data.get('name')}")

            # If we got this from stock (FMP), check if it exists as crypto (CoinGecko)
            elif data_source == 'fmp' or data_source == 'unknown':
                print(f"DEBUG: Checking if stock symbol '{symbol}' also exists as crypto")
                crypto_data = await fetch_crypto_by_symbol(symbol, original_query=original_query)
                if crypto_data and crypto_data.get('symbol', '').upper() == symbol:
                    # Verify this is actually a different asset
                    if crypto_data.get('name', '').lower() != ticker.get('name', '').lower():
                        alternative_assets.append({
                            'type': 'crypto',
                            'name': crypto_data.get('name', ''),
                            'symbol': symbol,
                            'price': crypto_data.get('price', 0),
                            'market_cap': crypto_data.get('marketCap', 0),
                            'data_source': 'coingecko',
                            'ticker_data': crypto_data
                        })
                        print(f"DEBUG: Found crypto alternative for {symbol}: {crypto_data.get('name')}")

        except Exception as e:
            print(f"DEBUG: Error checking for alternatives for {symbol}: {str(e)}")
            # Don't let this break the main flow
            pass

        # Add the original ticker to the enhanced list
        enhanced_ticker_list.append(ticker)

        # If we found alternatives, add them too and mark the conflict
        if alternative_assets:
            print(f"DEBUG: Symbol collision detected for '{symbol}' - found {len(alternative_assets)} alternatives")

            # Add all alternative assets as separate ticker entries
            for alt_asset in alternative_assets:
                enhanced_ticker_list.append({
                    "name": alt_asset['ticker_data'].get("name", ""),
                    "symbol": alt_asset['ticker_data'].get("symbol", ""),
                    "price": alt_asset['ticker_data'].get("price", 0),
                    "change": alt_asset['ticker_data'].get("changesPercentage", alt_asset['ticker_data'].get("change", 0)),
                    "market_cap": alt_asset['ticker_data'].get("marketCap", 0),
                    "volume": alt_asset['ticker_data'].get("volume", 0),
                    "data_source": alt_asset['data_source'],
                    "is_alternative": True,  # Mark this as an alternative asset
                    "original_symbol": symbol  # Reference to the original symbol query
                })

            # Mark the original ticker as having conflicts
            ticker['has_conflicts'] = True
            ticker['conflict_count'] = len(alternative_assets)

    return enhanced_ticker_list


def preprocess_query(query: str) -> str:
    """
    Clean and preprocess query for better asset resolution.

    Args:
        query: The raw query string

    Returns:
        Cleaned query string optimized for ticker extraction
    """
    # Remove common question words and phrases
    cleaned = re.sub(r'\b(what\'s|how\'s|tell me about|price of|info on|show me|give me|can you|please)\b', '', query, flags=re.IGNORECASE)

    # Remove trailing question marks and punctuation
    cleaned = re.sub(r'[?!.]+$', '', cleaned)

    # Extract potential tickers/symbols (2-8 chars, alphanumeric)
    potential_tickers = re.findall(r'\b[A-Za-z0-9]{2,8}\b', cleaned)

    # Remove common stop words that aren't tickers
    stop_words = {
        'the', 'and', 'or', 'but', 'not', 'are', 'was', 'has', 'had', 'can', 'may', 'will',
        'get', 'set', 'put', 'new', 'old', 'big', 'all', 'any', 'for', 'who', 'why', 'how',
        'when', 'where', 'here', 'there', 'long', 'short', 'buy', 'sell', 'good', 'bad',
        'best', 'worst', 'high', 'low', 'should', 'would', 'could', 'might', 'like', 'love',
        'hate', 'want', 'need', 'help', 'today', 'doing', 'look', 'seems', 'going', 'come'
    }

    # Filter out stop words but keep potential tickers
    filtered_tickers = []
    for ticker in potential_tickers:
        if ticker.lower() not in stop_words and len(ticker) >= 2:
            filtered_tickers.append(ticker)

    # If we found specific tickers, return them
    if filtered_tickers:
        return ' '.join(filtered_tickers)

    # Otherwise return the cleaned query
    return cleaned.strip()


def fuzzy_match_assets(query: str, confidence_threshold: float = 0.8) -> List[Dict]:
    """
    Simplified fuzzy matcher for asset resolution.

    Args:
        query: The search query
        confidence_threshold: Minimum confidence score for matches (higher = more conservative)

    Returns:
        List of matching assets with confidence scores
    """
    # Check alias cache first (shorter cache period)
    alias_key = f"alias_{query.lower()}"
    cached_result = cache.get(alias_key)
    if cached_result:
        return [cached_result]

    # Get known asset list from recent successful resolutions
    known_assets = cache.get("known_assets", [])

    matches = []
    for asset in known_assets:
        # Check symbol similarity (exact match prioritized)
        symbol_ratio = SequenceMatcher(None, query.lower(), asset['symbol'].lower()).ratio()

        # Only check exact symbol matches or very high name similarity
        if symbol_ratio >= confidence_threshold:
            matches.append({
                **asset,
                'confidence': symbol_ratio,
                'match_type': 'fuzzy'
            })

    # Cache successful matches as aliases (shorter period)
    if matches:
        cache.set(alias_key, matches[0], 10800)  # 3 hours instead of 24

    return sorted(matches, key=lambda x: x['confidence'], reverse=True)[:3]  # Only top 3


def update_known_assets(asset_data: Dict) -> None:
    """
    Update the known assets cache with new asset data (simplified version).

    Args:
        asset_data: Asset data dictionary
    """
    if not asset_data.get('symbol') or not asset_data.get('name'):
        return

    known_assets = cache.get("known_assets", [])

    # Check if asset already exists
    for existing_asset in known_assets:
        if existing_asset.get('symbol', '').upper() == asset_data.get('symbol', '').upper():
            return  # Asset already exists

    # Add new asset (simplified)
    asset_info = {
        'symbol': asset_data.get('symbol', '').upper(),
        'name': asset_data.get('name', ''),
        'confidence': asset_data.get('confidence', 0.5)
    }

    known_assets.append(asset_info)

    # Keep only the most recent 200 assets (reduced from 1000)
    if len(known_assets) > 200:
        known_assets = known_assets[-200:]

    # Cache for 6 hours instead of 24 to reduce memory usage
    cache.set("known_assets", known_assets, 21600)


# Removed complex alias management functions to reduce risk
# Simple alias caching is handled directly in fuzzy_match_assets()


async def simple_token_lookup(query: str) -> List[Dict]:
    """
    Ultra-simple token lookup with auto-caching.
    Provides fast lookups for top 500 tokens.

    Args:
        query: The search query

    Returns:
        List of matching tokens with confidence scores
    """
    # Check cache first
    tokens = cache.get('simple_tokens')
    if not tokens:
        # Fetch top 500 tokens ONCE, cache for 24 hours
        try:
            from .api_utils import http_client

            url = "https://pro-api.coingecko.com/api/v3/coins/markets"
            params = {
                'vs_currency': 'usd',
                'order': 'market_cap_desc',
                'per_page': 250,  # Reduced from 500 to lower risk
                'page': 1
            }

            # Add proper authentication headers for CoinGecko Pro API
            headers = {
                "accept": "application/json",
                "x-cg-pro-api-key": settings.COINGECKO_API_KEY
            }

            # Use existing http_client for consistency
            response = await http_client.get(url, params=params, headers=headers)

            if response.status_code == 200:
                data = response.json()

                # Store minimal data for fuzzy matching
                tokens = []
                for token in data:
                    tokens.append({
                        'symbol': token['symbol'].upper(),
                        'name': token['name'],
                        'id': token['id'],
                        'market_cap_rank': token.get('market_cap_rank', 999),
                        'current_price': token.get('current_price', 0),
                        'price_change_24h': token.get('price_change_percentage_24h', 0),
                        'market_cap': token.get('market_cap', 0),
                        'source': 'simple_token_cache'
                    })

                # Cache for 12 hours instead of 24 to reduce memory
                cache.set('simple_tokens', tokens, 43200)
            else:
                tokens = []

        except Exception as e:
            logging.error(f"Error fetching simple token list: {str(e)}")
            # Fallback to empty list if API fails
            tokens = []

    # Fuzzy match against cached tokens
    matches = []
    query_lower = query.lower()

    for token in tokens:
        # Check exact matches first
        if query_lower == token['symbol'].lower():
            matches.append({**token, 'confidence': 1.0, 'match_type': 'exact'})
            continue

        # Check fuzzy matches
        symbol_ratio = SequenceMatcher(None, query_lower, token['symbol'].lower()).ratio()
        name_ratio = SequenceMatcher(None, query_lower, token['name'].lower()).ratio()

        if symbol_ratio >= 0.8 or name_ratio >= 0.7:
            matches.append({
                **token,
                'confidence': max(symbol_ratio, name_ratio),
                'match_type': 'fuzzy'
            })

    # Sort by confidence, then by market cap rank
    matches.sort(key=lambda x: (x['confidence'], -x['market_cap_rank']), reverse=True)
    return matches[:5]  # Return top 5 matches


def convert_token_to_asset(token_data: Dict) -> Dict:
    """Convert simple token data to enriched asset format."""
    return {
        'symbol': token_data.get('symbol', ''),
        'name': token_data.get('name', ''),
        'price': token_data.get('current_price') or token_data.get('price'),
        'change': token_data.get('price_change_24h') or token_data.get('price_change_percentage_24h'),
        'market_cap': token_data.get('market_cap'),
        'market_cap_rank': token_data.get('market_cap_rank'),
        'volume': token_data.get('total_volume'),
        'confidence': token_data.get('confidence', 0.8),
        'source': 'simple_token_cache',
        'image': token_data.get('image')
    }


def detect_chain_context(query: str) -> List[str]:
    """
    Detect blockchain context from query.

    Args:
        query: The user query

    Returns:
        List of detected chain names
    """
    chain_keywords = {
        'ethereum': ['eth', 'ethereum', 'erc20', 'uniswap', 'metamask', 'vitalik'],
        'bsc': ['bsc', 'binance', 'pancakeswap', 'bnb', 'binance smart chain'],
        'polygon': ['polygon', 'matic', 'quickswap', 'polygon network'],
        'solana': ['sol', 'solana', 'spl', 'raydium', 'phantom', 'solana network'],
        'arbitrum': ['arbitrum', 'arb', 'arbitrum one'],
        'optimism': ['optimism', 'op', 'optimistic'],
        'avalanche': ['avax', 'avalanche', 'pangolin'],
        'base': ['base', 'base network', 'coinbase base']
    }

    detected_chains = []
    query_lower = query.lower()

    for chain, keywords in chain_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            detected_chains.append(chain)

    # Default to major chains if none detected
    return detected_chains if detected_chains else ['ethereum', 'bsc', 'polygon']


def get_chain_priority(chains: List[str]) -> List[str]:
    """
    Simplified chain priority - just return detected chains or defaults.

    Args:
        chains: List of detected chains

    Returns:
        List of chains (simplified)
    """
    # If specific chains detected, use them; otherwise use top 3
    return chains if chains else ['ethereum', 'bsc', 'polygon'] 