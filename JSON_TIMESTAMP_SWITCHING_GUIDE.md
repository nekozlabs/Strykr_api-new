# JSON Endpoint Automatic Timestamp Switching Guide

## Overview

The Strykr API now supports automatic timestamp switching for JSON endpoints. This feature allows the framework to automatically convert timestamps to real-time format based on your API configuration and endpoint context, providing seamless integration for different use cases.

## Key Features

- **Automatic Detection**: Framework automatically detects timestamp fields in JSON responses
- **Context-Aware Switching**: Different behavior for real-time vs historical data endpoints  
- **API Key Configuration**: Timestamp behavior based on your API key type and permissions
- **Multiple Modes**: Support for real-time, historical preservation, and automatic modes

## How It Works

### 1. Automatic Timestamp Detection

The system automatically identifies timestamp fields by looking for common patterns:
- Fields containing: `date`, `timestamp`, `time`, `created`, `updated`
- ISO format timestamps: `2024-01-01T12:00:00Z`
- Django datetime objects

### 2. Context-Aware Processing

The framework decides how to handle timestamps based on:

**Real-Time Endpoints** (automatically use current timestamps):
- `/api/alerts/market-screener`
- `/api/alerts/*` (market alerts)
- Any endpoint with "real-time" in the path

**Historical Endpoints** (preserve original timestamps):
- `/api/backtesting/*`
- Any endpoint with "backtesting" in the path
- Historical data endpoints

**Auto Mode** (intelligent detection):
- Analyzes response content for historical markers
- Uses real timestamps for live data, preserves historical timestamps

## API Configuration Integration

Your API key configuration in `api_configuration.json` determines timestamp behavior:

```json
{
  "applications": {
    "backtesting_portal": {
      "api_key": "BT_9KmN3PqX8vY2ZwA5fG7H1",
      "permissions": {
        "endpoints": ["/api/backtesting/*"]
      },
      "data_access": {
        "real_time_market_picks": true
      }
    },
    "mobile_app": {
      "api_key": "Client_MB_7JkL9MnP2QrS4TvW",
      "key_type": "client_side",
      "data_access": {
        "real_time_market_picks": true
      }
    }
  }
}
```

## Implementation Examples

### 1. Real-Time Market Data Endpoint

```python
from .response_helpers import json_endpoint_with_real_timestamps

@api.get("/market-screener-realtime")
@json_endpoint_with_real_timestamps
def market_screener_realtime(request):
    """All timestamps will be converted to real-time format"""
    return {
        "market_picks": [
            {
                "symbol": "AAPL",
                "analysis_date": "2024-01-01T12:00:00Z",  # Becomes current timestamp
                "recommendation": "BUY"
            }
        ],
        "generated_at": "2024-01-01T12:00:00Z"  # Becomes current timestamp
    }
```

### 2. Historical Data Endpoint

```python
from .response_helpers import create_enhanced_json_response

@api.get("/backtesting-data")
def backtesting_historical_data(request):
    """Historical timestamps preserved for backtesting accuracy"""
    historical_data = {
        "backtest_results": [
            {
                "entry_date": "2023-06-15T09:30:00Z",  # Preserved as-is
                "exit_date": "2023-06-20T16:00:00Z",   # Preserved as-is
                "symbol": "BTC"
            }
        ]
    }
    
    return create_enhanced_json_response(
        data=historical_data,
        request=request,
        timestamp_mode='preserve'  # Keep original timestamps
    )
```

### 3. Automatic Mode (Intelligent Detection)

```python
from .response_helpers import auto_timestamp_json_response

@api.get("/smart-endpoint")
@auto_timestamp_json_response()
def smart_endpoint(request):
    """Framework automatically detects if data is historical or real-time"""
    return {
        "live_price": 150.00,
        "last_updated": "2024-01-01T12:00:00Z",  # Real-time conversion
        "historical_data": [
            {
                "date": "2023-06-15T09:30:00Z",  # Preserved (historical context)
                "price": 145.00
            }
        ]
    }
```

## Response Format

Responses include metadata about timestamp handling:

