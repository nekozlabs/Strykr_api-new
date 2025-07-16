import json
import logging
import requests
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from openai import OpenAI
from typing import List, Optional
from ninja import Router, Query
from .models import CalendarMarketAlert, MarketAlert, MarketScreenerResult, NewsMarketAlert, CryptoNewsAlert
from ninja.errors import HttpError
from .schemas import (
    CalendarAlertOut, MarketAlertOut, MarketScreenerResultOut, AssetRecommendation, 
    NewsMarketAlertOut, CryptoNewsAlertOut, PaginatedCalendarAlerts, PaginatedMarketAlerts, 
    PaginatedNewsAlerts, PaginatedCryptoNewsAlerts, PaginationMeta
)
from .response_helpers import json_endpoint_with_real_timestamps, create_enhanced_json_response

router = Router()

@router.get("/calendar-alerts", response=PaginatedCalendarAlerts)
def list_calendar_alerts(
    request,
    limit: int = Query(100, description="Number of alerts to return (max 500)"),
    after_id: Optional[int] = Query(None, description="Return alerts with ID greater than this value"),
    before_id: Optional[int] = Query(None, description="Return alerts with ID less than this value")
):
    """List calendar alerts with pagination support."""
    # Validate and sanitize limit parameter
    limit = min(max(limit, 1), 500)  # Ensure limit is between 1 and 500
    
    # Build the queryset
    queryset = CalendarMarketAlert.objects.all()
    
    # Apply ID-based filtering for cursor pagination
    if after_id is not None:
        queryset = queryset.filter(id__gt=after_id)
    elif before_id is not None:
        queryset = queryset.filter(id__lt=before_id)
    
    # Order by ID descending (newest first) and apply limit
    queryset = queryset.order_by('-id')[:limit + 1]  # Get one extra to check if has_more
    
    # Convert to list for easier manipulation
    alerts = list(queryset)
    
    # Check if there are more results
    has_more = len(alerts) > limit
    if has_more:
        alerts = alerts[:limit]  # Remove the extra item
    
    # Calculate pagination cursors
    next_cursor = None
    prev_cursor = None
    
    if alerts:
        if has_more:
            next_cursor = alerts[-1].id  # ID of the last item for next page
        if after_id is not None or before_id is not None:
            prev_cursor = alerts[0].id  # ID of the first item for previous page
    
    # Create pagination metadata
    pagination = PaginationMeta(
        limit=limit,
        has_more=has_more,
        next_cursor=next_cursor,
        prev_cursor=prev_cursor
    )
    
    return PaginatedCalendarAlerts(data=alerts, pagination=pagination)

@router.get("/calendar-alerts/{alert_id}", response=CalendarAlertOut)
def get_calendar_alert(request, alert_id: int):
    """Get a specific calendar alert."""
    try:
        alert = CalendarMarketAlert.objects.get(id=alert_id)
        return alert
    except CalendarMarketAlert.DoesNotExist:
        raise HttpError(404, "Calendar alert not found")
    
## Market Screener Endpoints
@router.get("/market-screener", response=List[MarketScreenerResultOut])
def list_market_screener(request):
    """List all market screener alerts."""
    screener_result = MarketScreenerResult.objects.all()
    return screener_result

@router.get("/market-screener/{alert_id}", response=MarketScreenerResultOut)
def get_market_screener(request, alert_id: int):
    """Get a specific market screener alert."""
    try:
        alert = MarketScreenerResult.objects.get(id=alert_id)
        return alert
    except MarketScreenerResult.DoesNotExist:
        raise HttpError(404, "Market Screener alert not found")

## Market Alerts Endpoints
@router.get("/market-alerts", response=PaginatedMarketAlerts)
def list_market_alerts(
    request,
    limit: int = Query(100, description="Number of alerts to return (max 500)"),
    after_id: Optional[int] = Query(None, description="Return alerts with ID greater than this value"),
    before_id: Optional[int] = Query(None, description="Return alerts with ID less than this value")
):
    """List market alerts with pagination support."""
    # Validate and sanitize limit parameter
    limit = min(max(limit, 1), 500)  # Ensure limit is between 1 and 500
    
    # Build the queryset
    queryset = MarketAlert.objects.all()
    
    # Apply ID-based filtering for cursor pagination
    if after_id is not None:
        queryset = queryset.filter(id__gt=after_id)
    elif before_id is not None:
        queryset = queryset.filter(id__lt=before_id)
    
    # Order by ID descending (newest first) and apply limit
    queryset = queryset.order_by('-id')[:limit + 1]  # Get one extra to check if has_more
    
    # Convert to list for easier manipulation
    alerts = list(queryset)
    
    # Check if there are more results
    has_more = len(alerts) > limit
    if has_more:
        alerts = alerts[:limit]  # Remove the extra item
    
    # Calculate pagination cursors
    next_cursor = None
    prev_cursor = None
    
    if alerts:
        if has_more:
            next_cursor = alerts[-1].id  # ID of the last item for next page
        if after_id is not None or before_id is not None:
            prev_cursor = alerts[0].id  # ID of the first item for previous page
    
    # Create pagination metadata
    pagination = PaginationMeta(
        limit=limit,
        has_more=has_more,
        next_cursor=next_cursor,
        prev_cursor=prev_cursor
    )
    
    return PaginatedMarketAlerts(data=alerts, pagination=pagination)

