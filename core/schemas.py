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


# Enhanced Schemas for Comprehensive Backtesting Database API

class HistoricalMarketDataOut(Schema):
    """Historical market data output schema."""
    id: int
    timestamp: datetime
    analysis_date: date
    symbol: str
    asset_type: str
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[int] = None
    change_1d: Optional[float] = None
    change_7d: Optional[float] = None
    change_30d: Optional[float] = None
    rsi_14: Optional[float] = None
    ema_50: Optional[float] = None
    sma_200: Optional[float] = None
    screener_position: Optional[str] = None
    confidence_score: Optional[float] = None
    rank_in_category: Optional[int] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    data_source: str

class HistoricalMarketDataIn(Schema):
    """Historical market data input schema."""
    analysis_date: date
    symbol: str
    asset_type: str = 'STOCK'
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[int] = None
    change_1d: Optional[float] = None
    change_7d: Optional[float] = None
    change_30d: Optional[float] = None
    rsi_14: Optional[float] = None
    ema_50: Optional[float] = None
    sma_200: Optional[float] = None
    screener_position: Optional[str] = None
    confidence_score: Optional[float] = None
    rank_in_category: Optional[int] = None
    sector: Optional[str] = None
    industry: Optional[str] = None

class PortfolioPositionOut(Schema):
    """Portfolio position output schema."""
    id: int
    symbol: str
    asset_type: str
    position_type: str
    quantity: float
    entry_price: float
    current_price: float
    position_value: float
    weight: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    confidence_score: Optional[float] = None
    original_rank: Optional[int] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

class PortfolioSnapshotOut(Schema):
    """Portfolio snapshot output schema."""
    id: int
    timestamp: datetime
    snapshot_date: date
    portfolio_name: str
    strategy_type: str
    total_value: float
    long_exposure: float
    short_exposure: float
    cash_balance: float
    daily_return: Optional[float] = None
    cumulative_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    volatility: Optional[float] = None
    var_95: Optional[float] = None
    beta: Optional[float] = None
    market_sentiment_score: Optional[float] = None
    benchmark_return: Optional[float] = None
    positions: List[PortfolioPositionOut] = []

class PortfolioSnapshotIn(Schema):
    """Portfolio snapshot input schema."""
    snapshot_date: date
    portfolio_name: str = 'default'
    strategy_type: str = 'LONG_SHORT'
    total_value: float = 100000.00
    long_exposure: float = 0.00
    short_exposure: float = 0.00
    cash_balance: float = 0.00
    daily_return: Optional[float] = None
    cumulative_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    volatility: Optional[float] = None
    var_95: Optional[float] = None
    beta: Optional[float] = None
    market_sentiment_score: Optional[float] = None
    benchmark_return: Optional[float] = None

class BacktestResultOut(Schema):
    """Backtest result output schema."""
    id: int
    timestamp: datetime
    strategy_name: str
    start_date: date
    end_date: date
    initial_capital: float
    rebalance_frequency: str
    max_positions: int
    position_sizing: str
    final_value: float
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: Optional[float] = None
    var_95: Optional[float] = None
    beta: Optional[float] = None
    alpha: Optional[float] = None
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Optional[float] = None
    avg_win: Optional[float] = None
    avg_loss: Optional[float] = None
    profit_factor: Optional[float] = None
    benchmark_return: Optional[float] = None
    excess_return: Optional[float] = None
    information_ratio: Optional[float] = None
    configuration: dict
    execution_time: Optional[str] = None
    data_quality_score: Optional[float] = None

class BacktestResultIn(Schema):
    """Backtest result input schema."""
    strategy_name: str
    start_date: date
    end_date: date
    initial_capital: float = 100000.00
    rebalance_frequency: str = 'DAILY'
    max_positions: int = 10
    position_sizing: str = 'EQUAL_WEIGHT'
    final_value: float
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: Optional[float] = None
    var_95: Optional[float] = None
    beta: Optional[float] = None
    alpha: Optional[float] = None
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: Optional[float] = None
    avg_win: Optional[float] = None
    avg_loss: Optional[float] = None
    profit_factor: Optional[float] = None
    benchmark_return: Optional[float] = None
    excess_return: Optional[float] = None
    information_ratio: Optional[float] = None
    configuration: dict = {}
    data_quality_score: Optional[float] = None

