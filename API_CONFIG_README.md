# Strykr AI - API Configuration System

This system provides organized API key management and data access configuration for different applications in the Strykr AI ecosystem.

## Files

- **`api_configuration.json`** - Main configuration file with all API keys and settings
- **`api_config_manager.py`** - Full-featured configuration manager (requires Django)
- **`simple_config_viewer.py`** - Lightweight viewer (no Django required)

## Current API Keys Configuration

### Your Existing API Key
- **Main API**: `E9yGBPVF5aRukOVYT0Px4AwW`
  - Full access to all endpoints
  - 500 requests/day, 10,000/month

### New Backtesting Portal API Key
- **Backtesting Portal**: `BT_9KmN3PqX8vY2ZwA5fG7H1`
  - Specialized for backtesting data access
  - 2,000 requests/day, 50,000/month
  - Access to historical data, trading signals, portfolio snapshots

### Additional API Keys (Ready for Future Use)
- **Mobile App**: `Client_MB_7JkL9MnP2QrS4TvW` (client-side)
- **Web Dashboard**: `Client_WD_3FgH6JkL8MnQ1RtY` (client-side)
- **Research Tools**: `RT_5HjK8LnP1QsV4WxZ7` (high-volume)

## Quick Start

### View Configuration
```bash
python3 simple_config_viewer.py --summary
```

### Get Backtesting Config
```bash
python3 simple_config_viewer.py --backtesting-config
```

### Generate Python Client
```bash
python3 simple_config_viewer.py --generate-client
```

### List All Applications
```bash
python3 simple_config_viewer.py --list-apps
```

## Using the Backtesting API Key

### Python Example
```python
import requests

headers = {
    "X-API-Key": "BT_9KmN3PqX8vY2ZwA5fG7H1",
    "Content-Type": "application/json"
}

# Get historical data
response = requests.get(
    "https://api.strykr.ai/api/backtesting/historical-data",
    headers=headers,
    params={
        "symbols": "AAPL,GOOGL,MSFT",
        "start_date": "2024-01-01",
        "end_date": "2024-12-28"
    }
)

print(response.json())
```

### R Example
```r
library(httr)
library(jsonlite)

headers <- add_headers(
  `X-API-Key` = "BT_9KmN3PqX8vY2ZwA5fG7H1",
  `Content-Type` = "application/json"
)

response <- GET(
  "https://api.strykr.ai/api/backtesting/trading-signals",
  headers,
  query = list(confidence_threshold = 0.7)
)

data <- content(response, "parsed")
```

## Available Endpoints for Backtesting

| Endpoint | Purpose |
|----------|---------|
| `/api/backtesting/historical-data` | Get OHLC data, technical indicators |
| `/api/backtesting/trading-signals` | Get market screener signals |
| `/api/backtesting/portfolio-snapshots` | Get portfolio performance data |
| `/api/backtesting/backtest-results` | Store/retrieve backtest results |
| `/api/backtesting/analytics` | Get performance analytics |
| `/api/backtesting/export` | Export data (CSV, JSON, Parquet) |

## Data Sources

The backtesting portal connects to these data tables:
- **MarketScreenerResult** - Daily market screener recommendations
- **HistoricalMarketData** - OHLC prices, technical indicators, metadata
- **PortfolioSnapshot** - Portfolio performance tracking
- **TradingSignal** - Generated trading signals with confidence scores
- **BacktestResult** - Comprehensive backtest results

## Integration with Trade_Backtesting Repository

This configuration is designed to work seamlessly with your separate `Trade_Backtesting` repository:

1. Use the `BT_9KmN3PqX8vY2ZwA5fG7H1` API key
2. Set up polling to sync data incrementally
3. Export data in your preferred format (CSV, JSON, Parquet)
4. Track portfolio performance over time

## Creating Database Entries

To create the actual API keys in your database:

```bash
python3 api_config_manager.py --create-db-keys
```

This will:
- Create/find the "Strykr AI Analytics" organization
- Create API key entries in the database
- Set proper permissions and rate limits

## Security Notes

- Server-side keys (no "Client" prefix) for backend applications
- Client-side keys (with "Client" prefix) for frontend applications
- Domain restrictions for client-side keys
- Rate limiting configured per application type
- API keys can be rotated quarterly

## Configuration Management

The JSON configuration supports:
- Version tracking
- Environment specifications (production/staging)
- Rate limiting per application
- Domain restrictions
- Data access permissions
- Integration patterns
- Monitoring and security settings

## Next Steps

1. **Test the backtesting API key** with a simple request
2. **Set up data population** using the management command:
   ```bash
   python manage.py populate_historical_data
   ```
3. **Configure your backtesting repository** to use the new API
4. **Set up automated data sync** using the polling strategy
5. **Monitor usage** through the configured rate limits

This organized configuration system provides a foundation for scaling your data access across multiple applications while maintaining security and performance. 