"""
Query handlers module.
Contains functions for handling specific query types including crypto, market trends, and conflict detection.
"""

import logging
import re
from typing import Dict, List, Any

from .data_providers import fetch_market_gainers, fetch_market_losers
from .data_providers import (
    fetch_crypto_by_symbol,
    fetch_coingecko_crypto_data,
    fetch_global_market_data,
    fetch_memecoin_data,
    fetch_token_by_contract,
    fetch_top_gainers_losers,
    fetch_top_memecoins,
    search_coins_markets,
)
from .moralis_provider import (
    fetch_pumpfun_trending,
    fetch_trending_tokens,
    fetch_wallet_tokens,
)
from .ticker_services import get_ticker_quotes


async def handle_crypto_queries(
    query: str,
    ticker_data_for_prompt_list: List[Dict],
    query_context: Dict,
    query_intent: Dict,
    original_query: str
) -> tuple[List[Dict], Dict]:
    """
    Handle cryptocurrency-specific queries including contract addresses,
    memecoins, trending tokens, and wallet analysis.
    
    Returns:
        tuple: (updated_ticker_data, updated_query_context)
    """
    # Check for contract address in query
    contract_pattern = re.compile(r'0x[a-fA-F0-9]{40}')
    contract_match = contract_pattern.search(query)
    
    if contract_match:
        contract_address = contract_match.group(0)
        print(f"DEBUG: Detected contract address in query: {contract_address}")
        # Default to ethereum, but could extract chain from query in the future
        asset_platform = "ethereum"
        
        # Fetch token data by contract address
        token_data = await fetch_token_by_contract(asset_platform, contract_address)
        if token_data:
            # Add to ticker data list
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
            print(f"DEBUG: Found token data for contract {contract_address}")
        else:
            query_context["limitations"] = query_context.get("limitations", []) + [
                f"Unable to retrieve data for contract address {contract_address}. Will analyze using general market data."
            ]
    
    # Check if this is a memecoin query
    memecoin_terms = ['memecoin', 'meme coin', 'meme token', 'doge', 'shib', 'pepe']
    is_memecoin_query = any(term in query.lower() for term in memecoin_terms)
    
    if is_memecoin_query:
        print(f"DEBUG: Detected memecoin query: {query}")
        
        # First, get the memecoin category data
        memecoin_category = await fetch_memecoin_data()
        
        # Then, get top memecoins
        top_memecoins = await fetch_top_memecoins()
        
        if memecoin_category or top_memecoins:
            query_context["memecoin_data"] = {
                "category": memecoin_category,
                "top_coins": top_memecoins
            }
            print(f"DEBUG: Added memecoin data to response context")
            
            # If we don't have specific ticker data, add some top memecoins
            if not ticker_data_for_prompt_list and top_memecoins:
                for coin in top_memecoins[:3]:  # Add top 3 memecoins
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
                print(f"DEBUG: Added top {len(top_memecoins[:3])} memecoins to ticker data")
    
    # Check if this is a cryptocurrency query
    crypto_terms = ['crypto', 'coin', 'token', 'eth', 'btc', 'blockchain', 'memecoin', 'bitcoin', 'ethereum']
    potential_token_words = re.findall(r'\b([A-Za-z0-9]{2,8})\b', query)
    is_crypto_query = any(term in query.lower() for term in crypto_terms) or contract_match or any(len(word) >= 2 and len(word) <= 8 for word in potential_token_words)
    
    # Add Moralis trending tokens data for crypto queries
    if is_crypto_query and query_intent.get("type") in ["crypto_lookup", "market_overview"]:
        print(f"DEBUG: Fetching Moralis trending tokens for crypto query")
        
        # Determine which chains to check based on query
        chains_to_check = ["eth"]  # Default to Ethereum
        
        # Check for chain-specific terms
        if any(term in query.lower() for term in ["bsc", "binance", "bnb"]):
            chains_to_check.append("bsc")
        if any(term in query.lower() for term in ["polygon", "matic", "poly"]):
            chains_to_check.append("polygon")
        if any(term in query.lower() for term in ["base"]):
            chains_to_check.append("base")
        
        # If general crypto query, check multiple chains
        if any(term in query.lower() for term in ["trending", "hot", "popular", "new"]):
            chains_to_check = ["eth", "bsc", "polygon", "base"]
        
        # Fetch trending tokens from multiple chains
        moralis_trending = []
        for chain in chains_to_check:
            chain_tokens = await fetch_trending_tokens(chain, limit=10)
            moralis_trending.extend(chain_tokens)
        
        if moralis_trending:
            query_context["moralis_trending_tokens"] = moralis_trending
            print(f"DEBUG: Added {len(moralis_trending)} Moralis trending tokens")
            
            # If we're looking for trending tokens and don't have specific tickers
            if any(term in query.lower() for term in ["trending", "hot", "popular"]) and not ticker_data_for_prompt_list:
                # Add top trending tokens
                for token in moralis_trending[:6]:  # Top 6 trending tokens
                    if token.get("price_usd"):
                        ticker_data_for_prompt_list.append({
                            "name": token.get("name", ""),
                            "symbol": token.get("symbol", ""),
                            "price": token.get("price_usd", 0),
                            "change": token.get("price_change_24h", 0),
                            "market_cap": token.get("market_cap", 0),
                            "volume": token.get("volume_24h", 0),
                            "chain": token.get("chain", ""),
                            "data_source": "moralis"
                        })
                print(f"DEBUG: Added {len(ticker_data_for_prompt_list)} trending tokens from Moralis")
    
    # Add Pump.fun data for meme/Solana queries
    if any(term in query.lower() for term in ["pump", "pumpfun", "pump.fun", "solana", "sol", "meme"]):
        print(f"DEBUG: Fetching Pump.fun trending tokens")
        
        pumpfun_tokens = await fetch_pumpfun_trending()
        
        if pumpfun_tokens:
            query_context["pumpfun_trending"] = pumpfun_tokens
            print(f"DEBUG: Added {len(pumpfun_tokens)} Pump.fun trending tokens")
            
            # If specifically asking about pump.fun and no tickers yet
            if "pump" in query.lower() and not ticker_data_for_prompt_list:
                for token in pumpfun_tokens[:3]:  # Top 3 pump.fun tokens
                    ticker_data_for_prompt_list.append({
                        "name": token.get("name", ""),
                        "symbol": token.get("symbol", ""),
                        "price": token.get("price_usd", 0),
                        "change": 0,  # Not available from pump.fun
                        "market_cap": token.get("market_cap", 0),
                        "volume": 0,  # Not available
                        "platform": "pump.fun",
                        "bonding_curve": token.get("bonding_curve_percentage", 0),
                        "data_source": "moralis_pumpfun"
                    })
                print(f"DEBUG: Added top Pump.fun tokens to ticker data")
    
    # Check for wallet address in query
    wallet_pattern = re.compile(r'0x[a-fA-F0-9]{40}')
    wallet_match = wallet_pattern.search(query)
    
    if wallet_match:
        wallet_address = wallet_match.group(0)
        print(f"DEBUG: Detected wallet address in query: {wallet_address}")
        
        # Analyze wallet with Moralis (one chain at a time)
        wallet_holdings = []
        for chain in ["eth", "bsc", "polygon"]:
            chain_holdings = await fetch_wallet_tokens(wallet_address, chain)
            if chain_holdings:
                wallet_holdings.extend(chain_holdings)
        
        if wallet_holdings:
            query_context["wallet_analysis"] = {"holdings": wallet_holdings}
            print(f"DEBUG: Added wallet analysis for {wallet_address}")
            
            # Add top holdings as ticker data if no specific tickers
            if not ticker_data_for_prompt_list:
                for holding in wallet_holdings[:5]:  # Top 5 holdings
                    if holding.get("price_usd") and holding.get("value_usd", 0) > 100:  # Only significant holdings
                        ticker_data_for_prompt_list.append({
                            "name": holding.get("name", ""),
                            "symbol": holding.get("symbol", ""),
                            "price": holding.get("price_usd", 0),
                            "balance": holding.get("balance", 0),
                            "value_usd": holding.get("value_usd", 0),
                            "portfolio_percentage": holding.get("portfolio_percentage", 0),
                            "data_source": "moralis_wallet"
                        })
                print(f"DEBUG: Added top wallet holdings to ticker data")
    
    # Get general cryptocurrency market data if it's a crypto query
    if is_crypto_query and not ticker_data_for_prompt_list:
        print(f"DEBUG: Detected crypto query without specific tickers: {query}")
        
        # Get global crypto market data
        global_market_data = await fetch_global_market_data()
        
        if global_market_data:
            query_context["crypto_market_data"] = global_market_data
            print(f"DEBUG: Added global crypto market data to response context")
            
        # Get top gainers/losers
        crypto_gainers_losers = await fetch_top_gainers_losers()
        if crypto_gainers_losers:
            query_context["crypto_gainers_losers"] = crypto_gainers_losers
            print(f"DEBUG: Added crypto gainers/losers to response context")
            
            # If still no ticker data, add some top crypto gainers
            if not ticker_data_for_prompt_list and 'top_gainers' in crypto_gainers_losers:
                for coin in crypto_gainers_losers['top_gainers'][:3]:  # Add top 3 gainers
                    ticker_data_for_prompt_list.append({
                        "name": coin["name"],
                        "symbol": coin["symbol"],
                        "price": coin["usd"],
                        "change": 0,  # Not available in this response
                        "market_cap": 0,  # Not available in this response
                        "volume": coin.get("usd_24h_vol", 0),
                        "data_source": "coingecko"
                    })
                print(f"DEBUG: Added top crypto gainers to ticker data")
    
    return ticker_data_for_prompt_list, query_context


