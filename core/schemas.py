from ninja import Schema
from typing import List, Optional, Generic, TypeVar
from datetime import datetime, date
from .models import Org

T = TypeVar('T')

class PaginationMeta(Schema):
    """Pagination metadata for API responses."""
    limit: int
    has_more: bool
    next_cursor: Optional[int] = None
    prev_cursor: Optional[int] = None

class PaginatedResponse(Schema, Generic[T]):
    """Generic paginated response schema."""
    data: List[T]
    pagination: PaginationMeta

class APIKeySchema(Schema):
    id: int
    org_id: int
    user_id: str  # adding the user_id field.
    name: str
    key: str
    client_side_key: str
    allowed_domains: List[str]
    is_revoked: Optional[bool]
    is_unlimited: Optional[bool]
    expires_at: Optional[datetime]
    monthly_limit: Optional[int]
    permission_level: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        arbitrary_types_allowed = True

class CreateAPIKeySchema(Schema):
    org_id: int
    user_id: str
    name: str
    allowed_domains: List[str]
    is_revoked: Optional[bool] = False
    is_unlimited: Optional[bool] = False
    expires_at: Optional[datetime] = None
    monthly_limit: Optional[int] = 0
    permission_level: Optional[str] = None

class GetAPIKeySchema(Schema):
    user_id: str

class UpdateAPIKeySchema(Schema):
    user_id: str
    name: Optional[str] = None
    allowed_domains: Optional[List[str]] = None
    is_revoked: Optional[bool] = None
    is_unlimited: Optional[bool] = None
    expires_at: Optional[datetime] = None
    monthly_limit: Optional[int] = None
    permission_level: Optional[str] = None

class MarketAlertOut(Schema):
    """Market alert output schema."""
    id: int
    timestamp: datetime
    risk_level: str
    short_summary: str
    full_analysis: dict

class CalendarAlertOut(Schema):
    """Calendar alert output schema."""
    id: int
    timestamp: datetime
    strykr_score: float
    window_volatility_rating: float
    window_volatility_intensity: str
    short_summary: str
    full_analysis: str
    volatile_window_start: datetime
    volatile_window_end: datetime
    events_analyzed: List[dict]

class AssetRecommendation(Schema):
    """Schema for individual asset recommendation."""
    symbol: str
    name: str  # Optional name of the asset for display
    entry_price: float
    confidence_score: float  # 0-1 confidence level
    timeframe: str  # e.g., "1 day", "1 week"

class MarketScreenerResultOut(Schema):
    """Market screener result output schema."""
    id: int
    timestamp: datetime
    analysis_date: date
    top_stocks_long: List[dict]
    top_stocks_short: List[dict]
    top_cryptos_long: List[dict]
    top_cryptos_short: List[dict]
    market_sentiment_score: float
    market_sentiment: str
    explanation: str

class NewsMarketAlertOut(Schema):
    """News market alert output schema."""
    id: int
    timestamp: datetime
    summary: str
    sentiment: str
    sentiment_reasoning: str
    news_articles: List[dict]

class CryptoNewsAlertOut(Schema):
    """Crypto news alert output schema."""
    id: int
    timestamp: datetime
    summary: str
    sentiment: str
    sentiment_reasoning: str
    crypto_news_articles: List[dict]

# Paginated response types for alerts
class PaginatedCalendarAlerts(Schema):
    """Paginated calendar alerts response."""
    data: List[CalendarAlertOut]
    pagination: PaginationMeta

class PaginatedMarketAlerts(Schema):
    """Paginated market alerts response."""
    data: List[MarketAlertOut]
    pagination: PaginationMeta

class PaginatedNewsAlerts(Schema):
    """Paginated news alerts response."""
    data: List[NewsMarketAlertOut]
    pagination: PaginationMeta

class PaginatedCryptoNewsAlerts(Schema):
    """Paginated crypto news alerts response."""
    data: List[CryptoNewsAlertOut]
    pagination: PaginationMeta