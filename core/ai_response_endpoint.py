"""
Main AI response endpoint module.
Contains the core ai_response function that orchestrates the entire query processing flow.
Restored original logic for better performance while keeping enhancements.
"""

import asyncio
import json
import logging
import re
import time
from typing import Optional, List, Dict
from django.utils import timezone
from django.views.decorators.cache import never_cache
from ninja import Schema

from .api_utils import validate_api_key
from .calendar_builder import get_calendar_data
from .data_fetchers import (
    fetch_bellwether_assets,
    fetch_news_from_database,
    fetch_crypto_news_from_database,
    enhanced_parallel_asset_search,
)
from .models import AIQuery, EconomicEvents
from .prompt_builder import get_bellwether_assets_indices, get_full_prompt, get_tickers
from .response_helpers import get_helpful_fallback
from .ticker_services import fetch_enhanced_ticker_data

# Import enhanced data provider functions (keep CoinGecko + Moralis)
from .data_providers import (
    fetch_crypto_by_symbol,
    fetch_coingecko_crypto_data,
    search_coins_markets,
    fetch_memecoin_data,
    fetch_top_memecoins,
    fetch_top_gainers_losers,
    fetch_token_by_contract,
    fetch_global_market_data,
    fetch_market_gainers,
    fetch_market_losers
)

# Import Moralis provider for additional crypto data
from .moralis_provider import (
    fetch_trending_tokens,
    fetch_pumpfun_trending,
    # REMOVED: search_tokens_by_name and moralis_asset_search
    # These functions used endpoints not available on current Moralis plan
)

from .response_generators import handle_streaming_response, handle_regular_response


def should_skip_llm(ticker_data: List[Dict]) -> bool:
    """
    Check if we have high-confidence matches to skip LLM (conservative threshold).
    
    DISABLED: Fast-path optimization removed for better stability and UX.
    Users prefer rich AI analysis over simple ticker displays.
    
    Args:
        ticker_data: List of ticker data with confidence scores
        
    Returns:
        Always False - fast-path disabled
    """
    return False


def generate_fast_response(ticker_data: List[Dict]) -> Dict:
    """
    Generate a fast response for high-confidence matches without LLM.
    
    Args:
        ticker_data: List of ticker data
        
    Returns:
        Response dictionary
    """
    if not ticker_data:
        return {"response": "No asset data available."}
    
    # Take the highest confidence asset
    best_asset = max(ticker_data, key=lambda x: x.get('confidence', 0))
    
    # Create a simple response
    symbol = best_asset.get('symbol', 'Unknown')
    name = best_asset.get('name', 'Unknown Asset')
    price = best_asset.get('price', 0)
    change = best_asset.get('change', 0)
    market_cap = best_asset.get('market_cap', 0)
    
    response = f"**{symbol}** - {name}\n\n"
    response += f"💰 **Price**: ${price:,.2f}\n"
    
    if change > 0:
        response += f"📈 **24h Change**: +{change:.2f}%\n"
    elif change < 0:
        response += f"📉 **24h Change**: {change:.2f}%\n"
    else:
        response += f"➡️ **24h Change**: {change:.2f}%\n"
    
    if market_cap > 0:
        if market_cap > 1_000_000_000:
            response += f"🏢 **Market Cap**: ${market_cap/1_000_000_000:.2f}B\n"
        elif market_cap > 1_000_000:
            response += f"🏢 **Market Cap**: ${market_cap/1_000_000:.2f}M\n"
        else:
            response += f"🏢 **Market Cap**: ${market_cap:,.0f}\n"
    
    response += f"\n*Source: {best_asset.get('source', 'API')}*"
    
    return {"response": response}


# AIRequestBody schema definition
class AIRequestBody(Schema):
    query: str
    third_party_user_id: Optional[str] = ""
    return_prompt: Optional[bool] = False
    stream: Optional[bool] = False
    enable_bellwether: Optional[bool] = True
    enable_macro: Optional[bool] = True