async def handle_market_trends_and_fallbacks(
    query: str,
    ticker_data_for_prompt_list: List[Dict],
    query_context: Dict,
    has_ticker_terms: bool,
    is_crypto_query: bool,
    original_query: str
) -> tuple[List[Dict], Dict]:
    """
    Handle market trend queries and ticker fallbacks.
    
    Returns:
        tuple: (updated_ticker_data, updated_query_context)
    """
    # Initialize flags for token resolution tracking
    found_specific_ticker = False
    found_specific_coin_data = False
    
    # Handle ticker searches that weren't found
    if has_ticker_terms and not ticker_data_for_prompt_list:
        # Check if this is a market trend query
        trend_terms = ['trend', 'bullish', 'bearish', 'gaining', 'losing', 'performing', 'best', 'worst', 'top', 'movers']
        is_trend_query = any(term in query.lower() for term in trend_terms)
        
        if is_trend_query:
            # For market trend queries, fetch market gainers/losers directly
            print(f"DEBUG: Detected market trend query: {query}")
            
            # Try CoinGecko first if it's crypto-related
            if is_crypto_query and not 'crypto_gainers_losers' in query_context:
                crypto_gainers_losers = await fetch_top_gainers_losers()
                if crypto_gainers_losers:
                    query_context["crypto_gainers_losers"] = crypto_gainers_losers
                    print(f"DEBUG: Added crypto gainers/losers to trend query context")
            
            # Always get stock gainers/losers as backup
            market_gainers = await fetch_market_gainers()
            market_losers = await fetch_market_losers()
            
            if market_gainers or market_losers:
                # Create a specialized context with market trend data
                query_context.update({
                    "market_gainers": market_gainers,
                    "market_losers": market_losers,
                    "is_trend_query": True
                })
                print(f"DEBUG: Using market trend data with {len(market_gainers) if market_gainers else 0} gainers and {len(market_losers) if market_losers else 0} losers")
            else:
                # Note the limitation but continue
                logging.warning(f"No valid market data found for trend query: {query}")
                query_context["limitations"] = query_context.get("limitations", []) + ["Unable to retrieve current market gainers and losers. Will analyze using available data."]
        else:
            # Try to look for any coins that might match
            if is_crypto_query:
                # Extract potential coin names
                potential_coins = re.findall(r'\b[a-zA-Z0-9]{2,10}\b', query)
                for coin in potential_coins:
                    if len(coin) <= 8:  # Allow for slightly longer symbols too
                        # Use the original query directly
                        clean_original_query = original_query
                        
                        # For ETH specifically, force crypto lookup
                        if coin.upper() == "ETH":
                            print(f"DEBUG: ETH detected - forcing crypto lookup for Ethereum")
                            # Force search for ethereum directly
                            search_results = await search_coins_markets("ethereum")
                            if search_results and search_results.get('coins'):
                                eth_coin = search_results['coins'][0]  # Should be Ethereum
                                coin_data = await fetch_coingecko_crypto_data(crypto_id=eth_coin.get('id'))
                                if coin_data:
                                    ticker_data_for_prompt_list.append({
                                        "name": coin_data["name"],
                                        "symbol": coin_data["symbol"],
                                        "price": coin_data["price"],
                                        "change": coin_data.get("changesPercentage", 0),
                                        "market_cap": coin_data.get("marketCap", 0),
                                        "volume": coin_data.get("volume", 0),
                                        "data_source": "coingecko"
                                    })
                                    found_specific_ticker = True
                                    print(f"DEBUG: Found Ethereum crypto data via forced crypto lookup")
                                    break
                        else:
                            # Pass both the symbol and the clean query for better token resolution
                            coin_data = await fetch_crypto_by_symbol(coin, original_query=clean_original_query)
                            if coin_data:
                                ticker_data_for_prompt_list.append({
                                    "name": coin_data["name"],
                                    "symbol": coin_data["symbol"],
                                    "price": coin_data["price"],
                                    "change": coin_data.get("changesPercentage", 0),
                                    "market_cap": coin_data.get("marketCap", 0),
                                    "volume": coin_data.get("volume", 0),
                                    "data_source": coin_data.get("data_source", "unknown")
                                })
                                found_specific_ticker = True
                                print(f"DEBUG: Found coin data for symbol {coin} via symbol search")
                                break

            # Try to find specific coin data for the query
            if not found_specific_ticker and not found_specific_coin_data:
                # Extract potential token references from the query
                multi_word_matches = re.findall(r'\b([A-Za-z0-9]+(\s+[A-Za-z0-9]+)+)\b', query)
                potential_tokens = [match[0] for match in multi_word_matches] if multi_word_matches else []
                
                # Common words to filter out (stopwords)
                common_words = {'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'had', 'has', 'for', 'not', 'on', 'with', 'as', 'do', 'does', 'did', 'by', 'but', 'from', 'or', 'an', 'this', 'these', 'those', 'their', 'at', 'my', 'so', 'if', 'about', 'should', 'would', 'could', 'can', 'will', 'into', 'long', 'short', 'buy', 'sell'}
                
                # Then add single words that could be tokens or symbols
                single_words = re.findall(r'\b([A-Za-z0-9]{2,})\b', query)
                potential_tokens.extend([word for word in single_words if word.lower() not in common_words and len(word) >= 2])
                
                print(f"DEBUG: Extracted potential token references: {potential_tokens}")
                
                for token_ref in potential_tokens:
                    # First try direct symbol lookup for each potential token
                    print(f"DEBUG: Trying direct symbol lookup for '{token_ref}' with original query '{original_query[:50]}...'")
                    
                    # Use the original query directly
                    clean_original_query = original_query
                    
                    # Pass the clean query for better token resolution
                    coin_data = await fetch_crypto_by_symbol(token_ref, original_query=clean_original_query)
                    
                    if coin_data:
                        ticker_data_for_prompt_list.append({
                            "name": coin_data["name"],
                            "symbol": coin_data["symbol"],
                            "price": coin_data["price"],
                            "change": coin_data.get("changesPercentage", 0),
                            "market_cap": coin_data.get("marketCap", 0),
                            "volume": coin_data.get("volume", 0),
                            "data_source": coin_data.get("data_source", "unknown")
                        })
                        found_specific_coin_data = True
                        print(f"DEBUG: Found coin data for '{token_ref}' via direct symbol lookup")
                        break
                    
                    # If direct lookup fails, try fuzzy search with the CoinGecko search API
                    print(f"DEBUG: Direct lookup failed for '{token_ref}', trying search API")
                    search_results = await search_coins_markets(token_ref)
                    
                    if search_results and search_results.get('coins'):
                        coins_found = search_results['coins']
                        print(f"DEBUG: Found {len(coins_found)} coins via search for '{token_ref}'")
                        
                        # Try the top 3 results, in case the first one doesn't have market data
                        for i, potential_match in enumerate(coins_found[:3]):
                            match_id = potential_match.get('id')
                            match_name = potential_match.get('name', 'Unknown')
                            match_symbol = potential_match.get('symbol', 'N/A')
                            
                            print(f"DEBUG: Trying search result #{i+1}: {match_name} ({match_symbol})")
                            
                            if not match_id:
                                continue
                            
                            # Get full market data for this match
                            coin_data = await fetch_coingecko_crypto_data(crypto_id=match_id)
                            
                            if coin_data:
                                # Successfully found market data for this token
                                ticker_data_for_prompt_list.append({
                                    "name": coin_data.get("name", match_name),
                                    "symbol": coin_data.get("symbol", match_symbol),
                                    "price": coin_data.get("price", 0),
                                    "change": coin_data.get("changesPercentage", 0),
                                    "market_cap": coin_data.get("marketCap", 0),
                                    "volume": coin_data.get("volume", 0),
                                    "data_source": "coingecko"
                                })
                                found_specific_coin_data = True
                                print(f"DEBUG: Successfully found market data for search result: {match_name}")
                                break  # Stop after finding the first good match
                            else:
                                print(f"DEBUG: Could not get market data for {match_name}")
                        
                        # If we found a match with market data, break the outer loop too
                        if found_specific_coin_data:
                            break
                            
                query_context["limitations"] = query_context.get("limitations", []) + ["Unable to resolve specific ticker symbols from your query. Will analyze using general market data."]
            
        # Always try to give some value even with limitations
        query_context["attempt_answer_despite_limitations"] = True
    
    # ENHANCED FALLBACK: If still no coin data found, try direct search with full query
    if not found_specific_coin_data and is_crypto_query and not ticker_data_for_prompt_list:
        print(f"DEBUG: Enhanced fallback - trying direct CoinGecko search for: '{query}' (original: '{original_query}')")
        
        # Use the query directly
        clean_query = query
        
        # Try direct search with the clean query
        search_results = await search_coins_markets(clean_query)
        
        if search_results and search_results.get('coins'):
            print(f"DEBUG: Enhanced fallback found {len(search_results.get('coins', []))} results for '{query}'")
            for i, result in enumerate(search_results.get('coins', [])[:3]):
                print(f"DEBUG: Result #{i+1}: {result.get('name')} ({result.get('symbol')}) - ID: {result.get('id')}")
            
            top_result = search_results['coins'][0]
            print(f"DEBUG: Enhanced fallback selecting top result: {top_result.get('name')} ({top_result.get('symbol')})")
            
            # Get full market data for the top result
            coin_data = await fetch_coingecko_crypto_data(crypto_id=top_result.get('id'))
            
            if coin_data:
                ticker_data_for_prompt_list.append({
                    "name": coin_data.get("name", ""),
                    "symbol": coin_data.get("symbol", ""),
                    "price": coin_data.get("price", 0),
                    "change": coin_data.get("changesPercentage", 0),
                    "market_cap": coin_data.get("marketCap", 0),
                    "volume": coin_data.get("volume", 0),
                    "data_source": "coingecko"
                })
                found_specific_coin_data = True
                print(f"DEBUG: Enhanced fallback successful for '{query}' -> found {coin_data.get('name')}")
        else:
            print(f"DEBUG: Enhanced fallback - no results found for '{query}'")
    
    return ticker_data_for_prompt_list, query_context


async def detect_ticker_conflicts(ticker_data_list: List[Dict], original_query: str) -> List[Dict]:
    """
    Detect potential ticker conflicts between crypto and traditional assets by checking multiple data sources.
    
    Args:
        ticker_data_list: List of ticker data dictionaries
        original_query: The original user query
        
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