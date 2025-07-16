import json
import logging
import re
from django.conf import settings
from django.template import Template, Context
from openai import OpenAI

# Import is_valid_ticker from ticker_services
from .ticker_services import is_valid_ticker
from .bellwether_assets import BELLWETHER_ASSETS

client = OpenAI(timeout=30.0)


# Get the bellwether assets


bellwether_template = """
# User's query

The following is the query sent by the user:

{{ query }}

# Instructions

Analyze the following list of 100 assets to create a Bellwether Index to gauge market sentiments and trends to help answer the user's question.

```json
{{ bellwether_assets_simplified|safe }}
```

From the above list of 100 assets, pick the ones you would need to accurately answer the user's question. Pick 4-6 assets.

# Very Important

For the assets indentified, ONLY return the numeric keys (from the JSON data) as a list separated by commas. Return empty string if none match. Do not return anything other than a list of keys or an empty string.
"""


def get_bellwether_assets_indices(query):
	"""
	Given a query, get the relevant bellwether assets as a list of indices that
	correspond to the `BELLWETHER_ASSETS` data.
	"""

	# Simplify the bellwether assets for the prompt
	bellwether_assets_simplified = {}
	fields_to_remove = ["api_type", "RSI", "EMA", "DEMA", "SMA"]
	for key, value in BELLWETHER_ASSETS.items():
		bellwether_assets_simplified[key] = {
			k: v for k, v in value.items() if k not in fields_to_remove
		}

	# Create the prompt
	t = Template(bellwether_template)
	c = Context(
		{
			"query": query,
			"bellwether_assets_simplified": json.dumps(
				bellwether_assets_simplified, indent=2
			),
		}
	)
	prompt = t.render(c)

	# Use the LLM to get the indices of the relevant assets
	completion = client.chat.completions.create(
		model="gpt-4.1-mini",
		messages=[
			{
				"role": "system",
				"content": "You're an AI agent assisting with investment decisions.",
			},
			{"role": "user", "content": prompt},
		],
	)
	assets = [x.strip() for x in completion.choices[0].message.content.split(",")]
	return assets


# Get the tickers


def get_tickers(query):
	"""
	Given a query, get the relevant tickers for stocks, assets,
	cryptocurrencies, etc., as a list of tickers.
	"""
	try:
		# Enhanced prompt that's more aggressive about investment queries
		completion = client.chat.completions.create(
			model="gpt-4.1-mini",
			messages=[
				{
					"role": "system",
					"content": """Given the following query, return the tickers of the stocks and assets mentioned (if any). 

For crypto, return the price to USD, for example, BTCUSD, ETHUSD, etc. 
For Gold, Silver, and other similar assets, return the price to USD, for example, XAUUSD, XAGUSD, etc.

IMPORTANT: For investment queries like "should I long/short/buy/sell X", treat X as a potential crypto token even if the name seems unusual. Many legitimate crypto tokens have unconventional names (like FART, DOGE, SHIB, etc.).

Examples:
- "should I long fart" → FARTUSD
- "buy doge" → DOGEUSD  
- "short tesla" → TSLA
- "AAPL analysis" → AAPL

Return as list of tickers separated by commas.""",
				},
				{"role": "user", "content": query},
			],
		)
		
		# Simple extraction without heavy validation
		tickers = [x.strip() for x in completion.choices[0].message.content.split(",")]
		
		# Basic cleanup - remove empty strings and common non-ticker responses
		tickers = [ticker for ticker in tickers if ticker and ticker.upper() not in ['NO', 'NONE', 'NO RELEVANT STOCKS OR ASSETS MENTIONED.', 'NO TICKERS FOUND']]
		
		return tickers
		
	except Exception as e:
		logging.error(f"Error in get_tickers: {str(e)}")
		return []