```json
{
  "success": true,
  "data": {
    "market_picks": [...],
    "generated_at": "2024-12-28T15:30:45.123Z"
  },
  "metadata": {
    "endpoint": "/api/market-screener-realtime",
    "timestamp_mode": "real_time_converted",
    "timestamp_format": "real_time",
    "response_generated_at": "2024-12-28T15:30:45.123Z",
    "timezone": "UTC",
    "application": "Main Strykr API",
    "api_version": "1.0"
  }
}
```

## Available Decorators

### `@json_endpoint_with_real_timestamps`
Forces all timestamps to be converted to real-time format.

**Use Cases:**
- Live market data endpoints
- Real-time alerts and notifications
- Current market screener results

### `@preserve_historical_timestamps`  
Preserves all original timestamps exactly as provided.

**Use Cases:**
- Backtesting data endpoints
- Historical analysis
- Archived data retrieval

### `@auto_timestamp_json_response()`
Intelligent automatic detection with configurable options.

**Parameters:**
- `enable_auto_switching`: Enable/disable automatic switching (default: True)
- `force_real_timestamps`: Force real timestamps regardless of context (default: False)

## Utility Functions

### `create_enhanced_json_response()`
Manual response creation with timestamp control.

```python
return create_enhanced_json_response(
    data=your_data,
    request=request,
    timestamp_mode='auto'  # 'auto', 'real', or 'preserve'
)
```

### `format_response_timestamps()`
Format timestamps in existing data structures.

```python
formatted_data = format_response_timestamps(
    data=your_data,
    mode='real'  # 'auto', 'real', or 'preserve'  
)
```

## Middleware Integration

For automatic processing of all JSON responses, add to Django settings:

```python
MIDDLEWARE = [
    # ... other middleware
    'core.response_helpers.JSONTimestampMiddleware',
    # ... remaining middleware
]
```

## Testing Your Implementation

### Example API Calls

**Real-Time Endpoint:**
```bash
curl -H "X-API-Key: E9yGBPVF5aRukOVYT0Px4AwW" \
     https://api.strykr.ai/api/market-screener-realtime
```

**Historical Endpoint:**
```bash  
curl -H "X-API-Key: BT_9KmN3PqX8vY2ZwA5fG7H1" \
     https://api.strykr.ai/api/backtesting-historical
```

### Verifying Timestamp Conversion

Check the response metadata:
- `timestamp_mode`: Shows how timestamps were processed
- `timestamp_format`: Indicates if timestamps are real-time or preserved
- Response headers include `X-Timestamp-Mode` and `X-Response-Enhanced`

## Best Practices

1. **Use Appropriate Decorators**: Choose the right decorator for your endpoint type
2. **Check API Configuration**: Ensure your API key configuration supports the intended behavior
3. **Test Both Modes**: Verify both real-time and historical timestamp handling
4. **Monitor Metadata**: Use response metadata to confirm expected behavior
5. **Handle Edge Cases**: Consider timezone differences and timestamp formats

## Troubleshooting

### Common Issues

**Timestamps Not Converting:**
- Check API key permissions in `api_configuration.json`
- Verify endpoint path matches expected patterns
- Confirm decorator is properly applied

**Unexpected Timestamp Preservation:**
- Review endpoint path for historical markers
- Check `data_access.real_time_market_picks` setting
- Verify `key_type` in API configuration

**Missing Metadata:**
- Ensure proper decorator usage
- Check middleware configuration
- Verify JSON response format

### Debug Information

Enable logging to see timestamp processing details:

```python
import logging
logging.getLogger('core.response_helpers').setLevel(logging.DEBUG)
```

This will provide detailed information about:
- Timestamp field detection
- Conversion decisions
- API configuration lookups
- Processing errors

## Advanced Configuration

### Custom Timestamp Fields

Extend timestamp detection for custom field names:

```python
# In JSONResponseFormatter.format_timestamps_recursive()
timestamp_fields = ['date', 'timestamp', 'time', 'created', 'updated', 
                   'analysis_date', 'generated_at', 'last_seen']
```

### Custom Processing Logic

Override timestamp switching logic for specific endpoints:

```python
def custom_timestamp_handler(endpoint_path, api_config):
    if 'custom-endpoint' in endpoint_path:
        return 'preserve'  # Custom logic
    return 'auto'  # Default behavior
```

This comprehensive guide should help you implement and use the automatic timestamp switching functionality effectively in your Strykr API endpoints. 