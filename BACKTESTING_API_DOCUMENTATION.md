# Strykr AI - Comprehensive Backtesting Database API Documentation

## Overview

The Strykr AI Backtesting Database API provides comprehensive endpoints for tracking market screener data, historical asset performance, portfolio management, and backtesting integration. This API is designed to support quantitative analysis, algorithmic trading systems, and backtesting frameworks.

## Base URL

```
https://api.strykr.ai/api/backtesting/
```

## Authentication

All API endpoints require authentication using API keys. Include your API key in the request headers:

```http
X-API-Key: your_api_key_here
```

## Data Models

### HistoricalMarketData

Stores detailed historical market data for individual assets with comprehensive metrics for backtesting analysis.

**Fields:**
- `id`: Unique identifier
- `timestamp`: Record creation timestamp
- `analysis_date`: Date of the market analysis
- `symbol`: Asset symbol (e.g., "AAPL", "BTC")
- `asset_type`: Type of asset (STOCK, CRYPTO, ETF, FOREX, COMMODITY)
- `open_price`, `close_price`, `high_price`, `low_price`: OHLC data
- `volume`: Trading volume
- `market_cap`: Market capitalization
- `change_1d`, `change_7d`, `change_30d`: Performance changes
- `rsi_14`, `ema_50`, `sma_200`: Technical indicators
- `screener_position`: Position recommendation (LONG, SHORT, NEUTRAL)
- `confidence_score`: Confidence level (0-100)
- `rank_in_category`: Ranking within its category
- `sector`, `industry`: Classification data
- `data_source`: Source of the data

### PortfolioSnapshot

Tracks portfolio performance snapshots for backtesting and analysis.

**Fields:**
- `id`: Unique identifier
- `timestamp`: Snapshot creation time
- `snapshot_date`: Date of the portfolio snapshot
- `portfolio_name`: Name of the portfolio strategy
- `strategy_type`: Strategy type (LONG_ONLY, SHORT_ONLY, LONG_SHORT, MARKET_NEUTRAL)
- `total_value`: Total portfolio value
- `long_exposure`, `short_exposure`: Market exposures
- `cash_balance`: Available cash
- Performance metrics: `daily_return`, `cumulative_return`, `max_drawdown`, `sharpe_ratio`, `volatility`, `var_95`, `beta`
- `market_sentiment_score`: Market sentiment at snapshot time
- `benchmark_return`: Benchmark comparison
- `source_screener`: Reference to originating market screener

### BacktestResult

Comprehensive backtest results for strategy evaluation.

**Fields:**
- Strategy configuration: `strategy_name`, `start_date`, `end_date`, `initial_capital`
- Execution parameters: `rebalance_frequency`, `max_positions`, `position_sizing`
- Performance metrics: `final_value`, `total_return`, `annualized_return`, `volatility`, `sharpe_ratio`, `max_drawdown`
- Risk metrics: `calmar_ratio`, `var_95`, `beta`, `alpha`
- Trade statistics: `total_trades`, `winning_trades`, `losing_trades`, `win_rate`, `avg_win`, `avg_loss`, `profit_factor`
- Benchmark comparison: `benchmark_return`, `excess_return`, `information_ratio`
- Metadata: `configuration`, `execution_time`, `data_quality_score`

### TradingSignal

Individual trading signals with performance tracking.

**Fields:**
- Signal data: `symbol`, `asset_type`, `signal_type` (BUY, SELL, HOLD), `signal_date`
- Signal strength: `strength`, `confidence_score`
- Price data: `signal_price`, `target_price`, `stop_loss_price`
- Signal context: `timeframe`, `reasoning`, `technical_factors`, `fundamental_factors`
- Performance tracking: `status`, `exit_price`, `exit_date`, `realized_return`, `holding_period`

## API Endpoints

### Historical Market Data

#### GET /historical-data
Retrieve historical market data with comprehensive filtering options.

**Query Parameters:**
```json
{
    "symbols": ["AAPL", "MSFT", "BTC"],
    "asset_types": ["STOCK", "CRYPTO"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "screener_positions": ["LONG", "SHORT"],
    "min_confidence_score": 70.0,
    "sectors": ["Technology", "Healthcare"],
    "limit": 100,
    "offset": 0
}
```