# Get full prompt
best_practice_prompt_template = """
Follow each WARNINGS point. Use the REFERENCE_MATERIAL to answer the following query, and give the answer as per RESPONSE_FORMAT. ALWAYS try to provide helpful information based on available data, even if incomplete. If data is limited, acknowledge the limitations but still provide the best analysis possible with what's available. For investment advice queries, provide general market analysis and educational information rather than specific recommendations. Always start the message with 'Hi', 'Hello', or a similar greeting, and end with a closing statement like 'Hope this helps!' or 'Let me know if you need more information!'.

If specific limitations are noted in the query context, acknowledge them transparently but still provide value using available market data, bellwether assets, economic indicators, or general financial knowledge.

{{ query }}	

# CURRENT DATE AND TIME

<!-- Removed date/time reference to avoid conflicts with economic calendar -->

When discussing market events:
1. If referring to "today" or "yesterday", explicitly mention the date (e.g., "today, April 9, 2025")
2. For "this week", specify the exact date range (e.g., "this week, April 7-13, 2025")

{%  if news_data is not None and news_data|length > 0 %}
# RECENT MARKET NEWS

The following are recent financial news headlines that may provide additional context for your response:

{% for item in news_data %}
- [{{ item.date|slice:":10" }}] {{ item.headline }} ({{ item.source }})
{% endfor %}
{% endif %}

{%  if crypto_news_data is not None and crypto_news_data|length > 0 %}
# RECENT CRYPTO NEWS

The following are recent cryptocurrency news headlines that may provide additional context for your response:

{% for item in crypto_news_data %}
- [{{ item.date|slice:":10" }}] {{ item.headline }} ({{ item.source }})
{% endfor %}
{% endif %}
3. Always clarify if economic events have already occurred or are upcoming

# RESPONSE_FORMAT
Follow the key points outlined, but use a conversational and natural tone similar to the Example Response. The goal is to provide helpful and engaging information while maintaining flexibility in phrasing. Remember, the response doesn't need to match this word-for-word. Focus on being clear, concise, and engaging like a friendly market expert sharing insights. Use REFERENCE_MATERIAL wherever required:

{% if economic_calendar_data is None and bellwether_assets is None %}
- Focus only on the asset specific data: price, RSI, EMA.
- Skip any Bellwether Index or Macroeconomic Context.

Example Response: "Here's what we're seeing with [Asset]. It's currently trading at [price], with a [rise/drop] of X% over [timeframe]. The technical indicators is showing [overbought/oversold] conditions, and the moving averages suggest [trend direction]. If you're watching this closely, the key levels to watch are [support/resistance]."

{% endif %}

{% if economic_calendar_data is None and bellwether_assets is not None %}
- Start with specific asset data, but also interpret it in the context of overall market.
- Explain how bellwether assets affects the asset in question.
- If the bellwether signals uncertainty, acknowledge that and keep the focus on direct asset indicators.

Example Response: "Beyond just this asset, the broader market is showing [risk-on/risk-off] sentiment based on the Bellwether Index. Key indicators like [Bellwether asset X] and [Bellwether asset Y] are signaling [trend direction]. This suggests that [asset] may [follow market trends/behave independently]."
{% endif %}

{% if economic_calendar_data is not None and bellwether_assets is None %}
- Keep asset specific data first, then introduce the economic calendar insights.
- If an upcoming macro event is likely to impact the asset, explain how and why.
- If no major macro event are relevant, focus on the asset without forcing economic data.

Example Response: "One thing to keep an eye on: [Upcoming Macro Event] is coming up, and that's been a key driver of volatility in the past. Historically, when we've seen [similar events], [asset] has reacted with [X% move, trend change, etc.]. If this event surprises the market, we might see [potential outcomes]."
{% endif %}

{% if economic_calendar_data is not None and bellwether_assets is not None %}
- Start with asset specific data.
- Layer in Bellwether insights if they provide useful context.
- Bring in macroeconomic events if they could impact trends.
If the macro data doesn't strongly affect the asset, don't force it - just keep the focus on the markey conditions.

Example Response: "Looking at [Asset], it's currently at [price], with technical indicators at [overbought/oversold]. The Bellwether Index suggests [risk-on/risk-off sentiment], with key assets like [X] and [Y] driving the market in [direction]. Adding to this, we have [macro event] on the horizon, which has historically led to [volatility/range-bound trading/etc.]. Recent market headlines about [relevant news topic] suggest [implications for the asset or market]. Taking all these factors into account, we might see [possible outcomes]."
{% endif %}


# WARNINGS
- Do NOT respond with code, JSON or unstructured data. Only respond with text.
- ALWAYS respond in the same language as the user's query. For example, if the query is in Chinese, respond in Chinese.
- Return the result as Markdown.
- ALWAYS mention the stock prices if they are in the REFERENCE_MATERIAL.
- ALWAYS mention the Bellwether Assets and Macroeconomic events data to provide background support for your answer, citing relevant numbers if they are in the REFERENCE_MATERIAL.
- When recent market news is provided, CONSIDER these headlines in your analysis and incorporate relevant news context that may impact the query or assets in question.
- ALWAYS use the data provided in the REFERENCE_MATERIAL - never make assumptions.
- Use a conversational, professional tone that is easy to follow.
- Do not use the words "REFERENCE_MATERIAL", "WARNINGS", and "RESPONSE FORMAT" in the answer.

# REFERENCE_MATERIAL
---
# Precision Asset Intelligence

*Precision Asset Intelligence* extracts real time market data and key technical indicators.

Example: Precision Asset Intelligence provides real-time data on key technical indicators like Open, Close, Volume, Change, Market Cap for various assets.
The following is the data for the assets: 

{% for ticker in ticker_quotes %}

Name: {{ ticker.name|safe }}
Symbol: {{ ticker.symbol|safe }}
Price: {{ ticker.price|safe }}
Change: {{ ticker.change|safe }}
Market Cap: {{ ticker.market_cap|safe }}
Volume: {{ ticker.volume|safe }}
Average Volume: {{ ticker.average_volume|safe }}
PE Ratio: {{ ticker.pe_ratio|safe }}

{% if ticker.company_profile %}
**Company Information:**
- Sector: {{ ticker.company_profile.sector|safe }}
- Industry: {{ ticker.company_profile.industry|safe }}
- Market Cap: ${{ ticker.company_profile.marketCap|safe }}
- Description: {{ ticker.company_profile.description|safe|truncatechars:150 }}
{% endif %}

{% if ticker.key_metrics %}
**Key Financial Metrics:**
- Return on Equity: {{ ticker.key_metrics.returnOnEquityTTM|safe }}%
- Return on Assets: {{ ticker.key_metrics.returnOnAssetsTTM|safe }}%
- Debt to Equity: {{ ticker.key_metrics.debtToEquity|safe }}
- Current Ratio: {{ ticker.key_metrics.currentRatioTTM|safe }}
- FCF Yield: {{ ticker.key_metrics.freeCashFlowYieldTTM|safe }}%
- R&D to Revenue: {{ ticker.key_metrics.researchAndDevelopementToRevenueTTM|safe }}%
{% endif %}

{% if ticker.earnings_info %}
**Upcoming Earnings:**
{% for event in ticker.earnings_info|slice:":2" %}
- Date: {{ event.date|safe }}, EPS Est: {% if event.epsEstimated %}${{ event.epsEstimated|safe }}{% else %}N/A{% endif %}
{% endfor %}
{% endif %}

{% if ticker.technical_indicators %}
**Technical Indicators:**
{% for name, data in ticker.technical_indicators.items %}
{% if data and data|length > 0 %}
{% if name == 'RSI' %}
- {{ name|safe }}: {{ data.0.rsi|floatformat:2 }} ({{ data.0.metadata.timeframe|safe }} Period {{ data.0.metadata.period|safe }})
{% elif name == 'EMA' %}
- {{ name|safe }}: ${{ data.0.ema|floatformat:2 }} ({{ data.0.metadata.timeframe|safe }} Period {{ data.0.metadata.period|safe }})
{% elif name == 'SMA' %}
- {{ name|safe }}: ${{ data.0.sma|floatformat:2 }} ({{ data.0.metadata.timeframe|safe }} Period {{ data.0.metadata.period|safe }})
{% elif name == 'DEMA' %}
- {{ name|safe }}: ${{ data.0.dema|floatformat:2 }} ({{ data.0.metadata.timeframe|safe }} Period {{ data.0.metadata.period|safe }})
{% endif %}
{% endif %}
{% endfor %}
{% endif %}

{% if ticker.recent_news %}
**Recent News:**
{% for item in ticker.recent_news|slice:":3" %}
- {{ item.publishedDate|safe }}: {{ item.title|safe }} ({{ item.site|safe }})
{% endfor %}
{% endif %}

{% endfor %}

{% if ticker_quotes.0.market_gainers or ticker_quotes.0.market_losers or ticker_quotes.0.sector_performance %}
# Market Context

{% if ticker_quotes.0.sector_performance %}
**Sector Performance:**
{% for sector in ticker_quotes.0.sector_performance|slice:":5" %}
- {{ sector.name|safe }}: {{ sector.changesPercentage|safe }}%
{% endfor %}
{% endif %}

{% if ticker_quotes.0.market_gainers %}
**Top Market Gainers Today:**
{% for gainer in ticker_quotes.0.market_gainers|slice:":5" %}
- {{ gainer.symbol|safe }} ({{ gainer.name|safe }}): +{{ gainer.changesPercentage|safe }}% (${{ gainer.price|safe }})
{% endfor %}
{% endif %}

{% if ticker_quotes.0.market_losers %}
**Top Market Losers Today:**
{% for loser in ticker_quotes.0.market_losers|slice:":5" %}
- {{ loser.symbol|safe }} ({{ loser.name|safe }}): {{ loser.changesPercentage|safe }}% (${{ loser.price|safe }})
{% endfor %}
{% endif %}
{% endif %}

{% if bellwether_assets is not None %}
# Bellwether X - Market Sentiment Engine

*Bellwether X Market Sentiment Engine* includes key market indicators from **bellwether assets**, providing insight into broader market sentiment.

Example: Bellwether X Market Sentiment Engine constructs a custom Bellwether Index by selecting 4-6 assets to measure market sentiment shifts.

{%  for bellwether_asset in bellwether_assets  %}

## {{ bellwether_asset.name|safe }}

{{ bellwether_asset.descriptors|safe }}

The following is the 2 hour Relative Strength Index (RSI) with a period of 28 for {{ bellwether_asset.symbol|safe }}:

```json
{{ bellwether_asset.rsi_data|safe }}
```

The following is the 4 hour Exponential Moving Average (EMA) with a period of 50 for {{ bellwether_asset.symbol|safe }}:

```json
{{ bellwether_asset.ema_data|safe }}
```

{% if bellwether_asset.sma_data %}
The following is the 4 hour Simple Moving Average (SMA) with a period of 200 for {{ bellwether_asset.symbol|safe }}:

```json
{{ bellwether_asset.sma_data|safe }}
```
{% endif %}

{% if bellwether_asset.dema_data %}
The following is the 4 hour Double Exponential Moving Average (DEMA) with a period of 20 for {{ bellwether_asset.symbol|safe }}:

```json
{{ bellwether_asset.dema_data|safe }}
```
{% endif %}

{%  endfor  %}

{% endif %}
---

{%  if economic_calendar_data is not None %}
# MacroPulse - Economic Impact Scanner

The **MacroPulse Economic Impact Scanner** tracks significant **macroeconomic events** and their potential impact on market sentiment and volatility. These events often correlate with price movements and can create actionable insights for trade strategies. The following is the economic events for today and plus minus 3 days. Each day has a volatility score. The higher the volatility score, the higher the expected market volatility.

Example: The MacroPulse - Economic Impact Scanner analyzes macroeconomic events to predict market volatility and trading opportunities.

```json
{{ economic_calendar_data.week|safe }}
```

The following are the thresholds for the volatility scores for each day:

```json
{{ economic_calendar_data.thresholds|safe }}
```

{%  endif  %}

---

{% if economic_calendar_data is not None %}
# Strykr Volatility Score

The **Strykr Volatility Score** provides a daily forecast of market volatility, predicting the expected market fluctuations over the next 30 days. It helps assess the risk associated with current market conditions and informs the user about the likelihood of sudden price swings across asset classes.

*Example*: The Strykr Volatility Score for Bitcoin is {Strykr Volatility Score}, indicating {high/low} volatility over the next 30 days, which suggests increased price swings in the crypto market.

{%  endif  %}

{% if ticker_quotes %}
# Asset Data

This section includes data for the specific assets mentioned in the query.

{% for ticker in ticker_quotes %}
## {{ ticker.name|default:ticker.symbol }}

Price: **${{ ticker.price }}**
Change: **{{ ticker.change }}%**

Volume: **{{ ticker.volume }}**

{% if ticker.technical_indicators.RSI or ticker.technical_indicators.EMA or ticker.technical_indicators.SMA or ticker.technical_indicators.DEMA %}### Technical Indicators:
{% if ticker.technical_indicators.RSI %}
**RSI ({{ ticker.technical_indicators.RSI.0.metadata.timeframe }}, Period {{ ticker.technical_indicators.RSI.0.metadata.period }}):** {{ ticker.technical_indicators.RSI.0.rsi|floatformat:2 }}
{% endif %}

{% if ticker.technical_indicators.EMA %}
**EMA ({{ ticker.technical_indicators.EMA.0.metadata.timeframe }}, Period {{ ticker.technical_indicators.EMA.0.metadata.period }}):** ${{ ticker.technical_indicators.EMA.0.ema|floatformat:2 }}
{% endif %}

{% if ticker.technical_indicators.SMA %}
**SMA ({{ ticker.technical_indicators.SMA.0.metadata.timeframe }}, Period {{ ticker.technical_indicators.SMA.0.metadata.period }}):** ${{ ticker.technical_indicators.SMA.0.sma|floatformat:2 }}
{% endif %}

{% if ticker.technical_indicators.DEMA %}
**DEMA ({{ ticker.technical_indicators.DEMA.0.metadata.timeframe }}, Period {{ ticker.technical_indicators.DEMA.0.metadata.period }}):** ${{ ticker.technical_indicators.DEMA.0.dema|floatformat:2 }}
{% endif %}

{% if ticker.technical_indicators.RSI or ticker.technical_indicators.EMA or ticker.technical_indicators.SMA or ticker.technical_indicators.DEMA %}
IMPORTANT: When referencing these technical indicators in your response:
1. Format EMA, SMA, and DEMA values with dollar signs as they represent price levels (e.g., $1,500.00), unlike RSI which is a scale from 0-100.
2. Always use thousand separators (commas) for all numeric values over 999 in your response (e.g., $1,500.00 not $1500.00, 1,000,000 not 1000000).
{% endif %}
{% endif %}
{% endfor %}
{% endif %}

---

# QUERY-SPECIFIC GUIDANCE

## For Entry/Exit Point Questions
If the query is asking about entry/exit points, price targets, or good buying/selling levels:
1. Provide at least 2-3 price levels with clear rationale for each
2. Always include both technical and fundamental factors in your assessment
3. Clarify if your advice is for short-term or longer-term positions
4. Include risk management considerations alongside entry points (stop loss suggestions)

## For Risk Management Questions
If the query is about stop losses, position sizing, or risk management:
1. Default to conservative position sizing (1-2% of capital per trade)
2. Provide specific stop loss placement strategies with rationale
3. Suggest multiple stop options when appropriate (tight, standard, and loose)
4. Include the risk-to-reward ratio in your assessment

## For Economic Calendar Questions
If the query is about economic events or the economic calendar:
1. Prioritize HIGH and MEDIUM impact events in your response
2. Clearly indicate the date and time of each event
3. Explain potential market impact on relevant assets
4. Present events in chronological order

## For Market Sentiment Questions
If the query is asking about whether markets are bullish/bearish or risk-on/risk-off:
1. Reference specific bellwether assets as evidence for your assessment
2. Break down sentiment by sector or market when relevant
3. Explain any contradictory signals when present
4. Include both technical indicators and macro factors

## For Technical Analysis Questions
If the query is about technical indicators or chart patterns:
1. Explain what the indicator values suggest about market conditions
2. Put indicator readings in context (oversold, overbought, neutral)
3. Reference historical patterns when relevant
4. Suggest confirmation signals to watch for

# RESPONSE FORMATTING

1. Structure your response with clear sections using headers
2. Format all numbers consistently:
   - Use commas as thousand separators (e.g., $1,234.56)
   - Use dollar signs for price values
   - Show percentages with two decimal places (e.g., 12.34%)
3. When information is uncertain or missing:
   - Acknowledge the limitation explicitly
   - Provide general guidance based on available information
   - Suggest alternative approaches
4. End with 1-3 actionable takeaways or next steps

# Analysis Requirements

To provide the user with a complete assessment, you should evaluate the following perspectives and provide a summary of your findings as well, taking reference from REFERENCE_MATERIAL:

## Technical Analysis

**Price, Volume, Market Cap, Technical Indicators, PE Ratio and other related metrics in the REFERENCE_MATERIAL:** Evaluate whether the asset is overbought or oversold, its trend strength, and key support/resistance levels. If technical indicators are available, consider how they inform your analysis.

{%  if economic_calendar_data is not None %}
## Economic Calendar Impact

**Upcoming Events:** Analyze the likely impact of major macroeconomic events on the asset's price and **Strykr Volatility**.

## Market Structure Analysis

Evaluate the overall market trend, such as whether it is in a **bullish**, **bearish**, or **sideways** phase. Consider volatility levels, key technical patterns (e.g., breakouts, consolidations), and sentiment (risk-on vs. risk-off) to determine potential trade strategies.
{% endif %}

{% if bellwether_assets is not None %}
## Market Sentiment Interpretation (Risk-On/Risk-Off)

Analyze key bellwether assets (such as SPX500, VIX, EUR/USD, DXY, etc.) to determine the market's overall risk appetite (risk-on vs. risk-off). This helps assess whether investors are seeking higher risk/reward opportunities or are more risk-averse.
{% endif %}
---

"""

