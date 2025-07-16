"""
API endpoint definitions for the Strykr API.
This module contains all the main API endpoints including ai-response, precision-ai,
bellwether-x, macro-pulse, and calendar endpoints.
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Annotated, Optional, List, Dict, Any
from urllib.parse import urlparse

from django.http import StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError

from .ai_response_endpoint import ai_response
from .api_key_views import router as api_key_router
from .api_alert_views import router as api_alert_router
from .api_backtesting_views import router as api_backtesting_router
from .api_utils import validate_api_key, client, month_numbers
from .data_fetchers import fetch_economic_calendar_data
from .models import AIQuery, EconomicEvents

# Initialize API (documentation is automatically enabled by default)
api = NinjaAPI(
    title="STRYKR AI API",
    version="1.0.0",
    description="Financial market analysis API with alerts, AI insights, and real-time data"
)


class AIRequestBody(Schema):
    """Schema for AI request body."""
    query: str
    third_party_user_id: Optional[str] = ""
    return_prompt: Optional[bool] = False
    stream: Optional[bool] = False
    enable_bellwether: Optional[bool] = True  # Module 2: Controls bellwether asset processing
    enable_macro: Optional[bool] = True  # Module 3: Controls macro/calendar data inclusion


# Register the ai_response endpoint from ai_response_endpoint
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
api.add_router("/backtesting", api_backtesting_router) 