**Response:**
```json
{
    "data": [
        {
            "id": 1,
            "timestamp": "2024-01-15T10:30:00Z",
            "analysis_date": "2024-01-15",
            "symbol": "AAPL",
            "asset_type": "STOCK",
            "close_price": 185.64,
            "volume": 52043100,
            "market_cap": 2847654000000,
            "change_1d": 2.34,
            "rsi_14": 58.32,
            "ema_50": 182.45,
            "screener_position": "LONG",
            "confidence_score": 85.5,
            "sector": "Technology",
            "industry": "Consumer Electronics"
        }
    ],
    "pagination": {
        "limit": 100,
        "has_more": true,
        "next_cursor": 100,
        "prev_cursor": null
    }
}
```

#### POST /historical-data
Create new historical market data entry.

**Request Body:**
```json
{
    "analysis_date": "2024-01-15",
    "symbol": "AAPL",
    "asset_type": "STOCK",
    "close_price": 185.64,
    "volume": 52043100,
    "change_1d": 2.34,
    "screener_position": "LONG",
    "confidence_score": 85.5,
    "sector": "Technology"
}
```

#### GET /historical-data/symbol/{symbol}
Get historical data for a specific symbol with optional date filtering.

**Parameters:**
- `symbol`: Asset symbol
- `start_date`: Optional start date
- `end_date`: Optional end date
- `limit`: Maximum number of records (default: 100)

### Portfolio Management

#### GET /portfolios
List portfolio snapshots with filtering and pagination.

**Query Parameters:**
```json
{
    "portfolio_names": ["momentum_strategy", "mean_reversion"],
    "strategy_types": ["LONG_SHORT"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "min_total_value": 50000.0,
    "max_total_value": 500000.0,
    "limit": 50,
    "offset": 0
}
```

#### POST /portfolios
Create new portfolio snapshot.

**Request Body:**
```json
{
    "snapshot_date": "2024-01-15",
    "portfolio_name": "momentum_strategy",
    "strategy_type": "LONG_SHORT",
    "total_value": 125000.50,
    "long_exposure": 80000.00,
    "short_exposure": 30000.00,
    "cash_balance": 15000.50,
    "daily_return": 1.25,
    "cumulative_return": 25.5,
    "sharpe_ratio": 1.45,
    "market_sentiment_score": 15.2
}
```

#### GET /portfolios/performance/{portfolio_name}
Get performance history for a specific portfolio.

**Response:**
```json
[
    {
        "id": 1,
        "snapshot_date": "2024-01-15",
        "total_value": 125000.50,
        "daily_return": 1.25,
        "cumulative_return": 25.5,
        "positions": [
            {
                "symbol": "AAPL",
                "position_type": "LONG",
                "weight": 0.08,
                "unrealized_pnl_percent": 3.45
            }
        ]
    }
]
```

### Backtest Results

#### GET /backtests
List backtest results with filtering.

**Query Parameters:**
```json
{
    "strategy_names": ["momentum", "mean_reversion"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "min_return": 10.0,
    "min_sharpe_ratio": 1.0,
    "rebalance_frequencies": ["DAILY", "WEEKLY"],
    "limit": 50,
    "offset": 0
}
```

#### POST /backtests
Create new backtest result.

**Request Body:**
```json
{
    "strategy_name": "momentum_v2",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "initial_capital": 100000.0,
    "rebalance_frequency": "WEEKLY",
    "final_value": 125000.0,
    "total_return": 25.0,
    "annualized_return": 23.5,
    "volatility": 15.2,
    "sharpe_ratio": 1.55,
    "max_drawdown": -8.3,
    "total_trades": 156,
    "winning_trades": 89,
    "win_rate": 57.05,
    "configuration": {
        "lookback_period": 20,
        "momentum_threshold": 0.05,
        "max_positions": 10
    }
}
```

### Trading Signals

#### GET /signals
List trading signals with comprehensive filtering.

