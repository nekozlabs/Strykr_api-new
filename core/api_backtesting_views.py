"""
Comprehensive Backtesting Database API Views
Provides endpoints for market screener data tracking, historical data analysis,
portfolio management, and backtesting integration.
"""

import logging
import csv
import io
import json
import zipfile
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from decimal import Decimal

from django.db.models import Q, Count, Avg, Max, Min, Sum
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from ninja import Router, Query
from ninja.errors import HttpError

from .models import (
    MarketScreenerResult, HistoricalMarketData, PortfolioSnapshot, 
    PortfolioPosition, BacktestResult, TradingSignal
)
from .schemas import (
    # Output schemas
    HistoricalMarketDataOut, PortfolioSnapshotOut, BacktestResultOut, 
    TradingSignalOut, MarketScreenerResultOut,
    # Input schemas
    HistoricalMarketDataIn, PortfolioSnapshotIn, BacktestResultIn, 
    TradingSignalIn,
    # Query schemas
    MarketDataQuery, PortfolioQuery, BacktestQuery, SignalQuery,
    # Paginated responses
    PaginatedHistoricalData, PaginatedPortfolioSnapshots, 
    PaginatedBacktestResults, PaginatedTradingSignals,
    # Analytics schemas
    PerformanceMetrics, AssetPerformance, StrategyComparison, 
    MarketScreenerAnalytics, ExportRequest, ExportResponse
)

router = Router()

# ================================
# HISTORICAL MARKET DATA ENDPOINTS
# ================================

@router.get("/historical-data", response=PaginatedHistoricalData)
def list_historical_data(request, query: MarketDataQuery = Query(...)):
    """
    List historical market data with comprehensive filtering options.
    Supports filtering by symbols, asset types, date ranges, and screener positions.
    """
    queryset = HistoricalMarketData.objects.all()
    
    # Apply filters
    if query.symbols:
        queryset = queryset.filter(symbol__in=query.symbols)
    
    if query.asset_types:
        queryset = queryset.filter(asset_type__in=query.asset_types)
    
    if query.start_date:
        queryset = queryset.filter(analysis_date__gte=query.start_date)
    
    if query.end_date:
        queryset = queryset.filter(analysis_date__lte=query.end_date)
    
    if query.screener_positions:
        queryset = queryset.filter(screener_position__in=query.screener_positions)
    
    if query.min_confidence_score:
        queryset = queryset.filter(confidence_score__gte=query.min_confidence_score)
    
    if query.sectors:
        queryset = queryset.filter(sector__in=query.sectors)
    
    # Apply pagination
    total_count = queryset.count()
    data = list(queryset[query.offset:query.offset + query.limit])
    
    has_more = (query.offset + query.limit) < total_count
    
    from .schemas import PaginationMeta
    pagination = PaginationMeta(
        limit=query.limit,
        has_more=has_more,
        next_cursor=query.offset + query.limit if has_more else None,
        prev_cursor=max(0, query.offset - query.limit) if query.offset > 0 else None
    )
    
    return PaginatedHistoricalData(data=data, pagination=pagination)

@router.post("/historical-data", response=HistoricalMarketDataOut)
def create_historical_data(request, data: HistoricalMarketDataIn):
    """Create new historical market data entry."""
    historical_data = HistoricalMarketData.objects.create(**data.dict())
    return historical_data

@router.get("/historical-data/{data_id}", response=HistoricalMarketDataOut)
def get_historical_data(request, data_id: int):
    """Get specific historical market data by ID."""
    try:
        data = HistoricalMarketData.objects.get(id=data_id)
        return data
    except HistoricalMarketData.DoesNotExist:
        raise HttpError(404, "Historical market data not found")

