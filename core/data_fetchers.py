"""
Data fetching services for external APIs and database queries.
This module centralizes all data fetching operations including news, economic calendar,
bellwether assets, and Moralis integration.
"""

import asyncio
import calendar as cal
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .api_utils import http_client, month_numbers
from .bellwether_assets import BELLWETHER_ASSETS
from .calendar_builder import get_calendar_data
from .data_providers import (
    search_coins_markets,
    fetch_token_by_contract,
)
from .error_handlers import api_response_error_handler
from .models import BellwetherAsset, EconomicEvents, NewsMarketAlert, CryptoNewsAlert

import time

# Circuit breaker for smart merging
class SmartMergeCircuitBreaker:
    """Simple circuit breaker for smart merge functionality."""
    
    def __init__(self, failure_threshold=5, timeout=300):  # 5 failures, 5 min timeout
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False
    
    def call(self, func, *args, **kwargs):
        """Call function with circuit breaker protection."""
        # Check if circuit breaker should reset
        if self.is_open and self.last_failure_time:
            if time.time() - self.last_failure_time > self.timeout:
                self.is_open = False
                self.failure_count = 0
                logging.info("Smart merge circuit breaker reset")
        
        # If circuit is open, return fallback
        if self.is_open:
            logging.warning("Smart merge circuit breaker is open, skipping merge")
            return args[0] if args else []  # Return original assets without merging
        
        try:
            result = func(*args, **kwargs)
            # Reset failure count on success
            self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.is_open = True
                logging.error(f"Smart merge circuit breaker opened after {self.failure_count} failures")
            
            logging.error(f"Smart merge failed: {str(e)}")
            # Return original assets without merging
            return args[0] if args else []

# Global circuit breaker instance
smart_merge_breaker = SmartMergeCircuitBreaker()


async def get_bellwether_assets(symbols):
    """
    Get bellwether assets from database by symbols.
    
    Args:
        symbols: List of asset symbols to fetch
        
    Returns:
        List of BellwetherAsset objects
    """
    return await sync_to_async(
        lambda: list(BellwetherAsset.objects.filter(symbol__in=symbols))
    )()


async def fetch_bellwether_assets(bellwether_assets_indices):
    """
    Fetch bellwether assets data, parallelized.
    
    Args:
        bellwether_assets_indices: List of indices for BELLWETHER_ASSETS
        
    Returns:
        List of BellwetherAsset objects
    """
    try:
        bellwether_assets_symbols = [
            BELLWETHER_ASSETS[index]["symbol"]
            for index in bellwether_assets_indices
            if index in BELLWETHER_ASSETS
        ]
        bellwether_assets_qs = await get_bellwether_assets(
            bellwether_assets_symbols
        )
    
    except Exception as e:
        bellwether_assets_qs = []
        print(f"Error fetching bellwether data: {str(e)}")
        logging.error(f"Error fetching bellwether data: {str(e)}")

    return bellwether_assets_qs


async def fetch_news_from_database():
    """
    Fetch news articles from the database's NewsMarketAlert objects.
    Returns a list of deduplicated news articles from recent alerts.
    """
    try:
        # Get the latest 8 NewsMarketAlert objects (covers last ~2 hours)
        alerts = await sync_to_async(lambda: list(NewsMarketAlert.objects.order_by('-timestamp')[:8]))()
        
        # Extract and flatten news articles
        news_articles = []
        for alert in alerts:
            news_articles.extend(alert.news_articles)
        
        # Deduplicate by headline+date
        seen = set()
        deduped_news = []
        for item in news_articles:
            key = (item.get('headline', ''), item.get('date', ''))
            if key and key not in seen:
                deduped_news.append(item)
                seen.add(key)
        
        return deduped_news[:30]  # Limit to 30 most recent unique articles
    except Exception as e:
        logging.error(f"Error fetching news from database: {str(e)}")
        return []


async def fetch_crypto_news_from_database():
    """
    Fetch crypto news articles from the database's CryptoNewsAlert objects.
    Returns a list of deduplicated crypto news articles from recent alerts.
    """
    try:
        # Get the latest 8 CryptoNewsAlert objects (covers last ~2 hours)
        alerts = await sync_to_async(lambda: list(CryptoNewsAlert.objects.order_by('-timestamp')[:8]))()
        
        # Extract and flatten crypto news articles
        crypto_news_articles = []
        for alert in alerts:
            crypto_news_articles.extend(alert.crypto_news_articles)
        
        # Deduplicate by headline+date
        seen = set()
        deduped_crypto_news = []
        for item in crypto_news_articles:
            key = (item.get('headline', ''), item.get('date', ''))
            if key and key not in seen:
                deduped_crypto_news.append(item)
                seen.add(key)
        
        return deduped_crypto_news[:30]  # Limit to 30 most recent unique crypto articles
    except Exception as e:
        logging.error(f"Error fetching crypto news from database: {str(e)}")
        return []