**Query Parameters:**
```json
{
    "symbols": ["AAPL", "MSFT"],
    "asset_types": ["STOCK"],
    "signal_types": ["BUY", "SELL"],
    "statuses": ["ACTIVE", "EXECUTED"],
    "min_confidence_score": 70.0,
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "limit": 100,
    "offset": 0
}
```

#### POST /signals
Create new trading signal.

**Request Body:**
```json
{
    "signal_date": "2024-01-15",
    "symbol": "AAPL",
    "asset_type": "STOCK",
    "signal_type": "BUY",
    "confidence_score": 85.5,
    "signal_price": 185.64,
    "target_price": 195.00,
    "stop_loss_price": 178.00,
    "reasoning": "Strong momentum with breakout above resistance",
    "technical_factors": ["RSI oversold recovery", "EMA crossover"],
    "fundamental_factors": ["Strong earnings guidance"]
}
```

#### PUT /signals/{signal_id}/update-status
Update signal status and exit information.

**Request Body:**
```json
{
    "status": "EXECUTED",
    "exit_price": 192.45,
    "exit_date": "2024-01-22"
}
```

### Analytics and Aggregation

#### GET /analytics/performance/{portfolio_name}
Get comprehensive performance metrics for a portfolio.

**Response:**
```json
{
    "total_return": 25.5,
    "annualized_return": 23.2,
    "volatility": 15.8,
    "sharpe_ratio": 1.47,
    "max_drawdown": -8.2,
    "win_rate": 68.5,
    "profit_factor": 1.85
}
```

#### GET /analytics/assets/performance
Get performance analytics for individual assets.

**Query Parameters:**
- `asset_type`: Filter by asset type
- `start_date`, `end_date`: Date range
- `limit`: Maximum results

**Response:**
```json
[
    {
        "symbol": "AAPL",
        "asset_type": "STOCK",
        "total_signals": 45,
        "successful_signals": 32,
        "win_rate": 71.1,
        "avg_return": 3.45,
        "total_return": 155.25,
        "best_return": 12.8,
        "worst_return": -5.2,
        "avg_holding_period": 7.5
    }
]
```

#### GET /analytics/strategies/comparison
Compare performance across different backtest strategies.

**Response:**
```json
[
    {
        "strategy_name": "momentum_v2",
        "backtest_count": 12,
        "avg_return": 18.5,
        "avg_sharpe_ratio": 1.32,
        "avg_max_drawdown": -9.1,
        "best_return": 34.2,
        "worst_return": -2.1,
        "win_rate": 75.0
    }
]
```

### Data Export

#### POST /export
Export data in various formats (CSV, JSON, Excel).

**Request Body:**
```json
{
    "data_type": "historical_data",
    "format": "csv",
    "query_params": {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "symbols": ["AAPL", "MSFT"]
    },
    "include_metadata": true
}
```

**Response:**
```json
{
    "download_url": "/api/backtesting/downloads/export_20241215_143022.csv",
    "file_size": 1024000,
    "record_count": 5000,
    "export_id": "export_20241215_143022",
    "created_at": "2024-12-15T14:30:22Z",
    "expires_at": "2024-12-16T14:30:22Z"
}
```

#### GET /export/csv/historical-data
Direct CSV export of historical market data.

**Query Parameters:**
- `start_date`, `end_date`: Date range
- `symbols`: Comma-separated list of symbols

### Time Series Data

#### GET /time-series/portfolio/{portfolio_name}
Get time series data for a specific portfolio metric.

**Parameters:**
- `portfolio_name`: Name of the portfolio
- `start_date`, `end_date`: Optional date range
- `metric`: Metric to retrieve (total_value, daily_return, cumulative_return, etc.)

**Response:**
```json
{
    "portfolio_name": "momentum_strategy",
    "metric": "total_value",
    "data": [
        {
            "date": "2024-01-15",
            "value": 125000.50
        },
        {
            "date": "2024-01-16",
            "value": 126500.75
        }
    ]
}
```

### Dashboard Summary

#### GET /summary/dashboard
Get comprehensive dashboard summary for backtesting overview.

