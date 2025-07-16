# STRYKR AI API

![STRYKR AI](https://via.placeholder.com/800x200?text=STRYKR+AI+API)

The STRYKR AI API provides sophisticated financial market analysis, technical indicators, and economic insights powered by advanced AI.

## Features

- **AI-Powered Financial Analysis**: Get detailed answers to any market-related questions
- **Technical Indicators**: Access RSI, EMA, SMA, and DEMA indicators for any asset
- **Economic Calendar**: Track upcoming economic events and their potential market impact
- **Market Alerts**: Receive timely notifications with risk assessments and detailed analysis
- **Bellwether Asset Tracking**: Monitor key market indicators for early trend detection

## Getting Started

### Authentication

STRYKR AI uses API keys for authentication. Two types of keys are available:

- **Server-side Key**: For secure server-to-server communication
- **Client-side Key**: For browser applications with domain restrictions

```bash
# Example request to create an API key
curl -X POST https://api.strykr.ai/api/dashboard/create-api-key \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": 123,
    "user_id": "user_123",
    "name": "My API Key",
    "allowed_domains": ["example.com"]
  }'
```

### Quick Start Examples

#### Python

```python
import requests

API_KEY = "your_api_key"

# Get market analysis
response = requests.post(
    "https://api.strykr.ai/api/precision-ai",
    headers={"X-API-Key": API_KEY},
    json={"query": "What is the RSI for Bitcoin?"}
)

print(response.json())
```

#### JavaScript

```javascript
const API_KEY = "your_client_side_key";

fetch("https://api.strykr.ai/api/ai-response", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY
  },
  body: JSON.stringify({
    query: "What is the outlook for small cap stocks?"
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

## Core Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/ai-response` | General market analysis with full context |
| `/api/precision-ai` | Focused analysis for specific assets |
| `/api/bellwether-x` | Analysis focused on bellwether assets |
| `/api/macro-pulse` | Macroeconomic analysis and calendar events |
| `/api/calendar` | Economic events calendar data |

## Alerts Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/alerts/market-alerts` | List all market risk alerts |
| `/api/alerts/calendar-alerts` | List calendar-based volatility alerts |
| `/api/alerts/market-screener` | Get market screener results with asset recommendations |

## Response Structure

Our API provides structured responses with the following sections:

- **MARKET CONTEXT**: Overview of current market conditions
- **SPECIFIC ANALYSIS**: Detailed insights tailored to your query
- **RISK MANAGEMENT**: Position sizing and risk considerations
- **ACTION STEPS**: Clear, implementable takeaways

Example response:

```json
{
  "response": {
    "market_context": "Markets are currently experiencing volatility due to upcoming Fed announcements...",
    "specific_analysis": "Bitcoin's RSI is currently at 62, indicating slightly overbought conditions...",
    "risk_management": "Consider limiting position sizes to 1-2% of portfolio given current volatility...",
    "action_steps": [
      "Monitor BTC price action around the $60,000 resistance level",
      "Set stop losses at $55,800 to manage downside risk"
    ]
  },
  "technical_indicators": {
    "RSI": 62,
    "EMA": 58134,
    "SMA": 52870,
    "DEMA": 59102
  }
}
```

## Technical Indicators

STRYKR AI provides these technical indicators with specific configurations:

| Indicator | Timeframe | Period |
|-----------|-----------|--------|
| RSI | 2-hour | 28 |
| EMA | 4-hour | 50 |
| DEMA | 4-hour | 20 |
| SMA | 4-hour | 200 |

## Best Practices

1. **Be Specific**: Include specific asset names in your queries
2. **Mention Timeframes**: Specify relevant timeframes when applicable
3. **Use Streaming**: For longer analyses, use the streaming option (add `"stream": true` to your request)
4. **Error Handling**: Implement proper error handling for all status codes
5. **Security**: Store API keys securely and implement proper CORS settings

## Rate Limits

Rate limits are determined by your API key configuration:
- Monthly request limits
- Daily request limits
- Premium users may have unlimited access

## API Key Management

```
POST /api/dashboard/create-api-key   # Create a new API key
POST /api/dashboard/revoke-api-key   # Disable an existing key
POST /api/dashboard/update-api-key   # Modify key settings
POST /api/dashboard/list-api-keys    # List all keys for a user
POST /api/dashboard/get-api-key      # Get details for a specific key
```

## Error Handling

The API uses standard HTTP status codes:
- 400: Bad Request (invalid parameters)
- 401: Unauthorized (invalid API key)
- 403: Forbidden (revoked key or domain not allowed)
- 429: Too Many Requests (rate limit exceeded)
- 500: Internal Server Error

## Support

For questions or support with the STRYKR AI API:
- Email: support@strykr.ai
- Documentation: https://docs.strykr.ai
- Status: https://status.strykr.ai

## License

STRYKR AI API © 2023-2024. All rights reserved. 