@never_cache  # Disable caching for streaming responses
async def ai_response(request, body: AIRequestBody):
    """
    Main AI response endpoint with restored original logic for better performance.
    Keeps enhanced ticker data and Moralis integration while restoring working crypto fallbacks.
    """
    # Start timing the entire request
    request_start_time = time.time()
    
    # Get the API key from the header
    api_key = request.headers.get("X-API-KEY", default="")
    is_client_side_key = False

    # Get the domain of origin
    origin = request.headers.get("Origin", default="notarealorigin.xyz")
    from urllib.parse import urlparse
    domain = urlparse(origin).netloc
    domain = domain.split(":")[0]

    # Determine if API key is client side or not
    if api_key.startswith("Client "):
        api_key = api_key.replace("Client ", "", 1)
        is_client_side_key = True

    # Validate the API key
    api_key_obj = await validate_api_key(api_key, domain, is_client_side_key, request.user)

    # Save the query
    await AIQuery.objects.acreate(
        query=body.query,
        api_key=api_key_obj,
        third_party_user_id=body.third_party_user_id,
    )

    # RESTORED: Simple direct logic instead of complex query classification
    # Parallelize the data fetching - no unnecessary AI classification call
    tickers = get_tickers(body.query)
    
    tasks = []
    ticker_list = [ticker for ticker in tickers[:10]]

    # Use enhanced ticker data for richer context (keep this improvement)
    tasks.append(fetch_enhanced_ticker_data(ticker_list))

    if body.enable_bellwether:
        bell_indicies = get_bellwether_assets_indices(body.query)
        tasks.append(fetch_bellwether_assets(bell_indicies))
    else:
        tasks.append(asyncio.sleep(0))
    
    if body.enable_macro:
        # Get current month and year from system time
        current_month = timezone.now().strftime("%b").lower()
        current_year = timezone.now().strftime("%Y")

        # Create a dedicated async function for fetching calendar data
        async def fetch_economic_calendar():
            try:
                economic_event_obj = await EconomicEvents.objects.aget(
                    month=current_month, 
                    year=current_year
                )
                events = economic_event_obj.data
                return get_calendar_data(current_month, current_year, events, [])
            except EconomicEvents.DoesNotExist:
                return {}
            except Exception as e:
                logging.error(f"Error in fetch_economic_calendar task: {str(e)}")
                return {}
        
        # Add calendar fetch to parallel tasks
        tasks.append(fetch_economic_calendar())
        
        # Add news fetch to parallel tasks
        tasks.append(fetch_news_from_database())
        
        # Add crypto news fetch to parallel tasks
        tasks.append(fetch_crypto_news_from_database())
    else:
        tasks.append(asyncio.sleep(0))  # Calendar placeholder
        tasks.append(asyncio.sleep(0))  # News placeholder
        tasks.append(asyncio.sleep(0))  # Crypto news placeholder

    results = await asyncio.gather(*tasks)
    
    # Unpack results
    ticker_quotes = results[0] if len(results) > 0 and results[0] else []
    bellwether_assets_qs = results[1] if len(results) > 1 and results[1] else []
    
    economic_calendar_data = {}
    news_data = []
    crypto_news_data = []

    if body.enable_macro:
        # Economic calendar data from task result
        if len(results) > 2 and results[2] is not None:
            economic_calendar_data = results[2]
        else:
            economic_calendar_data = {}

        # News data from task result
        if len(results) > 3 and results[3] is not None:
            news_data = results[3]
        else:
            news_data = []
        
        # Crypto news data from task result
        if len(results) > 4 and results[4] is not None:
            crypto_news_data = results[4]
        else:
            crypto_news_data = []
    else:
        economic_calendar_data = {}
        news_data = []
        crypto_news_data = []

    # Ensure news_data is a list, as downstream code might expect it
    if not isinstance(news_data, list):
        news_data = []
    
    # RESTORED: Direct ticker data preparation (original working logic)
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
                "average_volume": ticker.get("avgVolume", ticker["volume"]),
                "pe_ratio": ticker.get("pe", None),
            }
            
            # Add enhanced data if available (keep this improvement)
            if "company_profile" in ticker:
                ticker_dict["company_profile"] = ticker["company_profile"]
            
            if "key_metrics" in ticker:
                ticker_dict["key_metrics"] = ticker["key_metrics"]
            
            if "recent_news" in ticker:
                ticker_dict["recent_news"] = ticker["recent_news"]
            
            if "earnings_info" in ticker:
                ticker_dict["earnings_info"] = ticker["earnings_info"]
                
            if "technical_indicators" in ticker:
                ticker_dict["technical_indicators"] = ticker["technical_indicators"]
                
            # Add market context data to the first ticker only
            if ticker_quotes.index(ticker) == 0:
                if "sector_performance" in ticker:
                    ticker_dict["sector_performance"] = ticker["sector_performance"]
                    
                if "market_gainers" in ticker:
                    ticker_dict["market_gainers"] = ticker["market_gainers"]
                    
                if "market_losers" in ticker:
                    ticker_dict["market_losers"] = ticker["market_losers"]
            
            ticker_data_for_prompt_list.append(ticker_dict)

    # DEBUG: Always log ticker extraction and FMP results
    print(f"DEBUG TICKER EXTRACTION: Raw tickers from query = {tickers}")
    print(f"DEBUG TICKER EXTRACTION: FMP returned {len(ticker_data_for_prompt_list)} results")
    print(f"DEBUG TICKER EXTRACTION: FMP result symbols = {[t.get('symbol', 'NO_SYMBOL') for t in ticker_data_for_prompt_list]}")
    print(f"DEBUG TICKER EXTRACTION: FMP result names = {[t.get('name', 'NO_NAME') for t in ticker_data_for_prompt_list]}")
    
    # ENHANCED: Multi-source crypto fallback with Moralis, CoinGecko, and FMP
    # FIX: Allow multiple ticker processing even when some are already found
    if tickers and len(ticker_data_for_prompt_list) < len(tickers):
        # DEBUG: Detailed logging for missing ticker diagnosis
        print(f"DEBUG TICKER SEARCH: Total tickers extracted = {tickers}")
        print(f"DEBUG TICKER SEARCH: FMP found {len(ticker_data_for_prompt_list)} tickers")
        print(f"DEBUG TICKER SEARCH: Found symbols = {[t.get('symbol', 'UNKNOWN') for t in ticker_data_for_prompt_list]}")
        
        # Calculate missing tickers by comparing input vs found symbols
        found_symbols = [t.get('symbol', '') for t in ticker_data_for_prompt_list]
        print(f"DEBUG TICKER SEARCH: Found symbols from FMP = {found_symbols}")
        
        # Find tickers that weren't found by FMP (actual missing tickers)
        missing_tickers = []
        for ticker in tickers:
            # Check if this ticker symbol appears in found results
            ticker_found = any(
                found_symbol.upper() == ticker.upper() or 
                found_symbol.upper() == ticker.replace('USD', '').upper()
                for found_symbol in found_symbols
            )
            if not ticker_found:
                missing_tickers.append(ticker)
        
        # Limit to 10 missing tickers
        missing_tickers = missing_tickers[:10]
        print(f"DEBUG TICKER SEARCH: Calculated missing tickers = {missing_tickers}")
        
        print(f"DEBUG TICKER SEARCH: Missing tickers for enhanced search = {missing_tickers}")
        print(f"DEBUG: Found {len(ticker_data_for_prompt_list)} of {len(tickers)} tickers via FMP, trying enhanced search for: {missing_tickers}")
        
        # Use enhanced parallel asset search (FMP + CoinGecko + Moralis + Contract lookup)
        search_results = await enhanced_parallel_asset_search(missing_tickers, body.query)
        
        if search_results:
            print(f"DEBUG: Enhanced search found {len(search_results)} assets")
            
            # Process search results and add to ticker data
            for asset in search_results[:len(missing_tickers)]:  # Limit to missing ticker count
                # Ensure we have valid data
                if asset.get('symbol') and asset.get('name'):
                    # Handle enriched data with proper field mapping
                    price = asset.get("price", 0)
                    change = asset.get("change") or asset.get("changesPercentage", 0)
                    market_cap = asset.get("market_cap") or asset.get("marketCap", 0)
                    volume = asset.get("volume", 0)
                    
                    # Note: Volume data should now be available from fixed CoinGecko endpoints
                    # Removed problematic "N/A" override logic that was blocking volume data
                    
                    ticker_data_for_prompt_list.append({
                        "name": asset.get("name", ""),
                        "symbol": asset.get("symbol", ""),
                        "price": price,
                        "change": change,
                        "market_cap": market_cap,
                        "volume": volume,
                        "average_volume": volume,
                        "pe_ratio": None,  # Not applicable for crypto
                        "data_source": asset.get("source", "enhanced_search"),
                        "confidence": asset.get("confidence", 0.5),
                        "enrichment_success": asset.get("enrichment_success", False),
                        "enrichment_strategy": asset.get("enrichment_strategy", "")
                    })
                    
                    # Log final volume data for tracking
                    volume_status = f"${volume:,.0f}" if volume and volume > 0 else "missing"
                    logging.info(f"📊 FINAL DATA: {asset.get('symbol')} → price=${price}, volume={volume_status}")
                    
                    print(f"DEBUG: Enhanced search successful for {asset.get('symbol')}: found {asset.get('name')} (source: {asset.get('source')}, confidence: {asset.get('confidence', 0.5)}, price: ${price}, market_cap: ${market_cap})")
        else:
            print(f"DEBUG: Enhanced search returned no results for {missing_tickers}")
            
            # Fallback to individual lookups if enhanced search fails
            for ticker_symbol in missing_tickers:
                print(f"DEBUG: Attempting individual crypto fallback for ticker: {ticker_symbol}")
                
                crypto_data = await fetch_crypto_by_symbol(ticker_symbol, original_query=body.query)
                
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
                    print(f"DEBUG: Individual crypto fallback successful for {ticker_symbol}: found {crypto_data.get('name')}")

    # RESTORED: Original bellwether data preparation
    bellwether_assets_dict_for_prompt = {}
    if bellwether_assets_qs:
        for asset in bellwether_assets_qs:
            if asset.symbol not in bellwether_assets_dict_for_prompt:
                bellwether_assets_dict_for_prompt[asset.symbol] = {
                    "name": asset.name,
                    "symbol": asset.symbol,
                    "descriptors": asset.descriptors
                }
            if asset.data_type == "RSI":
                bellwether_assets_dict_for_prompt[asset.symbol]["rsi_data"] = json.dumps(
                    [{k: d[k] for k in ["date", "rsi"]} for d in asset.data[:12]],
                    indent=2,
                )
            elif asset.data_type == "EMA":
                if asset.symbol in bellwether_assets_dict_for_prompt:
                    bellwether_assets_dict_for_prompt[asset.symbol]["ema_data"] = json.dumps(
                        [{k: d[k] for k in ["date", "ema"]} for d in asset.data[:12]],
                        indent=2,
                    )
    
    # RESTORED: Original economic calendar data preparation
    economic_calendar_data_for_prompt = {}
    if economic_calendar_data and isinstance(economic_calendar_data, dict):
        # Add current date context
        today = timezone.now()
        today_str = today.strftime("%Y-%m-%d")
        
        # Add proper date formatting and highlight today's events
        if "week" in economic_calendar_data:
            for date_str, data in economic_calendar_data["week"].items():
                try:
                    from datetime import datetime
                    event_date = datetime.strptime(date_str, "%Y-%m-%d")
                    data["date_display"] = event_date.strftime("%A, %B %d")
                    data["is_today"] = date_str == today_str
                except ValueError:
                    data["date_display"] = date_str
                    data["is_today"] = False
                    
            economic_calendar_data_for_prompt = economic_calendar_data
        else:
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
            except Exception as e:
                logging.error(f"Error processing week data: {str(e)}")

        # Add thresholds if available
        if "thresholds" in economic_calendar_data:
            try:
                economic_calendar_data_for_prompt["thresholds"] = json.dumps([{k: v} for k, v in economic_calendar_data["thresholds"].items()], indent=2)
            except Exception as e:
                logging.error(f"Error processing thresholds data: {str(e)}")

    # Initialize query_context
    query_context = {}
    
    # RESTORED: Original crypto query detection and handling
    ticker_terms = ['price', 'stock', 'ticker', 'coin', 'crypto', 'eth', 'btc', 'technical', 'rsi', 'ema', 'sma', 'dema']
    has_ticker_terms = any(term in body.query.lower() for term in ticker_terms)
    
    # Check if this is a cryptocurrency-specific query
    crypto_terms = ['crypto', 'coin', 'token', 'eth', 'btc', 'blockchain', 'memecoin', 'bitcoin', 'ethereum']
    contract_pattern = re.compile(r'0x[a-fA-F0-9]{40}')
    has_contract_address = bool(contract_pattern.search(body.query))
    
    # Extract potential token names/symbols for detection
    potential_token_words = re.findall(r'\b([A-Za-z0-9]{2,8})\b', body.query)
    
    # Always consider queries with short words (2-8 chars) as potentially crypto-related
    is_crypto_query = any(term in body.query.lower() for term in crypto_terms) or has_contract_address or any(len(word) >= 2 and len(word) <= 8 for word in potential_token_words)
    
    # Check if this is a memecoin query
    memecoin_terms = ['memecoin', 'meme coin', 'meme token', 'doge', 'shib', 'pepe']
    is_memecoin_query = any(term in body.query.lower() for term in memecoin_terms)
    
    # NOTE: Moralis integration is already handled in enhanced_parallel_asset_search
    # Removed redundant Moralis fallback call to eliminate 50-100ms latency for crypto queries
    # This was causing duplicate API calls since Moralis is already part of the parallel search above
    
    # Contract address lookups
    if has_contract_address:
        print(f"DEBUG: Detected contract address in query: {body.query}")
        contract_address = contract_pattern.search(body.query).group(0)
        asset_platform = "ethereum"  # Default
        
        token_data = await fetch_token_by_contract(asset_platform, contract_address)
        if token_data:
            ticker_data_for_prompt_list.append({
                "name": token_data["name"],
                "symbol": token_data["symbol"],
                "price": token_data["price"],
                "change": token_data["changesPercentage"],
                "market_cap": token_data["marketCap"],
                "volume": token_data["volume"],
                "contract_address": token_data["contract_address"],
                "asset_platform": token_data["asset_platform"],
                "data_source": "coingecko"
            })
            query_context["has_contract_lookup"] = True

    # Handle memecoin queries
    if is_memecoin_query:
        print(f"DEBUG: Detected memecoin query: {body.query}")
        
        memecoin_category = await fetch_memecoin_data()
        top_memecoins = await fetch_top_memecoins()
        
        if memecoin_category or top_memecoins:
            query_context["memecoin_data"] = {
                "category": memecoin_category,
                "top_coins": top_memecoins
            }
            
            # If we don't have specific ticker data, add some top memecoins
            if not ticker_data_for_prompt_list and top_memecoins:
                for coin in top_memecoins[:3]:
                    ticker_data_for_prompt_list.append({
                        "name": coin["name"],
                        "symbol": coin["symbol"],
                        "price": coin["current_price"],
                        "change": coin.get("price_change_percentage_24h", 0),
                        "market_cap": coin.get("market_cap", 0),
                        "volume": coin.get("total_volume", 0),
                        "average_volume": coin.get("total_volume", 0),
                        "data_source": "coingecko"
                    })

    # RESTORED: Original conflict detection (inline, not separate function)
    if ticker_data_for_prompt_list:
        enhanced_ticker_list = []
        
        for ticker in ticker_data_for_prompt_list:
            symbol = ticker.get('symbol', '').upper()
            data_source = ticker.get('data_source', 'unknown')
            
            # Check for alternatives
            alternative_assets = []
            
            try:
                # If we got this from crypto, check if it exists as a stock
                if data_source == 'coingecko' or data_source == 'moralis':
                    from .ticker_services import get_ticker_quotes
                    stock_quotes = await get_ticker_quotes(symbol)
                    if stock_quotes and len(stock_quotes) > 0:
                        stock_data = stock_quotes[0]
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
                
                # If we got this from stock, check if it exists as crypto
                elif data_source == 'fmp' or data_source == 'unknown':
                    crypto_data = await fetch_crypto_by_symbol(symbol, original_query=body.query)
                    if crypto_data and crypto_data.get('symbol', '').upper() == symbol:
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
            
            except Exception as e:
                logging.error(f"Error checking alternatives for {symbol}: {str(e)}")
            
            # Add the original ticker
            enhanced_ticker_list.append(ticker)
            
            # Add alternatives
            if alternative_assets:
                for alt_asset in alternative_assets:
                    enhanced_ticker_list.append({
                        "name": alt_asset['ticker_data'].get("name", ""),
                        "symbol": alt_asset['ticker_data'].get("symbol", ""),
                        "price": alt_asset['ticker_data'].get("price", 0),
                        "change": alt_asset['ticker_data'].get("changesPercentage", alt_asset['ticker_data'].get("change", 0)),
                        "market_cap": alt_asset['ticker_data'].get("marketCap", 0),
                        "volume": alt_asset['ticker_data'].get("volume", 0),
                        "data_source": alt_asset['data_source'],
                        "is_alternative": True,
                        "original_symbol": symbol
                    })
                
                # Mark the original ticker as having conflicts
                ticker['has_conflicts'] = True
                ticker['conflict_count'] = len(alternative_assets)
        
        ticker_data_for_prompt_list = enhanced_ticker_list
        
        # Check if any conflicts were detected
        conflicts_found = [ticker for ticker in ticker_data_for_prompt_list if ticker.get('has_conflicts')]
        if conflicts_found:
            symbols_with_conflicts = list(set([ticker.get('symbol') for ticker in conflicts_found]))
            query_context["symbol_conflicts"] = {
                "has_conflicts": True,
                "conflicted_symbols": symbols_with_conflicts,
                "total_assets_found": len(ticker_data_for_prompt_list),
                "instruction": "Multiple assets found with the same symbol(s). Please show both/all options to the user and ask them to clarify which asset they meant."
            }

    # Handle market trends if no specific ticker data found
    if has_ticker_terms and not ticker_data_for_prompt_list:
        trend_terms = ['trend', 'bullish', 'bearish', 'gaining', 'losing', 'performing', 'best', 'worst', 'top', 'movers']
        is_trend_query = any(term in body.query.lower() for term in trend_terms)
        
        if is_trend_query:
            if is_crypto_query:
                crypto_gainers_losers = await fetch_top_gainers_losers()
                if crypto_gainers_losers:
                    query_context["crypto_gainers_losers"] = crypto_gainers_losers
            
            # Always get stock gainers/losers as backup
            market_gainers = await fetch_market_gainers()
            market_losers = await fetch_market_losers()
            
            if market_gainers or market_losers:
                query_context.update({
                    "market_gainers": market_gainers,
                    "market_losers": market_losers,
                    "is_trend_query": True
                })

    # General crypto market data for broad crypto queries
    if is_crypto_query and not ticker_data_for_prompt_list:
        global_market_data = await fetch_global_market_data()
        if global_market_data:
            query_context["crypto_market_data"] = global_market_data

    # CONFIDENCE-BASED FAST-PATH: Skip LLM for high-confidence matches
    if should_skip_llm(ticker_data_for_prompt_list):
        logging.info(f"⚡ FAST-PATH: Skipping LLM for high-confidence matches")
        print(f"⚡ FAST-PATH: Skipping LLM for high-confidence matches")  # Railway console
        fast_response = generate_fast_response(ticker_data_for_prompt_list)
        total_time = time.time() - request_start_time
        logging.info(f"🎯 FAST-PATH TOTAL TIME: {total_time:.2f}s")
        print(f"🎯 FAST-PATH TOTAL TIME: {total_time:.2f}s")  # Railway console
        return fast_response

    # Create the prompt
    prompt = get_full_prompt(
        body.query,
        ticker_data_for_prompt_list,
        list(bellwether_assets_dict_for_prompt.values()),
        economic_calendar_data_for_prompt,
        news_data,
        crypto_news_data,
        query_context
    )

    if body.return_prompt:
        return {"prompt": prompt}

    # Prepare system message
    system_message = "You are an friendly, helpful and advanced AI Powered **Financial Market Analysis and Trading Assistant** Agent specializing in cryptocurrencies, forex, equities (including SPX500), commodities, options, and macroeconomic correlations. Your role is to provide comprehensive market insights, helping users manage positions, analyze risks, and develop actionable trading strategies based on current market conditions, macroeconomic events, and asset-specific technical analysis. Engage in natural, conversational dialogue and encourage follow-up questions."

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": "Hi! How are you?"},
        {"role": "assistant", "content": "I'm doing great, thank you! How can I help you today?"},
        {"role": "user", "content": prompt},
    ]

    try:
        # Log end-to-end timing before response generation
        data_processing_time = time.time() - request_start_time
        logging.info(f"🔄 DATA PROCESSING METRICS:")
        logging.info(f"   ⏱️  Data Processing Time: {data_processing_time:.2f}s")
        logging.info(f"   📊 Tickers Found: {len(ticker_data_for_prompt_list)}")
        logging.info(f"   🔔 Bellwether Assets: {len(bellwether_assets_dict_for_prompt)}")
        logging.info(f"   📅 Economic Events: {'Yes' if economic_calendar_data else 'No'}")
        logging.info(f"   📰 News Items: {len(news_data) if news_data else 0}")
        logging.info(f"   🎯 Stream Mode: {'Yes' if body.stream else 'No'}")
        
        # Print key metrics for Railway console
        print(f"🔄 DATA PROCESSING TIME: {data_processing_time:.2f}s | Tickers: {len(ticker_data_for_prompt_list)} | Stream: {'Yes' if body.stream else 'No'}")
        
        if body.stream:
            # Handle streaming response
            response = await handle_streaming_response(messages)
            # Log total request time
            total_time = time.time() - request_start_time
            logging.info(f"🎯 TOTAL REQUEST TIME: {total_time:.2f}s")
            print(f"🎯 TOTAL REQUEST TIME: {total_time:.2f}s")  # Railway console
            return response
        else:
            # Handle regular response
            response = await handle_regular_response(messages)
            # Log total request time
            total_time = time.time() - request_start_time
            logging.info(f"🎯 TOTAL REQUEST TIME: {total_time:.2f}s")
            print(f"🎯 TOTAL REQUEST TIME: {total_time:.2f}s")  # Railway console
            return response

    except Exception as e:
        # Log the error with timing
        total_time = time.time() - request_start_time
        logging.error(f"❌ Error in AI response generation after {total_time:.2f}s: {str(e)}")
        
        # Handle different types of errors appropriately
        error_message = str(e)
        
        # Check if it's an OpenAI API error
        if "Error code: 500" in error_message or "server_error" in error_message:
            logging.error("OpenAI API server error detected - using enhanced fallback")
            fallback = get_helpful_fallback(body.query)
            
            # Add context about the error for better user experience
            enhanced_fallback = f"I'm experiencing some technical difficulties with my AI processing right now. Here's what I can still help with:\n\n{fallback}\n\nPlease try your query again in a moment, or rephrase it if the issue persists."
            
            return {"response": enhanced_fallback}
        
        # Handle rate limiting
        elif "rate limit" in error_message.lower():
            return {"response": "I'm currently experiencing high demand. Please wait a moment and try your query again."}
        
        # Handle timeout errors
        elif "timeout" in error_message.lower():
            return {"response": "Your query is taking longer than expected to process. Please try a simpler version of your question."}
        
        # Generic fallback for other errors
        else:
            fallback = get_helpful_fallback(body.query)
            return {"response": fallback} 