**Response:**
```json
{
    "summary": {
        "total_historical_records": 125000,
        "total_portfolios": 15,
        "total_backtests": 48,
        "active_signals": 23,
        "avg_market_sentiment": 12.5
    },
    "recent_screeners": [
        {
            "id": 123,
            "date": "2024-01-15",
            "sentiment": "Bullish",
            "score": 15.2
        }
    ],
    "recent_backtests": [
        {
            "id": 456,
            "strategy": "momentum_v2",
            "return": 25.5,
            "sharpe": 1.45
        }
    ],
    "best_strategy": {
        "name": "momentum_v2",
        "return": 34.2,
        "sharpe": 1.87
    }
}
```

## Integration Examples

### Python Integration

```python
import requests
import pandas as pd

class StrykrBacktestAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.strykr.ai/api/backtesting"
        self.headers = {"X-API-Key": api_key}
    
    def get_historical_data(self, symbols, start_date, end_date):
        """Fetch historical data for backtesting."""
        params = {
            "symbols": symbols,
            "start_date": start_date,
            "end_date": end_date,
            "limit": 1000
        }
        response = requests.get(
            f"{self.base_url}/historical-data",
            headers=self.headers,
            params=params
        )
        return pd.DataFrame(response.json()["data"])
    
    def create_backtest_result(self, strategy_result):
        """Submit backtest results."""
        response = requests.post(
            f"{self.base_url}/backtests",
            headers=self.headers,
            json=strategy_result
        )
        return response.json()
    
    def get_portfolio_performance(self, portfolio_name):
        """Get portfolio performance time series."""
        response = requests.get(
            f"{self.base_url}/portfolios/performance/{portfolio_name}",
            headers=self.headers
        )
        return pd.DataFrame(response.json())

# Usage example
api = StrykrBacktestAPI("your_api_key")

# Get historical data for backtesting
data = api.get_historical_data(
    symbols=["AAPL", "MSFT", "TSLA"],
    start_date="2024-01-01",
    end_date="2024-12-31"
)

# Submit backtest results
backtest_result = {
    "strategy_name": "my_momentum_strategy",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "initial_capital": 100000.0,
    "final_value": 125000.0,
    "total_return": 25.0,
    "annualized_return": 23.5,
    "sharpe_ratio": 1.45,
    "max_drawdown": -8.2
}
result = api.create_backtest_result(backtest_result)
```

### R Integration

```r
library(httr)
library(jsonlite)

# Strykr Backtest API client
get_historical_data <- function(api_key, symbols, start_date, end_date) {
    response <- GET(
        "https://api.strykr.ai/api/backtesting/historical-data",
        add_headers(`X-API-Key` = api_key),
        query = list(
            symbols = paste(symbols, collapse = ","),
            start_date = start_date,
            end_date = end_date,
            limit = 1000
        )
    )
    
    data <- fromJSON(content(response, "text"))
    return(data$data)
}

# Usage
api_key <- "your_api_key"
data <- get_historical_data(
    api_key,
    c("AAPL", "MSFT", "TSLA"),
    "2024-01-01",
    "2024-12-31"
)
```

## Data Population

To populate historical data from existing market screener results, use the management command:

```bash
# Populate all historical data
python manage.py populate_historical_data

# Populate with date range
python manage.py populate_historical_data --start-date 2024-01-01 --end-date 2024-12-31

# Include trading signals and portfolio snapshots
python manage.py populate_historical_data --create-signals --create-portfolio

# Dry run to see what would be created
python manage.py populate_historical_data --dry-run
```

## Rate Limits

- 1000 requests per hour for free tier
- 10000 requests per hour for premium tier
- Bulk export operations count as 10 requests

## Error Handling

The API returns standard HTTP status codes:

- `200`: Success
- `400`: Bad Request (validation errors)
- `401`: Unauthorized (invalid API key)
- `404`: Not Found
- `429`: Rate Limit Exceeded
- `500`: Internal Server Error

Error responses include detailed error messages:

```json
{
    "error": "Invalid date format",
    "details": "Date must be in YYYY-MM-DD format",
    "code": "VALIDATION_ERROR"
}
```

## Support

For API support and questions:
- Documentation: https://docs.strykr.ai/backtesting-api
- Support: support@strykr.ai
- GitHub Issues: https://github.com/strykr-ai/api-issues 