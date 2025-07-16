"""
Moralis Data Provider for blockchain data integration.
Provides trending tokens, token metadata, wallet analysis, and pump.fun integration.
"""

import logging
import os
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import httpx
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Moralis API configuration
MORALIS_API_KEY = getattr(settings, 'MORALIS_API_KEY', os.getenv("MORALIS_API_KEY", ""))
MORALIS_BASE_URL_EVM = "https://deep-index.moralis.io/api/v2.2"
MORALIS_BASE_URL_SOLANA = "https://solana-gateway.moralis.io/token"

# Debug: Log API key status on module load
if MORALIS_API_KEY:
    print(f"DEBUG: Moralis API key loaded successfully (first 5 chars: {MORALIS_API_KEY[:5]}...)")
else:
    print("DEBUG: Moralis API key NOT found - check MORALIS_API_KEY in Railway variables and Django settings")

# EVM chain mapping
EVM_CHAINS = {
    "ethereum": "eth",
    "eth": "eth",
    "base": "base",
    "polygon": "polygon",
    "matic": "polygon",
    "binance-smart-chain": "bsc",
    "bsc": "bsc",
    "avalanche": "avalanche",
    "avax": "avalanche",
    "arbitrum": "arbitrum",
    "optimism": "optimism",
    "fantom": "fantom"
}

# Create a shared HTTP client
moralis_client = httpx.AsyncClient(
    timeout=httpx.Timeout(30.0),
    limits=httpx.Limits(max_keepalive_connections=10, max_connections=30)
)


