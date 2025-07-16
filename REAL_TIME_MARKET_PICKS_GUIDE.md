# Real-Time Market Picks Access Guide

## 🎯 Overview

Your Strykr AI system generates daily market screener results that include:
- **Top 5 stocks to go LONG** with confidence scores
- **Top 5 stocks to go SHORT** with confidence scores  
- **Top cryptocurrencies LONG/SHORT** recommendations
- **Market sentiment analysis** with numerical scoring
- **AI-generated explanations** of market conditions

## 🔑 API Access

### Your API Keys
- **Main API**: `E9yGBPVF5aRukOVYT0Px4AwW`
- **Backtesting Portal**: `BT_9KmN3PqX8vY2ZwA5fG7H1`

Both keys have access to market screener data.

## 📡 Real-Time Market Picks Endpoints

### 1. Get All Market Screener Results
```bash
GET https://api.strykr.ai/api/alerts/market-screener
```

**Headers:**
```
X-API-Key: E9yGBPVF5aRukOVYT0Px4AwW
Content-Type: application/json
```

**Response Structure:**
```json
[
  {
    "id": 123,
    "timestamp": "2024-12-28T12:00:00Z",
    "analysis_date": "2024-12-28",
    "market_sentiment": "Bullish",
    "market_sentiment_score": 15.6,
    "top_stocks_long": [
      {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "price": 195.50,
        "change_percent": 2.5,
        "confidence_score": 85.2
      }
    ],
    "top_stocks_short": [
      {
        "ticker": "NFLX", 
        "company_name": "Netflix Inc.",
        "price": 485.20,
        "change_percent": -1.8,
        "confidence_score": 78.9
      }
    ],
    "top_cryptos_long": [
      {
        "symbol": "BTC",
        "name": "Bitcoin",
        "price": 95450.00,
        "change_percent": 3.2,
        "market_cap": 1890000000000
      }
    ],
    "top_cryptos_short": [
      {
        "symbol": "ADA",
        "name": "Cardano", 
        "price": 0.85,
        "change_percent": -2.1,
        "market_cap": 30000000000
      }
    ],
    "explanation": "Market sentiment is bullish driven by strong tech earnings and crypto momentum..."
  }
]
```

### 2. Get Specific Market Screener Result
```bash
GET https://api.strykr.ai/api/alerts/market-screener/{id}
```

## 💻 Code Examples

### Python Example
```python
import requests
import json

def get_latest_market_picks():
    headers = {
        "X-API-Key": "E9yGBPVF5aRukOVYT0Px4AwW",
        "Content-Type": "application/json"
    }
    
    response = requests.get(
        "https://api.strykr.ai/api/alerts/market-screener",
        headers=headers
    )
    
    if response.status_code == 200:
        results = response.json()
        if results:
            latest = results[0]  # Most recent result
            
            print(f"Market Sentiment: {latest['market_sentiment']}")
            print(f"Sentiment Score: {latest['market_sentiment_score']}")
            
            print("\n🟢 TOP LONG PICKS:")
            for stock in latest['top_stocks_long']:
                print(f"  {stock['ticker']}: {stock['confidence_score']:.1f}% confidence")
            
            print("\n🔴 TOP SHORT PICKS:")
            for stock in latest['top_stocks_short']:
                print(f"  {stock['ticker']}: {stock['confidence_score']:.1f}% confidence")
                
            return latest
    
    return None

# Usage
picks = get_latest_market_picks()
```

### curl Example
```bash
# Get latest market picks
curl -X GET "https://api.strykr.ai/api/alerts/market-screener" \
  -H "X-API-Key: E9yGBPVF5aRukOVYT0Px4AwW" \
  -H "Content-Type: application/json"
```

### JavaScript/Node.js Example
```javascript
const axios = require('axios');

async function getLatestMarketPicks() {
    const config = {
        method: 'get',
        url: 'https://api.strykr.ai/api/alerts/market-screener',
        headers: {
            'X-API-Key': 'E9yGBPVF5aRukOVYT0Px4AwW',
            'Content-Type': 'application/json'
        }
    };
    
    try {
        const response = await axios(config);
        const latest = response.data[0];
        
        console.log(`Market Sentiment: ${latest.market_sentiment}`);
        console.log('Long Picks:', latest.top_stocks_long);
        console.log('Short Picks:', latest.top_stocks_short);
        
        return latest;
    } catch (error) {
        console.error('Error fetching picks:', error);
    }
}
```

### R Example
```r
library(httr)
library(jsonlite)

get_market_picks <- function() {
    headers <- add_headers(
        `X-API-Key` = "E9yGBPVF5aRukOVYT0Px4AwW",
        `Content-Type` = "application/json"
    )
    
    response <- GET(
        "https://api.strykr.ai/api/alerts/market-screener",
        headers
    )
    
    if (status_code(response) == 200) {
        data <- content(response, "parsed")
        latest <- data[[1]]
        
        cat("Market Sentiment:", latest$market_sentiment, "\n")
        cat("Sentiment Score:", latest$market_sentiment_score, "\n")
        
        return(latest)
    }
}

# Usage
picks <- get_market_picks()
```