class TradingSignalOut(Schema):
    """Trading signal output schema."""
    id: int
    timestamp: datetime
    signal_date: date
    symbol: str
    asset_type: str
    signal_type: str
    strength: str
    confidence_score: float
    signal_price: float
    target_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    timeframe: str
    reasoning: str
    technical_factors: List[str]
    fundamental_factors: List[str]
    status: str
    exit_price: Optional[float] = None
    exit_date: Optional[date] = None
    realized_return: Optional[float] = None
    holding_period: Optional[int] = None

class TradingSignalIn(Schema):
    """Trading signal input schema."""
    signal_date: date
    symbol: str
    asset_type: str = 'STOCK'
    signal_type: str
    strength: str = 'MODERATE'
    confidence_score: float
    signal_price: float
    target_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    timeframe: str = '1-7 days'
    reasoning: str = ''
    technical_factors: List[str] = []
    fundamental_factors: List[str] = []

# Query Schemas for Filtering and Aggregation

class MarketDataQuery(Schema):
    """Query schema for market data filtering."""
    symbols: Optional[List[str]] = None
    asset_types: Optional[List[str]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    screener_positions: Optional[List[str]] = None
    min_confidence_score: Optional[float] = None
    sectors: Optional[List[str]] = None
    limit: int = 100
    offset: int = 0

class PortfolioQuery(Schema):
    """Query schema for portfolio filtering."""
    portfolio_names: Optional[List[str]] = None
    strategy_types: Optional[List[str]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    min_total_value: Optional[float] = None
    max_total_value: Optional[float] = None
    limit: int = 100
    offset: int = 0

class BacktestQuery(Schema):
    """Query schema for backtest filtering."""
    strategy_names: Optional[List[str]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    min_return: Optional[float] = None
    max_return: Optional[float] = None
    min_sharpe_ratio: Optional[float] = None
    rebalance_frequencies: Optional[List[str]] = None
    limit: int = 100
    offset: int = 0

class SignalQuery(Schema):
    """Query schema for trading signal filtering."""
    symbols: Optional[List[str]] = None
    asset_types: Optional[List[str]] = None
    signal_types: Optional[List[str]] = None
    statuses: Optional[List[str]] = None
    min_confidence_score: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    limit: int = 100
    offset: int = 0

# Aggregation and Analytics Schemas

class PerformanceMetrics(Schema):
    """Performance metrics aggregation schema."""
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None

class AssetPerformance(Schema):
    """Asset performance analytics schema."""
    symbol: str
    asset_type: str
    total_signals: int
    successful_signals: int
    win_rate: float
    avg_return: float
    total_return: float
    best_return: float
    worst_return: float
    avg_holding_period: Optional[float] = None

class StrategyComparison(Schema):
    """Strategy comparison analytics schema."""
    strategy_name: str
    backtest_count: int
    avg_return: float
    avg_sharpe_ratio: float
    avg_max_drawdown: float
    best_return: float
    worst_return: float
    win_rate: float

class MarketScreenerAnalytics(Schema):
    """Market screener analytics schema."""
    total_screeners: int
    avg_sentiment_score: float
    most_common_sentiment: str
    top_performing_stocks: List[AssetPerformance]
    top_performing_cryptos: List[AssetPerformance]
    sector_performance: dict
    monthly_performance: dict

# Export Schemas

class ExportRequest(Schema):
    """Export request schema."""
    data_type: str  # 'historical_data', 'portfolios', 'backtests', 'signals'
    format: str = 'csv'  # 'csv', 'json', 'excel'
    query_params: dict = {}
    include_metadata: bool = True

class ExportResponse(Schema):
    """Export response schema."""
    download_url: str
    file_size: int
    record_count: int
    export_id: str
    created_at: datetime
    expires_at: datetime

# Paginated Response Types for New Models

class PaginatedHistoricalData(Schema):
    """Paginated historical market data response."""
    data: List[HistoricalMarketDataOut]
    pagination: PaginationMeta

class PaginatedPortfolioSnapshots(Schema):
    """Paginated portfolio snapshots response."""
    data: List[PortfolioSnapshotOut]
    pagination: PaginationMeta

class PaginatedBacktestResults(Schema):
    """Paginated backtest results response."""
    data: List[BacktestResultOut]
    pagination: PaginationMeta

class PaginatedTradingSignals(Schema):
    """Paginated trading signals response."""
    data: List[TradingSignalOut]
    pagination: PaginationMeta