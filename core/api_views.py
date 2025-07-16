import calendar as cal
import json
import logging
import re
import requests
import asyncio
from asgiref.sync import sync_to_async
from datetime import datetime, timedelta
from django.http import StreamingHttpResponse
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from django.views.decorators.gzip import gzip_page
from django.utils.decorators import method_decorator
from django.views.decorators.vary import vary_on_headers
from django.views.decorators.cache import never_cache
from typing import Annotated, Optional, List, Dict, Any
from urllib.parse import urlparse

# Import the news processor module
from core.models import NewsMarketAlert
from .news_processor import fetch_market_news

# Import enhanced data provider functions
from core.data_providers import (
    fetch_company_profile,
    fetch_key_metrics,
    fetch_ticker_news,
    fetch_earnings_info,
    fetch_sector_performance,
    fetch_market_gainers,
    fetch_market_losers,
    # CoinGecko API functions
    fetch_crypto_by_symbol,
    fetch_coingecko_crypto_data,
    search_coins_markets,
    fetch_coin_categories,
    fetch_memecoin_data,
    fetch_market_data,
    fetch_top_memecoins,
    fetch_top_gainers_losers,
    fetch_token_by_contract,
    fetch_global_market_data
)

# Import from new refactored modules
from .ai_response_endpoint import ai_response
from .api_utils import validate_api_key, http_client, client, month_numbers
from .ticker_services import (
    is_valid_ticker,
    get_ticker_quotes,
    get_enhanced_ticker_quotes,
    fetch_ticker_data,
    fetch_enhanced_ticker_data,
    fetch_asset_technical_indicators
    # Removed unused imports: fetch_smart_ticker_data, detect_ticker_conflicts
)
from .data_fetchers import (
    get_bellwether_assets,
    fetch_bellwether_assets,
    fetch_news_from_database,
    fetch_moralis_trending_tokens,
    fetch_moralis_pumpfun_tokens,
    fetch_moralis_wallet_analysis,
    fetch_economic_calendar_data,
    enhanced_parallel_asset_search
)
# AI services imports removed - using direct logic for better performance
# from .ai_services import (
#     classify_query_intent,
#     smart_asset_disambiguation, 
#     create_disambiguation_response
# )

from .bellwether_assets import BELLWETHER_ASSETS
from .calendar_builder import get_calendar_data
from .models import APIKey, AIQuery, EconomicEvents, BellwetherAsset
from .prompt_builder import get_bellwether_assets_indices, get_full_prompt, get_tickers
from .api_key_views import router as api_key_router
from .api_alert_views import router as api_alert_router
from .error_handlers import api_response_error_handler
from .response_helpers import get_helpful_fallback

# Initialize API
api = NinjaAPI()

# AIRequestBody schema for endpoint definitions
class AIRequestBody(Schema):
    query: str
    third_party_user_id: Optional[str] = ""
    return_prompt: Optional[bool] = False
    stream: Optional[bool] = False
    enable_bellwether: Optional[bool] = True  # Module 2: Controls bellwether asset processing
    enable_macro: Optional[bool] = True  # Module 3: Controls macro/calendar data inclusion


# Register the main AI response endpoint
api.post("/ai-response")(ai_response)


@api.post("/precision-ai")
async def precision_ai(request, body: AIRequestBody):
    """
    Module 1: Precision Asset Intelligence - Core Module.
    Includes base asset data - Open, Close, Volume, Market Cap, PE Ratio, etc. 
    """
    modified_body = body.dict()
    modified_body.update({"enable_bellwether": False, "enable_macro": False})
    return await ai_response(request, AIRequestBody(**modified_body))


@api.post("/bellwether-x")
async def bellwether_x(request, body: AIRequestBody):
    """
    Module 2: Bellwether X - Market Sentiment Engine
    Includes base asset data and bellwether asset analysis
    Excludes macro analysis
    """
    modified_body = body.dict()
    modified_body.update({"enable_bellwether": True, "enable_macro": False})
    return await ai_response(request, AIRequestBody(**modified_body))


@api.post("/macro-pulse")
async def macro_pulse(request, body: AIRequestBody):
    """
    Module 3: Macro Pulse
    Includes base asset data, macro/calendar analysis, and bellwether analysis
    Provides comprehensive market context with news, economic events, and bellwether assets
    """
    modified_body = body.dict()
    modified_body.update({"enable_bellwether": True, "enable_macro": True})
    return await ai_response(request, AIRequestBody(**modified_body))


@api.get("/calendar")
async def calendar(
    request,
    month: Annotated[str, r"^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)$"],
    year: Annotated[str, r"^[0-9]{4}$"],
    countries: str = "",
):
    """
    Get economic calendar data for a specific month and year.
    Optionally filter by countries.
    """
    # Get the API key from the header
    api_key = request.headers.get("X-API-KEY", default="")
    is_client_side_key = False

    # Get the domain of origin
    origin = request.headers.get("Origin", default="notarealorigin.xyz")
    domain = urlparse(origin).netloc
    domain = domain.split(":")[0]

    # Determine if API key is client side or not
    if api_key.startswith("Client "):
        api_key = api_key.replace("Client ", "", 1)
        is_client_side_key = True

    # Validate the API key
    api_key_obj = await validate_api_key(api_key, domain, is_client_side_key, request.user)
    
    # Fetch the calendar data
    calendar_data = await fetch_economic_calendar_data(request, month, year, countries)
    
    return calendar_data


# Add endpoints to create API Keys and manage them.
api.add_router("/dashboard", api_key_router)
api.add_router("/alerts", api_alert_router)