async def fetch_moralis_trending_tokens(chains: List[str] = ["eth", "bsc", "polygon"]) -> Dict[str, List[Dict]]:
    """
    Fetch trending tokens from Moralis for multiple chains.
    
    Args:
        chains: List of chains to fetch trending tokens for
        
    Returns:
        Dictionary with chain as key and list of trending tokens as value
    """
    try:
        from core.moralis_provider import fetch_trending_tokens
        
        # Fetch trending tokens for each chain in parallel
        tasks = []
        for chain in chains:
            tasks.append(fetch_trending_tokens(chain, limit=10))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Organize results by chain
        trending_by_chain = {}
        for i, chain in enumerate(chains):
            if i < len(results) and not isinstance(results[i], Exception):
                trending_by_chain[chain] = results[i]
            else:
                trending_by_chain[chain] = []
        
        return trending_by_chain
        
    except Exception as e:
        logging.error(f"Error fetching Moralis trending tokens: {str(e)}")
        return {}


async def fetch_moralis_pumpfun_tokens() -> List[Dict]:
    """
    Fetch trending Pump.fun tokens from Solana.
    
    Returns:
        List of trending Pump.fun tokens
    """
    try:
        from core.moralis_provider import fetch_pumpfun_trending
        
        tokens = await fetch_pumpfun_trending()
        return tokens
        
    except Exception as e:
        logging.error(f"Error fetching Pump.fun tokens: {str(e)}")
        return []


async def fetch_moralis_wallet_analysis(wallet_address: str, chains: List[str] = ["eth"]) -> Dict[str, Any]:
    """
    Analyze a wallet address across multiple chains using Moralis.
    
    Args:
        wallet_address: The wallet address to analyze
        chains: List of chains to check
        
    Returns:
        Wallet analysis data including holdings and total value
    """
    try:
        from core.moralis_provider import fetch_wallet_tokens
        
        # Fetch wallet data for each chain in parallel
        tasks = []
        for chain in chains:
            tasks.append(fetch_wallet_tokens(wallet_address, chain))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        all_holdings = []
        total_value = 0
        
        for i, chain in enumerate(chains):
            if i < len(results) and not isinstance(results[i], Exception):
                holdings = results[i]
                all_holdings.extend(holdings)
                
                # Calculate total value for this chain
                for token in holdings:
                    if token.get("value_usd"):
                        total_value += token["value_usd"]
        
        # Sort all holdings by value
        all_holdings.sort(key=lambda x: x.get("value_usd", 0) or 0, reverse=True)
        
        return {
            "wallet_address": wallet_address,
            "total_value_usd": total_value,
            "chains_analyzed": chains,
            "holdings": all_holdings[:20],  # Top 20 holdings
            "token_count": len(all_holdings),
            "data_source": "moralis"
        }
        
    except Exception as e:
        logging.error(f"Error analyzing wallet with Moralis: {str(e)}")
        return None


async def fetch_economic_calendar_data(request, month, year, countries=None):
    """
    Fetch economic calendar data for a given month and year.
    
    Args:
        request: HTTP request object
        month: Month name (e.g., "jan", "feb")
        year: Year string
        countries: Optional comma-separated list of countries
        
    Returns:
        Dictionary containing calendar data
    """
    logging.debug(f"Fetching economic calendar data for {month} {year}")
    cache_key = f"economic_calendar_{month}_{year}"
    cached_data = cache.get(cache_key)
    if cached_data:
        print(f">>> DEBUG: Retrieved cached economic calendar data")
        return cached_data

    try:
        print(f">>> DEBUG: Looking for economic events with month={month}, year={year}")
        logging.debug(f"Attempting to retrieve economic events from database")
        economic_events = await EconomicEvents.objects.aget(
            month=month,
            year=year
        )
        events = economic_events.data
        print(f">>> DEBUG: Retrieved economic events: {len(events) if isinstance(events, list) else type(events)}")
        logging.debug(f"Retrieved {len(events) if isinstance(events, list) else 0} events from database")
    except Exception as e:
        logging.error(f"Error retrieving economic events from database: {str(e)}")
        events = []

    if not events:
        # Calculate the date range including 3 days before and after the month
        first_of_this_month = datetime(int(year), int(month_numbers[month]), 1)
        _, number_of_days = cal.monthrange(int(year), int(month_numbers[month]))
        start_date = first_of_this_month - timedelta(days=3)
        end_date = datetime(
            int(year), int(month_numbers[month]), number_of_days
        ) + timedelta(days=3)

        # Format dates for API request
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        # Debug FMP API key (partial for security)
        api_key = settings.FMP_API_KEY
        masked_key = api_key[:4] + "*****" + api_key[-4:] if api_key else "None"
        logging.debug(f"Using FMP API Key for economic calendar: {masked_key}")
        logging.debug(f"Fetching economic calendar from {start_date_str} to {end_date_str}")

        # Send request to the API with extended date range
        try:
            api_url = f"https://financialmodelingprep.com/api/v3/economic_calendar?from={start_date_str}&to={end_date_str}&apikey={settings.FMP_API_KEY}"
            logging.debug(f"API URL (with key masked): {api_url.replace(settings.FMP_API_KEY, masked_key)}")
            
            # Use async http_client instead of blocking requests.get
            api_response = await http_client.get(api_url)
            
            if api_response.status_code != 200:
                logging.error(f"API Error: {api_response.status_code} - {api_response.text}")
                events = []
            else:
                events = api_response.json()
                logging.debug(f"Retrieved {len(events)} events from API")
                
                # Store in database
                if len(events) > 0:
                    logging.debug("Storing economic events in database")
                    try:
                        await EconomicEvents.objects.aupdate_or_create(
                            month=month,
                            year=year,
                            defaults={
                                "month": month,
                                "year": year,
                                "data": events,
                            },
                            create_defaults={
                                "month": month,
                                "year": year,
                                "data": events,
                            },
                        )
                    except Exception as e:
                        logging.error(f"Error storing economic events in database: {str(e)}")
        except Exception as e:
            logging.error(f"Error fetching economic calendar data from API: {str(e)}")
            events = []
    country_list = []
    if countries:
        country_list = [item.strip() for item in countries.split(",")]
    
    # Cache the data - in the format we want.
    calendar_data = get_calendar_data(month, year, events, country_list)
    
    print(f">>> ECONOMIC CALENDAR DEBUG: calendar_data keys: {calendar_data.keys() if isinstance(calendar_data, dict) else 'not dict'}")
    if 'week' in calendar_data:
        print(f">>> ECONOMIC CALENDAR DEBUG: week dates: {list(calendar_data['week'].keys())}")
        print(f">>> ECONOMIC CALENDAR DEBUG: sample from first date - top_10_events count: {len(calendar_data['week'][list(calendar_data['week'].keys())[0]]['top_10_events']) if calendar_data['week'] else 'no data'}")
    
    cache.set(cache_key, calendar_data, timeout=3600)  # Cache for 1 hour

    return calendar_data