@router.get("/market-alerts/{alert_id}", response=MarketAlertOut)
def get_market_alert(request, alert_id: int):
    """Get a specific market alert by ID."""
    try:
        return MarketAlert.objects.get(id=alert_id)
    except MarketAlert.DoesNotExist:
        raise HttpError(404, "Market alert not found")

## News Alert Endpoints
@router.get("/news-alerts", response=PaginatedNewsAlerts)
def list_news_alerts(
    request,
    limit: int = Query(100, description="Number of alerts to return (max 500)"),
    after_id: Optional[int] = Query(None, description="Return alerts with ID greater than this value"),
    before_id: Optional[int] = Query(None, description="Return alerts with ID less than this value")
):
    """List news alerts with pagination support."""
    # Validate and sanitize limit parameter
    limit = min(max(limit, 1), 500)  # Ensure limit is between 1 and 500
    
    # Build the queryset
    queryset = NewsMarketAlert.objects.all()
    
    # Apply ID-based filtering for cursor pagination
    if after_id is not None:
        queryset = queryset.filter(id__gt=after_id)
    elif before_id is not None:
        queryset = queryset.filter(id__lt=before_id)
    
    # Order by ID descending (newest first) and apply limit
    queryset = queryset.order_by('-id')[:limit + 1]  # Get one extra to check if has_more
    
    # Convert to list for easier manipulation
    alerts = list(queryset)
    
    # Check if there are more results
    has_more = len(alerts) > limit
    if has_more:
        alerts = alerts[:limit]  # Remove the extra item
    
    # Calculate pagination cursors
    next_cursor = None
    prev_cursor = None
    
    if alerts:
        if has_more:
            next_cursor = alerts[-1].id  # ID of the last item for next page
        if after_id is not None or before_id is not None:
            prev_cursor = alerts[0].id  # ID of the first item for previous page
    
    # Create pagination metadata
    pagination = PaginationMeta(
        limit=limit,
        has_more=has_more,
        next_cursor=next_cursor,
        prev_cursor=prev_cursor
    )
    
    return PaginatedNewsAlerts(data=alerts, pagination=pagination)

@router.get("/news-alerts/{alert_id}", response=NewsMarketAlertOut)
def get_news_alert(request, alert_id: int):
    """Get a specific news alert."""
    try:
        alert = NewsMarketAlert.objects.get(id=alert_id)
        return alert
    except NewsMarketAlert.DoesNotExist:
        raise HttpError(404, "News alert not found")

## Crypto News Alert Endpoints
@router.get("/crypto-news-alerts", response=PaginatedCryptoNewsAlerts)
def list_crypto_news_alerts(
    request,
    limit: int = Query(100, description="Number of alerts to return (max 500)"),
    after_id: Optional[int] = Query(None, description="Return alerts with ID greater than this value"),
    before_id: Optional[int] = Query(None, description="Return alerts with ID less than this value")
):
    """List crypto news alerts with pagination support."""
    # Validate and sanitize limit parameter
    limit = min(max(limit, 1), 500)  # Ensure limit is between 1 and 500
    
    # Build the queryset
    queryset = CryptoNewsAlert.objects.all()
    
    # Apply ID-based filtering for cursor pagination
    if after_id is not None:
        queryset = queryset.filter(id__gt=after_id)
    elif before_id is not None:
        queryset = queryset.filter(id__lt=before_id)
    
    # Order by ID descending (newest first) and apply limit
    queryset = queryset.order_by('-id')[:limit + 1]  # Get one extra to check if has_more
    
    # Convert to list for easier manipulation
    alerts = list(queryset)
    
    # Check if there are more results
    has_more = len(alerts) > limit
    if has_more:
        alerts = alerts[:limit]  # Remove the extra item
    
    # Calculate pagination cursors
    next_cursor = None
    prev_cursor = None
    
    if alerts:
        if has_more:
            next_cursor = alerts[-1].id  # ID of the last item for next page
        if after_id is not None or before_id is not None:
            prev_cursor = alerts[0].id  # ID of the first item for previous page
    
    # Create pagination metadata
    pagination = PaginationMeta(
        limit=limit,
        has_more=has_more,
        next_cursor=next_cursor,
        prev_cursor=prev_cursor
    )
    
    return PaginatedCryptoNewsAlerts(data=alerts, pagination=pagination)

@router.get("/crypto-news-alerts/{alert_id}", response=CryptoNewsAlertOut)
def get_crypto_news_alert(request, alert_id: int):
    """Get a specific crypto news alert."""
    try:
        alert = CryptoNewsAlert.objects.get(id=alert_id)
        return alert
    except CryptoNewsAlert.DoesNotExist:
        raise HttpError(404, "Crypto news alert not found")