def get_full_prompt(query, ticker_quotes=[], bellwether_assets=[], economic_calendar_data=[], news_data=None, crypto_news_data=None, query_context=None):
	"""
	Given a query, ticker quotes, bellwether assets, economic calendar data, news data, and query context,
	get the full prompt needed to create a detailed response.
	"""
	
	# Removed datetime logic to avoid conflicts with economic calendar
	
	# Ensure ticker quotes are properly formatted with technical indicators
	processed_ticker_quotes = []
	for quote in ticker_quotes:
		logging.info(f"Processing quote for {quote.get('symbol', 'unknown')}: {quote}")
		if isinstance(quote, dict):
			# Keep the existing technical_indicators if available
			if "technical_indicators" not in quote:
				logging.info(f"No technical indicators found for {quote.get('symbol', 'unknown')}")
				quote["technical_indicators"] = {}
			else:
				logging.info(f"Technical indicators found for {quote.get('symbol', 'unknown')}: {quote['technical_indicators']}")
			processed_ticker_quotes.append(quote)

	# Create and return the prompt
	prompt = None
	try:
			# Safely add news data to context
		news_data_for_prompt = None
		try:
			if news_data and isinstance(news_data, list) and len(news_data) > 0:
				print(f">>> NEWS DEBUG: Received {len(news_data)} news items to process")
				# Validate each news item to ensure it won't break template rendering
				validated_news = []
				for item in news_data:
					if not isinstance(item, dict):
						continue
					
					# Ensure all required fields are present and valid
					if all(k in item and item[k] for k in ['headline', 'source', 'date']):
						validated_news.append(item)
				
				# Only use news if we have valid items
				if validated_news:
					news_data_for_prompt = validated_news
					print(f">>> NEWS DEBUG: Added {len(validated_news)} validated news items to prompt")
					# Print the first few headlines to confirm content
					for i, item in enumerate(validated_news[:3]):
						print(f">>> NEWS HEADLINE {i+1}: {item['headline'][:50]}...")
				else:
					news_data_for_prompt = None
					logging.warning("No valid news items found in news data")
			else:
				print(">>> NEWS DEBUG: No news data received")
		except Exception as e:
			# If news processing fails, log and continue without news
			logging.error(f"Error processing news data for prompt: {str(e)}")
			news_data_for_prompt = None
		
		# Create context with all data
		t = Template(best_practice_prompt_template)
		c = Context(
			{
				"query": query,
				"economic_calendar_data": economic_calendar_data if economic_calendar_data else None,
				"bellwether_assets": bellwether_assets if bellwether_assets else None,
				"ticker_quotes": processed_ticker_quotes,
				"news_data": news_data_for_prompt,
				"crypto_news_data": crypto_news_data if crypto_news_data else None,
				"query_context": query_context
			}
		)
		prompt = t.render(c)
	except Exception as e:
		# If anything fails in the template rendering, fall back to basic prompt without news
		logging.error(f"Error rendering prompt template with news: {str(e)}")
		# Create context without news data as a fallback
		try:
			t = Template(best_practice_prompt_template)
			c = Context(
				{
					"query": query,
					"economic_calendar_data": economic_calendar_data if economic_calendar_data else None,
					"bellwether_assets": bellwether_assets if bellwether_assets else None,
					"ticker_quotes": processed_ticker_quotes,
					"news_data": None,
					"crypto_news_data": None,
					"query_context": query_context
				}
			)
			prompt = t.render(c)
		except Exception as e2:
			logging.error(f"Fatal error in prompt building: {str(e2)}")
			# Last resort fallback - return just the query
			prompt = f"USER QUERY:\n\n{query}"
	
	return prompt