async def _make_moralis_request(url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Make a request to Moralis API with error handling and caching.
    """
    if not MORALIS_API_KEY:
        logger.warning("Moralis API key not configured")
        print("DEBUG: Moralis API key not found - please set MORALIS_API_KEY in Railway variables")
        return None
    
    headers = {
        "X-API-Key": MORALIS_API_KEY,
        "accept": "application/json"
    }
    
    try:
        response = await moralis_client.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            logger.error("Moralis API authentication failed - check API key")
            print(f"DEBUG: Moralis API returned 401 - Authentication failed. API key present: {bool(MORALIS_API_KEY)}")
            print(f"DEBUG: API key first 5 chars: {MORALIS_API_KEY[:5] if MORALIS_API_KEY else 'EMPTY'}...")
            return None
        elif response.status_code == 429:
            logger.warning("Moralis API rate limit hit")
            return None
        else:
            logger.error(f"Moralis API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error calling Moralis API: {str(e)}")
        return None


async def fetch_trending_tokens(chain: str = "eth", limit: int = 20) -> List[Dict[str, Any]]:
    """
    Fetch trending tokens from Moralis for a specific chain.
    
    Args:
        chain: The blockchain to get trending tokens for (e.g., "eth", "bsc", "polygon")
        limit: Maximum number of tokens to return
        
    Returns:
        List of trending tokens with metadata
    """
    cache_key = f"moralis_trending_{chain}_{limit}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    # Map chain to Moralis format
    moralis_chain = EVM_CHAINS.get(chain.lower(), chain.lower())
    
    url = f"{MORALIS_BASE_URL_EVM}/tokens/trending"
    params = {
        "chain": moralis_chain,
        "limit": limit
    }
    
    try:
        data = await _make_moralis_request(url, params)
        
        if not data:
            return []
        
        # Extract tokens from response
        tokens = []
        raw_tokens = data if isinstance(data, list) else data.get("result", data.get("tokens", []))
        
        for token in raw_tokens[:limit]:
            # Extract price changes
            price_changes = token.get("pricePercentChange", {})
            
            processed_token = {
                "address": token.get("tokenAddress", "").lower(),
                "symbol": token.get("symbol", "").upper(),
                "name": token.get("name", "Unknown"),
                "chain": chain,
                "price_usd": token.get("usdPrice"),
                "price_change_24h": price_changes.get("24h"),
                "price_change_1h": price_changes.get("1h"),
                "volume_24h": token.get("totalVolume", {}).get("24h") if isinstance(token.get("totalVolume"), dict) else token.get("totalVolume"),
                "market_cap": token.get("marketCap"),
                "liquidity_usd": token.get("liquidityUsd"),
                "holders": token.get("holders"),
                "logo": token.get("logo"),
                "created_at": token.get("createdAt"),
                "data_source": "moralis"
            }
            
            # Calculate buy/sell ratio if available
            buys = token.get("buyTransactions", {}).get("24h", 0)
            sells = token.get("sellTransactions", {}).get("24h", 0)
            if sells > 0:
                processed_token["buy_sell_ratio"] = buys / sells
            
            tokens.append(processed_token)
        
        # Cache for 5 minutes
        cache.set(cache_key, tokens, 300)
        logger.info(f"Fetched {len(tokens)} trending tokens for {chain} from Moralis")
        return tokens
        
    except Exception as e:
        logger.error(f"Error fetching trending tokens from Moralis: {str(e)}")
        return []


async def fetch_token_metadata(chain: str, token_address: str) -> Optional[Dict[str, Any]]:
    """
    Fetch detailed metadata for a specific token.
    
    Args:
        chain: The blockchain (e.g., "eth", "bsc", "polygon")
        token_address: The token contract address
        
    Returns:
        Token metadata dictionary or None
    """
    cache_key = f"moralis_token_{chain}_{token_address}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    moralis_chain = EVM_CHAINS.get(chain.lower(), chain.lower())
    
    url = f"{MORALIS_BASE_URL_EVM}/erc20/metadata"
    params = {
        "chain": moralis_chain,
        "addresses": [token_address]
    }
    
    try:
        data = await _make_moralis_request(url, params)
        
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        
        token_data = data[0]
        
        metadata = {
            "address": token_data.get("address", "").lower(),
            "name": token_data.get("name"),
            "symbol": token_data.get("symbol", "").upper(),
            "decimals": token_data.get("decimals"),
            "logo": token_data.get("logo"),
            "logo_hash": token_data.get("logo_hash"),
            "thumbnail": token_data.get("thumbnail"),
            "total_supply": token_data.get("total_supply"),
            "total_supply_formatted": token_data.get("total_supply_formatted"),
            "fully_diluted_valuation": token_data.get("fully_diluted_valuation"),
            "block_number": token_data.get("block_number"),
            "validated": token_data.get("validated"),
            "created_at": token_data.get("created_at"),
            "data_source": "moralis"
        }
        
        # Cache for 1 hour
        cache.set(cache_key, metadata, 3600)
        return metadata
        
    except Exception as e:
        logger.error(f"Error fetching token metadata from Moralis: {str(e)}")
        return None


async def fetch_wallet_tokens(wallet_address: str, chain: str = "eth") -> List[Dict[str, Any]]:
    """
    Fetch all tokens held by a wallet address.
    
    Args:
        wallet_address: The wallet address to analyze
        chain: The blockchain (e.g., "eth", "bsc", "polygon")
        
    Returns:
        List of token holdings with balances and values
    """
    cache_key = f"moralis_wallet_{chain}_{wallet_address}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    moralis_chain = EVM_CHAINS.get(chain.lower(), chain.lower())
    
    url = f"{MORALIS_BASE_URL_EVM}/wallets/{wallet_address}/tokens"
    params = {
        "chain": moralis_chain,
        "exclude_spam": True,
        "exclude_unverified_contracts": False
    }
    
    try:
        data = await _make_moralis_request(url, params)
        
        if not data:
            return []
        
        tokens = []
        result_list = data.get("result", []) if isinstance(data, dict) else data
        
        for token in result_list:
            processed_token = {
                "address": token.get("token_address", "native"),
                "name": token.get("name", "Unknown"),
                "symbol": token.get("symbol", "").upper(),
                "decimals": token.get("decimals", 18),
                "logo": token.get("logo"),
                "balance": token.get("balance_formatted", 0),
                "balance_raw": token.get("balance", "0"),
                "price_usd": token.get("usd_price"),
                "value_usd": token.get("usd_value"),
                "portfolio_percentage": token.get("portfolio_percentage"),
                "is_native": token.get("native_token", False),
                "verified": token.get("verified_contract", False),
                "data_source": "moralis"
            }
            
            tokens.append(processed_token)
        
        # Sort by value
        tokens.sort(key=lambda x: x.get("value_usd", 0) or 0, reverse=True)
        
        # Cache for 5 minutes
        cache.set(cache_key, tokens, 300)
        logger.info(f"Fetched {len(tokens)} tokens for wallet {wallet_address} on {chain}")
        return tokens
        
    except Exception as e:
        logger.error(f"Error fetching wallet tokens from Moralis: {str(e)}")
        return []


async def fetch_pumpfun_trending() -> List[Dict[str, Any]]:
    """
    Fetch trending Pump.fun tokens from Solana.
    
    Returns:
        List of trending Pump.fun tokens
    """
    cache_key = "moralis_pumpfun_trending"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    url = f"{MORALIS_BASE_URL_SOLANA}/token/mainnet/exchange/pumpfun/bonding"
    params = {
        "limit": 20,
        "sortBy": "volume",
        "sortOrder": "desc"
    }
    
    try:
        data = await _make_moralis_request(url, params)
        
        if not data:
            return []
        
        tokens = []
        for token in data[:20]:
            processed_token = {
                "mint": token.get("mint"),
                "name": token.get("name", "Unknown"),
                "symbol": token.get("symbol", "").upper(),
                "description": token.get("description"),
                "image_uri": token.get("imageUri"),
                "metadata_uri": token.get("metadataUri"),
                "twitter": token.get("twitter"),
                "telegram": token.get("telegram"),
                "website": token.get("website"),
                "market_cap": token.get("marketCap"),
                "price_usd": token.get("priceInSol", 0) * 150,  # Approximate USD conversion
                "bonding_curve_percentage": token.get("bondingCurvePercentage"),
                "created_timestamp": token.get("createdTimestamp"),
                "data_source": "moralis_pumpfun"
            }
            
            tokens.append(processed_token)
        
        # Cache for 3 minutes (pump.fun moves fast)
        cache.set(cache_key, tokens, 180)
        logger.info(f"Fetched {len(tokens)} trending Pump.fun tokens")
        return tokens
        
    except Exception as e:
        logger.error(f"Error fetching Pump.fun trending tokens: {str(e)}")
        return []


async def fetch_token_price_history(chain: str, token_address: str, days: int = 7) -> Optional[Dict[str, Any]]:
    """
    Fetch historical price data for a token.
    
    Args:
        chain: The blockchain (e.g., "eth", "bsc", "polygon")
        token_address: The token contract address
        days: Number of days of history to fetch
        
    Returns:
        Price history data or None
    """
    cache_key = f"moralis_price_history_{chain}_{token_address}_{days}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    moralis_chain = EVM_CHAINS.get(chain.lower(), chain.lower())
    
    # Calculate date range
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)
    
    url = f"{MORALIS_BASE_URL_EVM}/erc20/{token_address}/price"
    params = {
        "chain": moralis_chain,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat()
    }
    
    try:
        data = await _make_moralis_request(url, params)
        
        if not data:
            return None
        
        # Process the price data
        price_history = {
            "token_address": token_address,
            "chain": chain,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "prices": data.get("result", []),
            "data_source": "moralis"
        }
        
        # Cache for 30 minutes
        cache.set(cache_key, price_history, 1800)
        return price_history
        
    except Exception as e:
        logger.error(f"Error fetching token price history from Moralis: {str(e)}")
        return None


# REMOVED: search_tokens_by_name and moralis_asset_search functions
# These functions used the /tokens/search endpoint which is not available on the current Moralis plan
# Removing them eliminates 6+ failed API calls per query, improving performance by 18+ seconds
# The working Moralis endpoints (trending, metadata, wallet analysis, pump.fun) are still available above 