## 🔄 Integration with Backtesting System

### Real-Time Data Flow for Backtesting

1. **Fetch Current Picks**
```python
def fetch_current_picks():
    """Get latest market screener results for backtesting."""
    headers = {"X-API-Key": "BT_9KmN3PqX8vY2ZwA5fG7H1"}
    
    response = requests.get(
        "https://api.strykr.ai/api/alerts/market-screener",
        headers=headers
    )
    
    return response.json()[0] if response.status_code == 200 else None
```

2. **Convert to Trading Signals**
```python
def convert_picks_to_signals(picks):
    """Convert market picks to trading signals for backtesting."""
    signals = []
    
    # Long signals
    for stock in picks['top_stocks_long']:
        signals.append({
            'symbol': stock['ticker'],
            'action': 'BUY',
            'confidence': stock['confidence_score'] / 100,
            'price': stock['price'],
            'timestamp': picks['timestamp']
        })
    
    # Short signals  
    for stock in picks['top_stocks_short']:
        signals.append({
            'symbol': stock['ticker'],
            'action': 'SELL',
            'confidence': stock['confidence_score'] / 100,
            'price': stock['price'],
            'timestamp': picks['timestamp']
        })
    
    return signals
```

3. **Track Performance**
```python
def track_pick_performance(picks):
    """Track how market picks perform over time."""
    
    # Store in backtesting database
    headers = {"X-API-Key": "BT_9KmN3PqX8vY2ZwA5fG7H1"}
    
    for stock in picks['top_stocks_long'] + picks['top_stocks_short']:
        signal_data = {
            'symbol': stock['ticker'],
            'signal_type': 'market_screener_pick',
            'confidence_score': stock['confidence_score'],
            'entry_price': stock['price'],
            'sentiment': picks['market_sentiment'],
            'analysis_date': picks['analysis_date']
        }
        
        requests.post(
            "https://api.strykr.ai/api/backtesting/trading-signals",
            headers=headers,
            json=signal_data
        )
```

## 🕐 Data Generation & Scheduling

### Manual Generation
To generate new market picks manually:
```bash
python manage.py generate_market_screener
```

### Automated Scheduling 
Set up a cron job to generate picks daily:
```bash
# Add to crontab for daily 6 AM generation
0 6 * * * cd /path/to/strykr_api && python manage.py generate_market_screener
```

## 📊 Data Structure Details

### Market Sentiment Scoring
- **Score Range**: -100 (Very Bearish) to +100 (Very Bullish)
- **Sentiment Labels**: 
  - `score > 30`: "Bullish"
  - `score > 10`: "Mildly Bullish" 
  - `score > -10`: "Neutral"
  - `score > -30`: "Mildly Bearish"
  - `score <= -30`: "Bearish"

### Confidence Scores
- **Range**: 0-100%
- **Calculation**: Based on technical indicators:
  - Price momentum (70% weight)
  - Volume analysis (30% weight)
  - Relative strength vs market

### Pick Selection Criteria
**Long Picks (Top 5)**:
- Highest positive strength scores
- Strong upward price momentum  
- Above-average volume
- Positive technical indicators

**Short Picks (Top 5)**:
- Lowest (most negative) strength scores
- Downward price momentum
- Technical weakness signals
- Below-average performance

## 🔧 Troubleshooting

### Common Issues

1. **No Data Returned**
   - Check if market screener has been generated today
   - Run: `python manage.py generate_market_screener`

2. **Authentication Errors**
   - Verify API key is correct
   - Check key permissions in database

3. **Empty Picks Arrays**
   - Market data may be unavailable
   - Check FMP API key and CoinGecko access

### API Status Codes
- **200**: Success
- **403**: Invalid API key or permissions
- **404**: No market screener results found
- **500**: Server error

## 🚀 Quick Start Checklist

1. ✅ **API Key Ready**: `E9yGBPVF5aRukOVYT0Px4AwW`
2. ✅ **Endpoints Configured**: `/api/alerts/market-screener`
3. ✅ **Backtesting Access**: `BT_9KmN3PqX8vY2ZwA5fG7H1`
4. ⬜ **Generate Sample Data**: Run market screener command
5. ⬜ **Test API Access**: Use provided curl/Python examples
6. ⬜ **Set Up Polling**: Integrate with your backtesting system
7. ⬜ **Track Performance**: Store picks and measure outcomes

## 📈 Integration Benefits

- **Real-Time Signals**: Get fresh market picks daily
- **Confidence Scoring**: Filter picks by confidence level
- **Multi-Asset Coverage**: Stocks and cryptocurrencies  
- **Sentiment Analysis**: Understand market conditions
- **Historical Tracking**: Build performance database
- **Backtesting Ready**: Direct integration with your Trade_Backtesting repo

Your market picks are generated using real market data, technical analysis, and AI-powered sentiment analysis, giving you a robust foundation for algorithmic trading strategies. 