@router.get("/historical-data/symbol/{symbol}", response=List[HistoricalMarketDataOut])
def get_historical_data_by_symbol(
    request, 
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
):
    """Get historical data for a specific symbol with optional date filtering."""
    queryset = HistoricalMarketData.objects.filter(symbol=symbol.upper())
    
    if start_date:
        queryset = queryset.filter(analysis_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(analysis_date__lte=end_date)
    
    return list(queryset[:limit])

# ================================
# PORTFOLIO MANAGEMENT ENDPOINTS
# ================================

@router.get("/portfolios", response=PaginatedPortfolioSnapshots)
def list_portfolios(request, query: PortfolioQuery = Query(...)):
    """List portfolio snapshots with filtering and pagination."""
    queryset = PortfolioSnapshot.objects.select_related('source_screener').prefetch_related('positions')
    
    # Apply filters
    if query.portfolio_names:
        queryset = queryset.filter(portfolio_name__in=query.portfolio_names)
    
    if query.strategy_types:
        queryset = queryset.filter(strategy_type__in=query.strategy_types)
    
    if query.start_date:
        queryset = queryset.filter(snapshot_date__gte=query.start_date)
    
    if query.end_date:
        queryset = queryset.filter(snapshot_date__lte=query.end_date)
    
    if query.min_total_value:
        queryset = queryset.filter(total_value__gte=query.min_total_value)
    
    if query.max_total_value:
        queryset = queryset.filter(total_value__lte=query.max_total_value)
    
    # Apply pagination
    total_count = queryset.count()
    data = list(queryset[query.offset:query.offset + query.limit])
    
    has_more = (query.offset + query.limit) < total_count
    
    from .schemas import PaginationMeta
    pagination = PaginationMeta(
        limit=query.limit,
        has_more=has_more,
        next_cursor=query.offset + query.limit if has_more else None,
        prev_cursor=max(0, query.offset - query.limit) if query.offset > 0 else None
    )
    
    return PaginatedPortfolioSnapshots(data=data, pagination=pagination)

@router.post("/portfolios", response=PortfolioSnapshotOut)
def create_portfolio_snapshot(request, data: PortfolioSnapshotIn):
    """Create new portfolio snapshot."""
    portfolio = PortfolioSnapshot.objects.create(**data.dict())
    return portfolio

@router.get("/portfolios/{portfolio_id}", response=PortfolioSnapshotOut)
def get_portfolio(request, portfolio_id: int):
    """Get specific portfolio snapshot with positions."""
    try:
        portfolio = PortfolioSnapshot.objects.select_related('source_screener').prefetch_related('positions').get(id=portfolio_id)
        return portfolio
    except PortfolioSnapshot.DoesNotExist:
        raise HttpError(404, "Portfolio snapshot not found")

@router.get("/portfolios/performance/{portfolio_name}", response=List[PortfolioSnapshotOut])
def get_portfolio_performance_history(
    request, 
    portfolio_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get performance history for a specific portfolio."""
    queryset = PortfolioSnapshot.objects.filter(portfolio_name=portfolio_name)
    
    if start_date:
        queryset = queryset.filter(snapshot_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(snapshot_date__lte=end_date)
    
    return list(queryset.order_by('snapshot_date'))

# ================================
# BACKTEST RESULTS ENDPOINTS
# ================================

@router.get("/backtests", response=PaginatedBacktestResults)
def list_backtest_results(request, query: BacktestQuery = Query(...)):
    """List backtest results with filtering and pagination."""
    queryset = BacktestResult.objects.all()
    
    # Apply filters
    if query.strategy_names:
        queryset = queryset.filter(strategy_name__in=query.strategy_names)
    
    if query.start_date:
        queryset = queryset.filter(start_date__gte=query.start_date)
    
    if query.end_date:
        queryset = queryset.filter(end_date__lte=query.end_date)
    
    if query.min_return:
        queryset = queryset.filter(total_return__gte=query.min_return)
    
    if query.max_return:
        queryset = queryset.filter(total_return__lte=query.max_return)
    
    if query.min_sharpe_ratio:
        queryset = queryset.filter(sharpe_ratio__gte=query.min_sharpe_ratio)
    
    if query.rebalance_frequencies:
        queryset = queryset.filter(rebalance_frequency__in=query.rebalance_frequencies)
    
    # Apply pagination
    total_count = queryset.count()
    data = list(queryset[query.offset:query.offset + query.limit])
    
    has_more = (query.offset + query.limit) < total_count
    
    from .schemas import PaginationMeta
    pagination = PaginationMeta(
        limit=query.limit,
        has_more=has_more,
        next_cursor=query.offset + query.limit if has_more else None,
        prev_cursor=max(0, query.offset - query.limit) if query.offset > 0 else None
    )
    
    return PaginatedBacktestResults(data=data, pagination=pagination)

@router.post("/backtests", response=BacktestResultOut)
def create_backtest_result(request, data: BacktestResultIn):
    """Create new backtest result."""
    backtest = BacktestResult.objects.create(**data.dict())
    return backtest

@router.get("/backtests/{backtest_id}", response=BacktestResultOut)
def get_backtest_result(request, backtest_id: int):
    """Get specific backtest result."""
    try:
        backtest = BacktestResult.objects.get(id=backtest_id)
        return backtest
    except BacktestResult.DoesNotExist:
        raise HttpError(404, "Backtest result not found")

@router.get("/backtests/strategy/{strategy_name}", response=List[BacktestResultOut])
def get_backtest_results_by_strategy(request, strategy_name: str):
    """Get all backtest results for a specific strategy."""
    return list(BacktestResult.objects.filter(strategy_name=strategy_name).order_by('-timestamp'))

# ================================
# TRADING SIGNALS ENDPOINTS
# ================================

@router.get("/signals", response=PaginatedTradingSignals)
def list_trading_signals(request, query: SignalQuery = Query(...)):
    """List trading signals with comprehensive filtering."""
    queryset = TradingSignal.objects.select_related('source_screener')
    
    # Apply filters
    if query.symbols:
        queryset = queryset.filter(symbol__in=query.symbols)
    
    if query.asset_types:
        queryset = queryset.filter(asset_type__in=query.asset_types)
    
    if query.signal_types:
        queryset = queryset.filter(signal_type__in=query.signal_types)
    
    if query.statuses:
        queryset = queryset.filter(status__in=query.statuses)
    
    if query.min_confidence_score:
        queryset = queryset.filter(confidence_score__gte=query.min_confidence_score)
    
    if query.start_date:
        queryset = queryset.filter(signal_date__gte=query.start_date)
    
    if query.end_date:
        queryset = queryset.filter(signal_date__lte=query.end_date)
    
    # Apply pagination
    total_count = queryset.count()
    data = list(queryset[query.offset:query.offset + query.limit])
    
    has_more = (query.offset + query.limit) < total_count
    
    from .schemas import PaginationMeta
    pagination = PaginationMeta(
        limit=query.limit,
        has_more=has_more,
        next_cursor=query.offset + query.limit if has_more else None,
        prev_cursor=max(0, query.offset - query.limit) if query.offset > 0 else None
    )
    
    return PaginatedTradingSignals(data=data, pagination=pagination)

@router.post("/signals", response=TradingSignalOut)
def create_trading_signal(request, data: TradingSignalIn):
    """Create new trading signal."""
    signal = TradingSignal.objects.create(**data.dict())
    return signal

@router.get("/signals/{signal_id}", response=TradingSignalOut)
def get_trading_signal(request, signal_id: int):
    """Get specific trading signal."""
    try:
        signal = TradingSignal.objects.select_related('source_screener').get(id=signal_id)
        return signal
    except TradingSignal.DoesNotExist:
        raise HttpError(404, "Trading signal not found")

@router.put("/signals/{signal_id}/update-status")
def update_signal_status(
    request, 
    signal_id: int, 
    status: str,
    exit_price: Optional[float] = None,
    exit_date: Optional[str] = None
):
    """Update trading signal status and exit information."""
    try:
        signal = TradingSignal.objects.get(id=signal_id)
        signal.status = status
        
        if exit_price:
            signal.exit_price = Decimal(str(exit_price))
            signal.exit_date = exit_date
            
            # Calculate realized return
            if signal.position_type == 'LONG':
                signal.realized_return = ((Decimal(str(exit_price)) - signal.signal_price) / signal.signal_price) * 100
            else:  # SHORT
                signal.realized_return = ((signal.signal_price - Decimal(str(exit_price))) / signal.signal_price) * 100
                
            # Calculate holding period
            if signal.exit_date and signal.signal_date:
                exit_date_obj = datetime.strptime(exit_date, '%Y-%m-%d').date()
                signal.holding_period = (exit_date_obj - signal.signal_date).days
        
        signal.save()
        return {"success": True, "message": "Signal status updated"}
        
    except TradingSignal.DoesNotExist:
        raise HttpError(404, "Trading signal not found")

# ================================
# ANALYTICS AND AGGREGATION ENDPOINTS
# ================================

@router.get("/analytics/performance/{portfolio_name}", response=PerformanceMetrics)
def get_portfolio_performance_metrics(
    request, 
    portfolio_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get comprehensive performance metrics for a portfolio."""
    queryset = PortfolioSnapshot.objects.filter(portfolio_name=portfolio_name)
    
    if start_date:
        queryset = queryset.filter(snapshot_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(snapshot_date__lte=end_date)
    
    if not queryset.exists():
        raise HttpError(404, "No portfolio data found for the specified criteria")
    
    # Calculate performance metrics
    snapshots = list(queryset.order_by('snapshot_date'))
    
    if len(snapshots) < 2:
        raise HttpError(400, "Insufficient data for performance calculation")
    
    first_snapshot = snapshots[0]
    last_snapshot = snapshots[-1]
    
    # Calculate total return
    total_return = ((last_snapshot.total_value - first_snapshot.total_value) / first_snapshot.total_value) * 100
    
    # Calculate other metrics (simplified version - in production you'd use more sophisticated calculations)
    daily_returns = []
    for i in range(1, len(snapshots)):
        daily_return = ((snapshots[i].total_value - snapshots[i-1].total_value) / snapshots[i-1].total_value)
        daily_returns.append(daily_return)
    
    if daily_returns:
        avg_daily_return = sum(daily_returns) / len(daily_returns)
        annualized_return = (avg_daily_return * 252) * 100  # 252 trading days
        
        # Calculate volatility
        variance = sum([(r - avg_daily_return) ** 2 for r in daily_returns]) / len(daily_returns)
        volatility = (variance ** 0.5) * (252 ** 0.5) * 100
        
        # Calculate Sharpe ratio (assuming 2% risk-free rate)
        risk_free_rate = 2.0
        sharpe_ratio = (annualized_return - risk_free_rate) / volatility if volatility > 0 else 0
        
        # Calculate max drawdown
        peak = first_snapshot.total_value
        max_drawdown = 0
        for snapshot in snapshots:
            if snapshot.total_value > peak:
                peak = snapshot.total_value
            drawdown = ((peak - snapshot.total_value) / peak) * 100
            max_drawdown = max(max_drawdown, drawdown)
    else:
        annualized_return = total_return
        volatility = 0
        sharpe_ratio = 0
        max_drawdown = 0
    
    return PerformanceMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        volatility=volatility,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown
    )

@router.get("/analytics/assets/performance", response=List[AssetPerformance])
def get_asset_performance_analytics(
    request,
    asset_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50
):
    """Get performance analytics for individual assets based on trading signals."""
    queryset = TradingSignal.objects.filter(status='EXECUTED', realized_return__isnull=False)
    
    if asset_type:
        queryset = queryset.filter(asset_type=asset_type)
    
    if start_date:
        queryset = queryset.filter(signal_date__gte=start_date)
    
    if end_date:
        queryset = queryset.filter(signal_date__lte=end_date)
    
    # Aggregate by symbol
    asset_stats = {}
    
    for signal in queryset:
        symbol = signal.symbol
        if symbol not in asset_stats:
            asset_stats[symbol] = {
                'symbol': symbol,
                'asset_type': signal.asset_type,
                'total_signals': 0,
                'successful_signals': 0,
                'returns': [],
                'holding_periods': []
            }
        
        asset_stats[symbol]['total_signals'] += 1
        if signal.realized_return > 0:
            asset_stats[symbol]['successful_signals'] += 1
        
        asset_stats[symbol]['returns'].append(float(signal.realized_return))
        if signal.holding_period:
            asset_stats[symbol]['holding_periods'].append(signal.holding_period)
    
    # Calculate performance metrics
    performance_list = []
    for symbol, stats in asset_stats.items():
        if stats['total_signals'] > 0:
            win_rate = (stats['successful_signals'] / stats['total_signals']) * 100
            avg_return = sum(stats['returns']) / len(stats['returns'])
            total_return = sum(stats['returns'])
            best_return = max(stats['returns'])
            worst_return = min(stats['returns'])
            avg_holding_period = sum(stats['holding_periods']) / len(stats['holding_periods']) if stats['holding_periods'] else None
            
            performance_list.append(AssetPerformance(
                symbol=symbol,
                asset_type=stats['asset_type'],
                total_signals=stats['total_signals'],
                successful_signals=stats['successful_signals'],
                win_rate=win_rate,
                avg_return=avg_return,
                total_return=total_return,
                best_return=best_return,
                worst_return=worst_return,
                avg_holding_period=avg_holding_period
            ))
    
    # Sort by total return and limit
    performance_list.sort(key=lambda x: x.total_return, reverse=True)
    return performance_list[:limit]

@router.get("/analytics/strategies/comparison", response=List[StrategyComparison])
def get_strategy_comparison(request):
    """Compare performance across different backtest strategies."""
    # Aggregate backtest results by strategy
    strategy_stats = BacktestResult.objects.values('strategy_name').annotate(
        backtest_count=Count('id'),
        avg_return=Avg('total_return'),
        avg_sharpe_ratio=Avg('sharpe_ratio'),
        avg_max_drawdown=Avg('max_drawdown'),
        best_return=Max('total_return'),
        worst_return=Min('total_return')
    )
    
    comparisons = []
    for stats in strategy_stats:
        # Calculate win rate (returns > 0)
        strategy_backtests = BacktestResult.objects.filter(strategy_name=stats['strategy_name'])
        winning_backtests = strategy_backtests.filter(total_return__gt=0).count()
        win_rate = (winning_backtests / stats['backtest_count']) * 100 if stats['backtest_count'] > 0 else 0
        
        comparisons.append(StrategyComparison(
            strategy_name=stats['strategy_name'],
            backtest_count=stats['backtest_count'],
            avg_return=float(stats['avg_return'] or 0),
            avg_sharpe_ratio=float(stats['avg_sharpe_ratio'] or 0),
            avg_max_drawdown=float(stats['avg_max_drawdown'] or 0),
            best_return=float(stats['best_return'] or 0),
            worst_return=float(stats['worst_return'] or 0),
            win_rate=win_rate
        ))
    
    return sorted(comparisons, key=lambda x: x.avg_return, reverse=True)

@router.get("/analytics/market-screener", response=MarketScreenerAnalytics)
def get_market_screener_analytics(
    request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get comprehensive analytics for market screener performance."""
    queryset = MarketScreenerResult.objects.all()
    
    if start_date:
        queryset = queryset.filter(analysis_date__gte=start_date)
    
    if end_date:
        queryset = queryset.filter(analysis_date__lte=end_date)
    
    if not queryset.exists():
        raise HttpError(404, "No market screener data found for the specified criteria")
    
    # Calculate basic metrics
    total_screeners = queryset.count()
    avg_sentiment_score = queryset.aggregate(avg=Avg('market_sentiment_score'))['avg'] or 0
    
    # Most common sentiment
    sentiment_counts = queryset.values('market_sentiment').annotate(count=Count('id')).order_by('-count')
    most_common_sentiment = sentiment_counts[0]['market_sentiment'] if sentiment_counts else 'Unknown'
    
    # Get top performing assets (simplified - would need more complex logic in production)
    top_stocks = []
    top_cryptos = []
    
    # Sector performance (simplified)
    sector_performance = {}
    
    # Monthly performance (simplified)
    monthly_performance = {}
    
    return MarketScreenerAnalytics(
        total_screeners=total_screeners,
        avg_sentiment_score=float(avg_sentiment_score),
        most_common_sentiment=most_common_sentiment,
        top_performing_stocks=top_stocks,
        top_performing_cryptos=top_cryptos,
        sector_performance=sector_performance,
        monthly_performance=monthly_performance
    )

# ================================
# DATA EXPORT ENDPOINTS
# ================================

@router.post("/export", response=ExportResponse)
def export_data(request, export_request: ExportRequest):
    """Export data in various formats (CSV, JSON, Excel)."""
    # Generate export based on data type and format
    export_id = f"export_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
    
    # This is a simplified implementation - in production you'd:
    # 1. Queue the export job
    # 2. Generate the file asynchronously
    # 3. Store it in cloud storage
    # 4. Return a download URL
    
    # For now, return a mock response
    return ExportResponse(
        download_url=f"/api/backtesting/downloads/{export_id}.{export_request.format}",
        file_size=1024000,  # Mock size
        record_count=1000,  # Mock count
        export_id=export_id,
        created_at=timezone.now(),
        expires_at=timezone.now() + timedelta(hours=24)
    )

@router.get("/export/csv/historical-data")
def export_historical_data_csv(
    request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    symbols: Optional[str] = None
):
    """Export historical market data as CSV."""
    queryset = HistoricalMarketData.objects.all()
    
    if start_date:
        queryset = queryset.filter(analysis_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(analysis_date__lte=end_date)
    if symbols:
        symbol_list = symbols.split(',')
        queryset = queryset.filter(symbol__in=symbol_list)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="historical_market_data.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Date', 'Symbol', 'Asset Type', 'Open', 'Close', 'High', 'Low', 
        'Volume', 'Market Cap', 'Change 1D', 'Change 7D', 'Change 30D',
        'RSI 14', 'EMA 50', 'SMA 200', 'Screener Position', 'Confidence Score',
        'Rank', 'Sector', 'Industry'
    ])
    
    for data in queryset:
        writer.writerow([
            data.analysis_date,
            data.symbol,
            data.asset_type,
            data.open_price,
            data.close_price,
            data.high_price,
            data.low_price,
            data.volume,
            data.market_cap,
            data.change_1d,
            data.change_7d,
            data.change_30d,
            data.rsi_14,
            data.ema_50,
            data.sma_200,
            data.screener_position,
            data.confidence_score,
            data.rank_in_category,
            data.sector,
            data.industry
        ])
    
    return response

# ================================
# TIME SERIES AND AGGREGATION ENDPOINTS
# ================================

@router.get("/time-series/portfolio/{portfolio_name}")
def get_portfolio_time_series(
    request,
    portfolio_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    metric: str = 'total_value'
):
    """Get time series data for a specific portfolio metric."""
    queryset = PortfolioSnapshot.objects.filter(portfolio_name=portfolio_name)
    
    if start_date:
        queryset = queryset.filter(snapshot_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(snapshot_date__lte=end_date)
    
    # Valid metrics
    valid_metrics = [
        'total_value', 'daily_return', 'cumulative_return', 'max_drawdown',
        'sharpe_ratio', 'volatility', 'long_exposure', 'short_exposure'
    ]
    
    if metric not in valid_metrics:
        raise HttpError(400, f"Invalid metric. Valid options: {', '.join(valid_metrics)}")
    
    data = []
    for snapshot in queryset.order_by('snapshot_date'):
        value = getattr(snapshot, metric)
        data.append({
            'date': snapshot.snapshot_date,
            'value': float(value) if value is not None else None
        })
    
    return {
        'portfolio_name': portfolio_name,
        'metric': metric,
        'data': data
    }

@router.get("/summary/dashboard")
def get_dashboard_summary(request):
    """Get comprehensive dashboard summary for backtesting overview."""
    # Get recent data counts
    total_historical_records = HistoricalMarketData.objects.count()
    total_portfolios = PortfolioSnapshot.objects.values('portfolio_name').distinct().count()
    total_backtests = BacktestResult.objects.count()
    active_signals = TradingSignal.objects.filter(status='ACTIVE').count()
    
    # Get recent performance
    recent_screeners = MarketScreenerResult.objects.order_by('-timestamp')[:5]
    recent_backtests = BacktestResult.objects.order_by('-timestamp')[:5]
    
    # Calculate some basic metrics
    avg_sentiment = MarketScreenerResult.objects.aggregate(
        avg=Avg('market_sentiment_score')
    )['avg'] or 0
    
    best_backtest = BacktestResult.objects.order_by('-total_return').first()
    
    return {
        'summary': {
            'total_historical_records': total_historical_records,
            'total_portfolios': total_portfolios,
            'total_backtests': total_backtests,
            'active_signals': active_signals,
            'avg_market_sentiment': float(avg_sentiment)
        },
        'recent_screeners': [
            {
                'id': screener.id,
                'date': screener.analysis_date,
                'sentiment': screener.market_sentiment,
                'score': float(screener.market_sentiment_score)
            } for screener in recent_screeners
        ],
        'recent_backtests': [
            {
                'id': backtest.id,
                'strategy': backtest.strategy_name,
                'return': float(backtest.total_return),
                'sharpe': float(backtest.sharpe_ratio)
            } for backtest in recent_backtests
        ],
        'best_strategy': {
            'name': best_backtest.strategy_name if best_backtest else None,
            'return': float(best_backtest.total_return) if best_backtest else None,
            'sharpe': float(best_backtest.sharpe_ratio) if best_backtest else None
        } if best_backtest else None
    } 