async def enhanced_parallel_asset_search(search_terms: List[str], original_query: str) -> List[Dict]:
    """
    Enhanced parallel asset search across multiple data sources.
    Searches FMP, CoinGecko, Moralis, and includes simple token lookup for fast results.
    
    Args:
        search_terms: List of terms to search for
        original_query: The original user query for context
        
    Returns:
        List of found assets with metadata and confidence scores
    """
    
    # Fast-path: Try simple token lookup first for crypto-like queries
    fast_results = []
    crypto_indicators = ['crypto', 'coin', 'token', 'meme', 'blockchain']
    is_crypto_query = any(indicator in original_query.lower() for indicator in crypto_indicators)
    
    if is_crypto_query:
        from .ticker_services import simple_token_lookup, convert_token_to_asset
        for term in search_terms:
            token_matches = await simple_token_lookup(term)
            if token_matches and token_matches[0]['confidence'] > 0.9:
                # High confidence match - use it
                fast_results.append(convert_token_to_asset(token_matches[0]))
        
        # If we found high-confidence matches, return them quickly
        if fast_results:
            return fast_results
    
    async def search_fmp_assets(term: str) -> List[Dict]:
        """Search Financial Modeling Prep for assets (stocks and crypto)."""
        try:
            results = []
            # Try regular search first
            search_url = f"https://financialmodelingprep.com/api/v3/search?query={term}&limit=5&apikey={settings.FMP_API_KEY}"
            response = await http_client.get(search_url)
            
            if response.status_code == 200:
                data = response.json()
                for item in data[:3]:  # Top 3 results
                    symbol = item.get("symbol", "").upper()
                    is_crypto = symbol.endswith(("USD", "USDT", "BTC", "ETH"))
                    results.append({
                        "name": item.get("name", ""),
                        "symbol": symbol,
                        "exchange": item.get("stockExchange", ""),
                        "source": "fmp",
                        "confidence": 0.9 if term.lower() in symbol.lower() else 0.7,
                        "type": "crypto" if is_crypto else "stock"
                    })
            
            # For potential crypto (2-5 chars), also try USD format
            if len(term) >= 2 and len(term) <= 5 and term.isalpha():
                crypto_term = f"{term.upper()}USD"
                crypto_url = f"https://financialmodelingprep.com/api/v3/search?query={crypto_term}&limit=3&apikey={settings.FMP_API_KEY}"
                crypto_response = await http_client.get(crypto_url)
                
                if crypto_response.status_code == 200:
                    crypto_data = crypto_response.json()
                    for item in crypto_data[:2]:  # Top 2 crypto results
                        symbol = item.get("symbol", "").upper()
                        if symbol.endswith("USD"):  # Crypto confirmed
                            # Higher confidence for exact crypto match
                            confidence = 0.95 if term.upper() == symbol.replace("USD", "") else 0.8
                            results.append({
                                "name": item.get("name", ""),
                                "symbol": symbol,
                                "exchange": item.get("stockExchange", ""),
                                "source": "fmp",
                                "confidence": confidence,
                                "type": "crypto"
                            })
            
            return results
        except Exception as e:
            logging.error(f"FMP search error for '{term}': {str(e)}")
        return []
    
    async def search_coingecko_enhanced(term: str) -> List[Dict]:
        """Enhanced CoinGecko search with better matching."""
        try:
            # Strip USD suffix for search (same logic as in search_coins_markets)
            processed_term = term
            if term.upper().endswith('USD'):
                processed_term = term[:-3]
            
            # Use the existing search function
            search_results = await search_coins_markets(term)
            
            if not search_results or not search_results.get('coins'):
                return []
            
            # Format the results with confidence scoring using the processed term
            formatted_results = []
            for coin in search_results['coins'][:5]:  # Top 5 results
                # Calculate confidence based on match quality using the processed term
                name_match = processed_term.lower() in coin.get('name', '').lower()
                symbol_match = processed_term.lower() == coin.get('symbol', '').lower()
                
                confidence = 0.5  # Base confidence
                if symbol_match:
                    confidence = 0.95
                elif name_match:
                    confidence = 0.85
                elif any(word in coin.get('name', '').lower() for word in processed_term.lower().split()):
                    confidence = 0.7
                
                formatted_results.append({
                    "name": coin.get('name', ''),
                    "symbol": coin.get('symbol', '').upper(),
                    "id": coin.get('id', ''),
                    "source": "coingecko",
                    "confidence": confidence,
                    "type": "crypto",
                    "market_cap_rank": coin.get('market_cap_rank'),
                    "thumb": coin.get('thumb', '')
                })
            
            return formatted_results
            
        except Exception as e:
            logging.error(f"CoinGecko search error for '{term}': {str(e)}")
            return []
    
    async def search_moralis_assets(term: str) -> List[Dict]:
        """Search Moralis for tokens across all major chains (simplified - no chain detection)."""
        # REMOVED: Moralis token search functionality
        # The /tokens/search endpoint is not available on current Moralis plan
        # This was causing 6+ failed API calls per query (18+ seconds wasted)
        # Other Moralis endpoints (trending, metadata, wallet analysis) still work
        return []
    
    async def search_by_contract(term: str) -> List[Dict]:
        """Search for tokens by contract address if term looks like one."""
        # Check if term looks like a contract address
        if re.match(r'^0x[a-fA-F0-9]{40}$', term):
            try:
                # Default to Ethereum, but could be enhanced to detect chain
                token_data = await fetch_token_by_contract("ethereum", term)
                if token_data:
                    return [{
                        "name": token_data.get("name", ""),
                        "symbol": token_data.get("symbol", "").upper(),
                        "contract_address": term,
                        "source": "coingecko_contract",
                        "confidence": 1.0,  # Exact match
                        "type": "crypto",
                        "platform": "ethereum"
                    }]
            except Exception as e:
                logging.error(f"Contract lookup error for '{term}': {str(e)}")
        return []
    
    # Progressive timeout helper function
    async def search_with_timeout(search_func, term, timeout_seconds):
        """Execute search function with timeout protection."""
        try:
            return await asyncio.wait_for(search_func(term), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logging.warning(f"Search timeout for {search_func.__name__} with term '{term}' after {timeout_seconds}s")
            return []
        except Exception as e:
            logging.error(f"Search error in {search_func.__name__} for '{term}': {str(e)}")
            return []
    
    # Collect all search tasks with progressive timeouts
    tasks = []
    for term in search_terms:
        # Add all search sources with tiered timeouts
        tasks.extend([
            search_with_timeout(search_fmp_assets, term, 1.5),        # Fast for stocks
            search_with_timeout(search_coingecko_enhanced, term, 2.0), # Medium for crypto
            # REMOVED: search_moralis_assets - endpoint not available on current plan
            search_with_timeout(search_by_contract, term, 1.0)         # Quick for contract lookups
        ])
    
    # Execute all searches in parallel with timeout protection
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Merge and deduplicate results
    all_assets = []
    seen_symbols = set()
    
    for result in results:
        if isinstance(result, Exception):
            logging.error(f"Search error: {str(result)}")
            continue
            
        if result and isinstance(result, list):
            for asset in result:
                # Create unique key for deduplication
                key = f"{asset.get('symbol', '').upper()}_{asset.get('source', '')}"
                if key not in seen_symbols and asset.get('symbol'):
                    seen_symbols.add(key)
                    all_assets.append(asset)
                    # Update known assets cache for fuzzy matching
                    from .ticker_services import update_known_assets
                    update_known_assets(asset)
    
    # If we have few results, try fuzzy matching as fallback (conservative)
    if len(all_assets) < 2:
        from .ticker_services import fuzzy_match_assets
        for term in search_terms:
            fuzzy_matches = fuzzy_match_assets(term, confidence_threshold=0.9)  # Very conservative
            for match in fuzzy_matches:
                key = f"{match.get('symbol', '').upper()}_fuzzy"
                if key not in seen_symbols and match.get('symbol'):
                    seen_symbols.add(key)
                    all_assets.append(match)
    
    # Smart merge assets from multiple sources with circuit breaker protection
    merged_assets = smart_merge_breaker.call(smart_merge_assets, all_assets)
    
    # ENHANCED: Apply multi-strategy enrichment to top assets (inspired by StrykrScreener)
    if merged_assets and len(merged_assets) <= 10:  # Only for manageable number of assets
        logging.info(f"🚀 APPLYING MULTI-STRATEGY ENRICHMENT to {len(merged_assets)} assets...")
        print(f"🚀 APPLYING MULTI-STRATEGY ENRICHMENT to {len(merged_assets)} assets...")  # Railway console
        
        # Use semaphore to control concurrent enrichment
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent enrichments
        
        async def enrich_with_limit(asset):
            async with semaphore:
                return await multi_strategy_asset_enrichment(asset, original_query)
        
        # Apply enrichment to assets that need more data
        enrichment_tasks = []
        for asset in merged_assets[:5]:  # Only enrich top 5 assets
            symbol = asset.get('symbol', 'Unknown')
            has_price = bool(asset.get('price'))
            confidence = asset.get('confidence', 0)
            has_volume = bool(asset.get('volume'))
            
            # Log enrichment decision for debugging
            logging.info(f"🔍 ENRICHMENT CHECK: {symbol} - price={has_price}, confidence={confidence:.2f}, volume={has_volume}")
            print(f"🔍 ENRICHMENT CHECK: {symbol} - price={has_price}, confidence={confidence:.2f}, volume={has_volume}")
            
            # FIXED: Also enrich assets that don't have volume data, even if they have price
            if not asset.get('price') or asset.get('confidence', 0) < 0.8 or not asset.get('volume'):
                logging.info(f"🔍 ENRICHING {symbol}: price={has_price}, confidence={confidence:.2f}, volume={has_volume}")
                print(f"🔍 ENRICHING {symbol}: price={has_price}, confidence={confidence:.2f}, volume={has_volume}")
                enrichment_tasks.append(enrich_with_limit(asset))
            else:
                logging.debug(f"⏭️ SKIPPING {symbol}: already has complete data (price={has_price}, confidence={confidence:.2f}, volume={has_volume})")
                print(f"⏭️ SKIPPING {symbol}: already has complete data (price={has_price}, confidence={confidence:.2f}, volume={has_volume})")
                # For assets that don't need enrichment, create a simple async function
                async def return_asset(a=asset):
                    return a
                enrichment_tasks.append(return_asset())
        
        if enrichment_tasks:
            try:
                enriched_results = await asyncio.wait_for(
                    asyncio.gather(*enrichment_tasks, return_exceptions=True), 
                    timeout=15.0  # Max 15 seconds for all enrichments
                )
                
                # Replace assets with enriched versions
                for i, result in enumerate(enriched_results[:len(merged_assets)]):
                    if not isinstance(result, Exception) and result.get('enrichment_success'):
                        original_symbol = merged_assets[i].get('symbol', 'Unknown')
                        logging.info(f"✅ ENRICHMENT SUCCESS: {original_symbol} updated with new data")
                        print(f"✅ ENRICHMENT SUCCESS: {original_symbol} updated with new data")
                        merged_assets[i] = result
                        merged_assets[i]['confidence'] = min(0.95, merged_assets[i].get('confidence', 0.5) + 0.2)
                    elif isinstance(result, Exception):
                        logging.error(f"❌ ENRICHMENT ERROR: {merged_assets[i].get('symbol', 'Unknown')} - {result}")
                        print(f"❌ ENRICHMENT ERROR: {merged_assets[i].get('symbol', 'Unknown')} - {result}")
                    else:
                        logging.info(f"⚠️ ENRICHMENT SKIPPED: {merged_assets[i].get('symbol', 'Unknown')} - no enrichment success flag")
                        print(f"⚠️ ENRICHMENT SKIPPED: {merged_assets[i].get('symbol', 'Unknown')} - no enrichment success flag")
                    
                logging.info(f"✅ Multi-strategy enrichment completed")
                
            except asyncio.TimeoutError:
                logging.warning("⏰ Multi-strategy enrichment timed out, using original data")
                print("⏰ Multi-strategy enrichment timed out, using original data")
            except Exception as e:
                logging.warning(f"💥 Multi-strategy enrichment failed: {e}")
                print(f"💥 Multi-strategy enrichment failed: {e}")
        else:
            logging.info(f"⏭️ SKIPPING ENRICHMENT: {len(merged_assets)} assets (over limit or empty)")
            print(f"⏭️ SKIPPING ENRICHMENT: {len(merged_assets)} assets (over limit or empty)")
    
    # Sort by confidence score
    merged_assets.sort(key=lambda x: x.get('confidence', 0), reverse=True)
    
    # If we have too many results, apply smart filtering
    if len(merged_assets) > 10:
        # Keep high confidence results and diverse sources
        filtered_assets = []
        sources_seen = set()
        
        # First pass: high confidence (>0.8)
        for asset in merged_assets:
            if asset.get('confidence', 0) > 0.8:
                filtered_assets.append(asset)
                sources_seen.add(asset.get('source'))
        
        # Second pass: add diversity from different sources
        for asset in merged_assets:
            if len(filtered_assets) >= 10:
                break
            if asset not in filtered_assets and asset.get('source') not in sources_seen:
                filtered_assets.append(asset)
                sources_seen.add(asset.get('source'))
        
        return filtered_assets[:10]
    
    return merged_assets 


# Enhanced multi-strategy asset enrichment inspired by StrykrScreener
async def multi_strategy_asset_enrichment(asset_data: Dict, original_query: str) -> Dict:
    """
    Enhanced asset enrichment using multiple parallel strategies.
    Inspired by StrykrScreener's multi-strategy approach.
    
    Args:
        asset_data: Basic asset data from initial search
        original_query: Original user query for context
        
    Returns:
        Enriched asset data with best available information
    """
    symbol = asset_data.get('symbol', 'Unknown')
    address = asset_data.get('address') or asset_data.get('contract_address')
    network = asset_data.get('network') or asset_data.get('chain', 'ethereum')
    coingecko_id = asset_data.get('id')  # CoinGecko ID from search
    
    # Log what we're starting with
    logging.info(f"🔍 MULTI-STRATEGY ENRICHMENT START: {symbol}")
    print(f"🔍 MULTI-STRATEGY ENRICHMENT START: {symbol}")
    logging.info(f"   Original data: price={asset_data.get('price')}, volume={asset_data.get('volume')}, market_cap={asset_data.get('market_cap')}")
    print(f"   Original data: price={asset_data.get('price')}, volume={asset_data.get('volume')}, market_cap={asset_data.get('market_cap')}")
    
    # For CoinGecko search results, we might have an ID but no address
    if not address and not coingecko_id:
        logging.debug(f"⚠️ {symbol}: No address or CoinGecko ID found, skipping enrichment")
        print(f"⚠️ {symbol}: No address or CoinGecko ID found, skipping enrichment")
        return asset_data
    
    address_str = address[:10] + "..." if address else "CoinGecko ID: " + str(coingecko_id)
    logging.info(f"🔍 MULTI-STRATEGY ENRICHMENT: {symbol} on {network} ({address_str})")
    print(f"🔍 MULTI-STRATEGY ENRICHMENT: {symbol} on {network} ({address_str})")
    
    # Network mapping for consistency
    network_mapping = {
        'eth': 'ethereum',
        'ethereum': 'ethereum',
        'bsc': 'binance-smart-chain',
        'polygon': 'polygon-pos',
        'arbitrum': 'arbitrum-one',
        'optimism': 'optimistic-ethereum',
        'base': 'base',
        'solana': 'solana'
    }
    normalized_network = network_mapping.get(network.lower(), network.lower())
    
    # Strategy 1: Enhanced FMP lookup
    async def strategy_fmp_enhanced():
        try:
            from .api_utils import http_client
            
            # Try both direct symbol and address-based lookup
            tasks = []
            
            # Direct symbol lookup
            if symbol:
                url = f"https://financialmodelingprep.com/api/v3/quote/{symbol}USD"
                tasks.append(http_client.get(url, params={'apikey': settings.FMP_API_KEY}))
            
            # Profile lookup for additional data
            if symbol:
                profile_url = f"https://financialmodelingprep.com/api/v3/profile/{symbol}"
                tasks.append(http_client.get(profile_url, params={'apikey': settings.FMP_API_KEY}))
            
            if tasks:
                results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=3.0)
                
                price_data = None
                profile_data = None
                
                for result in results:
                    if isinstance(result, Exception):
                        continue
                    if result.status_code == 200:
                        data = result.json()
                        if isinstance(data, list) and data:
                            if 'price' in data[0]:
                                price_data = data[0]
                            elif 'companyName' in data[0]:
                                profile_data = data[0]
                
                if price_data:
                    return {
                        'price': price_data.get('price'),
                        'change': price_data.get('changesPercentage'),
                        'volume': price_data.get('volume'),
                        'market_cap': price_data.get('marketCap'),
                        'strategy': 'fmp_enhanced'
                    }
                    
        except Exception as e:
            logging.debug(f"   💥 Strategy 1 (FMP Enhanced): {symbol} - {e}")
        return None
    
    # Strategy 2: CoinGecko lookup (by contract or ID)
    async def strategy_coingecko_lookup():
        try:
            from .data_providers import fetch_token_by_contract, fetch_coingecko_crypto_data
            
            token_data = None
            
            # Log what we're working with
            logging.info(f"🔍 COINGECKO STRATEGY: {symbol} - address={address[:10] + '...' if address else 'None'}, coingecko_id={coingecko_id}")
            print(f"🔍 COINGECKO STRATEGY: {symbol} - address={address[:10] + '...' if address else 'None'}, coingecko_id={coingecko_id}")
            
            # Try by contract address if available
            if address:
                # Map our network names to CoinGecko platform IDs
                platform_mapping = {
                    'ethereum': 'ethereum',
                    'binance-smart-chain': 'binance-smart-chain',
                    'polygon-pos': 'polygon-pos',
                    'arbitrum-one': 'arbitrum-one',
                    'optimistic-ethereum': 'optimistic-ethereum',
                    'base': 'base',
                    'solana': 'solana'
                }
                
                platform = platform_mapping.get(normalized_network, 'ethereum')
                logging.info(f"🔍 TRYING CONTRACT LOOKUP: {symbol} on {platform}")
                print(f"🔍 TRYING CONTRACT LOOKUP: {symbol} on {platform}")
                
                token_data = await asyncio.wait_for(
                    fetch_token_by_contract(platform, address), 
                    timeout=4.0
                )
                
                if token_data:
                    logging.info(f"✅ CONTRACT LOOKUP SUCCESS: {symbol}")
                    print(f"✅ CONTRACT LOOKUP SUCCESS: {symbol}")
                else:
                    logging.info(f"❌ CONTRACT LOOKUP FAILED: {symbol}")
                    print(f"❌ CONTRACT LOOKUP FAILED: {symbol}")
            
            # Try by CoinGecko ID if no address or contract lookup failed
            if not token_data and coingecko_id:
                logging.info(f"🔍 TRYING COINGECKO ID LOOKUP: {symbol} with ID {coingecko_id}")
                print(f"🔍 TRYING COINGECKO ID LOOKUP: {symbol} with ID {coingecko_id}")
                
                # FIXED: Use full data endpoint first (has volume data via our fixes)
                token_data = await asyncio.wait_for(
                    fetch_coingecko_crypto_data(coingecko_id),
                    timeout=4.0
                )
                
                if token_data:
                    logging.info(f"✅ COINGECKO ID LOOKUP SUCCESS: {symbol}")
                    print(f"✅ COINGECKO ID LOOKUP SUCCESS: {symbol}")
                else:
                    logging.info(f"❌ COINGECKO ID LOOKUP FAILED: {symbol}, trying simple price endpoint")
                    print(f"❌ COINGECKO ID LOOKUP FAILED: {symbol}, trying simple price endpoint")
                    
                    # Fallback to simple price endpoint only if full endpoint fails
                    from .data_providers import fetch_coin_price_by_id
                    simple_price = await asyncio.wait_for(
                        fetch_coin_price_by_id(coingecko_id),
                        timeout=2.0
                    )
                    if simple_price:
                        token_data = simple_price
                        logging.info(f"✅ SIMPLE PRICE LOOKUP SUCCESS: {symbol}")
                        print(f"✅ SIMPLE PRICE LOOKUP SUCCESS: {symbol}")
            
            if token_data:
                # Debug volume data mapping
                volume_value = token_data.get('total_volume') or token_data.get('volume') or token_data.get('volume_24h')
                logging.info(f"📊 VOLUME DEBUG: {symbol} - total_volume={token_data.get('total_volume')}, volume={token_data.get('volume')}, volume_24h={token_data.get('volume_24h')}, final={volume_value}")
                print(f"📊 VOLUME DEBUG: {symbol} - total_volume={token_data.get('total_volume')}, volume={token_data.get('volume')}, volume_24h={token_data.get('volume_24h')}, final={volume_value}")
                
                # Log successful volume retrieval
                if volume_value:
                    logging.info(f"✅ VOLUME SUCCESS: {symbol} got volume={volume_value} via CoinGecko strategy")
                    print(f"✅ VOLUME SUCCESS: {symbol} got volume={volume_value} via CoinGecko strategy")
                else:
                    logging.warning(f"❌ VOLUME MISSING: {symbol} has price but no volume from CoinGecko")
                    print(f"❌ VOLUME MISSING: {symbol} has price but no volume from CoinGecko")
                
                # Log what we're returning
                result = {
                    'price': token_data.get('current_price') or token_data.get('price'),
                    'change': token_data.get('price_change_percentage_24h') or token_data.get('changesPercentage'),
                    'volume': volume_value,
                    'market_cap': token_data.get('market_cap') or token_data.get('marketCap'),
                    'market_cap_rank': token_data.get('market_cap_rank'),
                    'image': token_data.get('image'),
                    'strategy': 'coingecko_lookup'
                }
                logging.info(f"📊 STRATEGY RESULT: {symbol} - price={result['price']}, volume={result['volume']}, market_cap={result['market_cap']}")
                print(f"📊 STRATEGY RESULT: {symbol} - price={result['price']}, volume={result['volume']}, market_cap={result['market_cap']}")
                
                return result
            else:
                logging.warning(f"❌ NO TOKEN DATA: {symbol} - all lookups failed")
                print(f"❌ NO TOKEN DATA: {symbol} - all lookups failed")
                
        except Exception as e:
            logging.error(f"💥 Strategy 2 (CoinGecko Lookup): {symbol} - {e}")
            print(f"💥 Strategy 2 (CoinGecko Lookup): {symbol} - {e}")
        return None
    
    # Strategy 3: Moralis token metadata
    async def strategy_moralis_metadata():
        try:
            from core.moralis_provider import search_tokens_by_name
            
            # Convert network name for Moralis
            moralis_chains = {
                'ethereum': 'eth',
                'binance-smart-chain': 'bsc', 
                'polygon-pos': 'polygon',
                'arbitrum-one': 'arbitrum',
                'optimistic-ethereum': 'optimism',
                'base': 'base',
                'solana': 'solana'
            }
            
            chain = moralis_chains.get(normalized_network, 'eth')
            moralis_data = await asyncio.wait_for(
                search_tokens_by_name(symbol, [chain]),
                timeout=5.0
            )
            
            if moralis_data:
                best_match = moralis_data[0]
                return {
                    'price': best_match.get('price'),
                    'change': best_match.get('price_change_24h'),
                    'volume': best_match.get('volume_24h'),
                    'market_cap': best_match.get('market_cap'),
                    'holders': best_match.get('holders_count'),
                    'liquidity': best_match.get('liquidity_usd'),
                    'strategy': 'moralis_metadata'
                }
                
        except Exception as e:
            logging.debug(f"   💥 Strategy 3 (Moralis Metadata): {symbol} - {e}")
        return None
    
    # Strategy 4: Simple token cache lookup
    async def strategy_simple_cache():
        try:
            from .ticker_services import simple_token_lookup
            
            cache_matches = await asyncio.wait_for(
                simple_token_lookup(symbol),
                timeout=1.0
            )
            
            if cache_matches and cache_matches[0].get('confidence', 0) > 0.8:
                match = cache_matches[0]
                return {
                    'price': match.get('current_price'),
                    'change': match.get('price_change_24h'),
                    'market_cap': match.get('market_cap'),
                    'market_cap_rank': match.get('market_cap_rank'),
                    'strategy': 'simple_cache'
                }
                
        except Exception as e:
            logging.debug(f"   💥 Strategy 4 (Simple Cache): {symbol} - {e}")
        return None
    
    # Execute all strategies in parallel
    strategies = [
        strategy_fmp_enhanced(),
        strategy_coingecko_lookup(),
        strategy_moralis_metadata(),
        strategy_simple_cache()
    ]
    
    try:
        # Run all strategies concurrently
        results = await asyncio.gather(*strategies, return_exceptions=True)
        
        # Find the best result (prioritize by strategy order and data completeness)
        best_result = None
        strategies_used = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logging.warning(f"   Strategy {i+1} failed: {result}")
                continue
            if result and result.get('price'):
                strategy_name = result.get('strategy', f'strategy_{i+1}')
                logging.info(f"   ✅ Strategy {i+1} ({strategy_name}) returned data: price={result.get('price')}, volume={result.get('volume')}")
                print(f"   ✅ Strategy {i+1} ({strategy_name}) returned data: price={result.get('price')}, volume={result.get('volume')}")
                
                if not best_result:
                    best_result = result
                    strategies_used.append(result['strategy'])
                    logging.info(f"   🎯 Setting as best result: {strategy_name}")
                    print(f"   🎯 Setting as best result: {strategy_name}")
                elif result.get('volume') and not best_result.get('volume'):
                    # Prefer results with volume data over those without
                    best_result = result
                    strategies_used = [result['strategy']]
                    logging.info(f"   🎯 New best result (has volume): {strategy_name}")
                    print(f"   🎯 New best result (has volume): {strategy_name}")
                elif result.get('market_cap_rank') and not best_result.get('market_cap_rank'):
                    # Prefer results with ranking only if current best doesn't have volume
                    if not best_result.get('volume') or result.get('volume'):
                        best_result = result
                        strategies_used = [result['strategy']]
                        logging.info(f"   🎯 New best result (has ranking): {strategy_name}")
                        print(f"   🎯 New best result (has ranking): {strategy_name}")
        
        # Merge best result with original asset data
        if best_result:
            enriched_data = asset_data.copy()
            enriched_data.update({
                'price': best_result.get('price'),
                'change': best_result.get('change'),
                'volume': best_result.get('volume'),
                'market_cap': best_result.get('market_cap'),
                'market_cap_rank': best_result.get('market_cap_rank'),
                'enrichment_strategy': best_result['strategy'],
                'enrichment_success': True
            })
            
            # Add additional data if available
            for key in ['image', 'holders', 'liquidity']:
                if best_result.get(key):
                    enriched_data[key] = best_result[key]
            
            logging.info(f"🎉 SUCCESS: {symbol} enriched via {', '.join(strategies_used)}")
            print(f"🎉 SUCCESS: {symbol} enriched via {', '.join(strategies_used)}")
            logging.info(f"   Final enriched data: price={enriched_data.get('price')}, volume={enriched_data.get('volume')}, market_cap={enriched_data.get('market_cap')}")
            print(f"   Final enriched data: price={enriched_data.get('price')}, volume={enriched_data.get('volume')}, market_cap={enriched_data.get('market_cap')}")
            return enriched_data
        else:
            logging.info(f"❌ FAILED: {symbol} - All strategies failed")
            print(f"❌ FAILED: {symbol} - All strategies failed")
            return asset_data
            
    except Exception as e:
        logging.warning(f"💥 EXCEPTION: {symbol} - {e}")
        print(f"💥 EXCEPTION: {symbol} - {e}")
        return asset_data


def smart_merge_assets(all_assets: List[Dict]) -> List[Dict]:
    """
    Intelligently merge assets from multiple sources with data enrichment.
    
    Args:
        all_assets: List of assets from different sources
        
    Returns:
        List of merged and enriched assets
    """
    # Group by symbol
    symbol_groups = {}
    for asset in all_assets:
        symbol = asset.get('symbol', '').upper()
        if symbol not in symbol_groups:
            symbol_groups[symbol] = []
        symbol_groups[symbol].append(asset)
    
    merged_assets = []
    for symbol, assets in symbol_groups.items():
        if len(assets) == 1:
            merged_assets.append(assets[0])
        else:
            # Multiple sources - merge intelligently
            merged_asset = merge_multi_source_asset(assets)
            merged_assets.append(merged_asset)
    
    return merged_assets


def merge_multi_source_asset(assets: List[Dict]) -> Dict:
    """
    Simplified merge of asset data from multiple sources.
    
    Args:
        assets: List of assets for the same symbol from different sources
        
    Returns:
        Merged asset (simplified)
    """
    if not assets:
        return {}
    
    if len(assets) == 1:
        return assets[0]
    
    # Simple priority: prefer Moralis > CoinGecko > others
    priority_sources = ['moralis', 'coingecko', 'coingecko_contract']
    
    # Find highest priority asset
    best_asset = assets[0]
    for asset in assets:
        if asset.get('source') in priority_sources:
            best_asset = asset
            break
    
    # Simple merge: take best asset and add missing price/market_cap from others
    merged = best_asset.copy()
    
    for asset in assets:
        if not merged.get('price') and asset.get('price'):
            merged['price'] = asset.get('price')
        if not merged.get('market_cap') and asset.get('market_cap'):
            merged['market_cap'] = asset.get('market_cap')
    
    # Mark as merged with small confidence boost
    merged['sources'] = [asset.get('source') for asset in assets]
    merged['confidence'] = min(0.99, merged.get('confidence', 0) + 0.05)
    
    return merged 