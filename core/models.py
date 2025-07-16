from django.contrib.auth.models import User
try:
    from django.contrib.postgres.fields import ArrayField
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
from django.db import models
from django.utils.crypto import get_random_string
from datetime import timezone

class Org(models.Model):
	"""
	A business or team that wants to use the API.
	"""

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	name = models.CharField(max_length=255)
	is_verified = models.BooleanField(default=False)

	def __str__(self):
		return self.name


def create_random_api_key():
	"""Generate a random API key."""
	return get_random_string(24)


class APIKey(models.Model):
	"""
	A key that gives access to the API.
	"""

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	org = models.ForeignKey(Org, on_delete=models.CASCADE)
	user_id = models.CharField(max_length=255, default = "NOTAREALUSERID")  # Adding the user_id field.
	#user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_keys") # To clearly identify the user.
	name = models.CharField(max_length=255)
	key = models.CharField(
		max_length=24, unique=True, db_index=True, default=create_random_api_key
	)
	client_side_key = models.CharField(
		max_length=24, unique=True, db_index=True, default=create_random_api_key
	)
	# Use JSONField for cross-database compatibility (PostgreSQL ArrayField equivalent)
	allowed_domains = models.JSONField(blank=True, null=True, default=list)
	is_revoked = models.BooleanField(default=False)
	is_unlimited = models.BooleanField(default=False)

	daily_limit = models.IntegerField(default=0)
	expires_at = models.DateTimeField(blank=True, null=True)
	monthly_limit = models.IntegerField(default=0)
	permission_level = models.CharField(max_length=255, blank=True, null=True)
	# permission_level = models.IntegerField(default=0)

	def __str__(self):
		return self.name

	def is_valid(self):
		"""
		Check if API key is valid to use or not.
		"""
		if self.is_revoked:
			return False

		if self.is_unlimited:
			return True

		# TODO: implement time based validity
		if self.expires_at and self.expires_at < timezone.now():
			return False
		
		# TODO: check whether number of requests are less than monthly.

		return True


class AIQuery(models.Model):
	"""
	Stores an AI query sent to the API.
	"""

	created_at = models.DateTimeField(auto_now_add=True)
	user = models.ForeignKey(
		User,
		blank=True,
		null=True,
		on_delete=models.SET_NULL,
	)
	api_key = models.ForeignKey(
		APIKey,
		blank=True,
		null=True,
		on_delete=models.SET_NULL,
	)
	query = models.TextField()
	third_party_user_id = models.CharField(max_length=255, blank=True)

	class Meta:
		verbose_name_plural = "AI queries"

	def __str__(self):
		return self.query


class EconomicEvents(models.Model):
	"""
	Stores economic events for a month.
	"""

	updated_at = models.DateTimeField(auto_now=True)
	month = models.CharField(max_length=3)
	year = models.CharField(max_length=4)
	data = models.JSONField(default=dict)

	class Meta:
		verbose_name_plural = "Economic events"
		ordering = ["-updated_at"]

	def __str__(self):
		return f"{self.month} {self.year}"


class BellwetherAsset(models.Model):
	"""
	Stores bellwether assets.
	"""

	updated_at = models.DateTimeField(auto_now=True)
	name = models.CharField(max_length=255)
	symbol = models.CharField(max_length=255)
	descriptors = models.TextField()
	api_type = models.IntegerField()
	data_type = models.CharField(max_length=255)
	data = models.JSONField(default=dict)

	class Meta:
		ordering = ["-updated_at"]

	def __str__(self):
		return f"{self.symbol} {self.data_type}"


class MarketAlert(models.Model):
	"""Market alert with push notification and detailed analysis."""
	RISK_LEVELS = [
		('LOW', 'Low Risk'),
		('MEDIUM', 'Medium Risk'),
		('HIGH', 'High Risk')
	]

	timestamp = models.DateTimeField(auto_now_add=True)
	risk_level = models.CharField(max_length=20, choices=RISK_LEVELS)
	short_summary = models.CharField(max_length=200)  # For push notifications
	full_analysis = models.JSONField(default=dict)    # Extended summary and detailed analysis. Need to ensure JSON formatting is correct.
	assets_analyzed = models.ManyToManyField(BellwetherAsset)

	class Meta:
		ordering = ["-timestamp"]
		verbose_name = "Market Alert"
		verbose_name_plural = "Market Alerts"

	def __str__(self):
		return f"{self.risk_level} Alert: {self.short_summary[:50]}..."

	def get_emoji(self):
		"""Returns the appropriate emoji for the risk level."""
		return {
			'LOW': '🟢',
			'MEDIUM': '🟡',
			'HIGH': '🔴'
		}.get(self.risk_level, '⚪')

	def get_notification_text(self):
		"""Returns formatted text for push notification."""
		return f"{self.get_emoji()} {self.risk_level}: {self.short_summary}"




class CalendarMarketAlert(models.Model):
	"""Calendar-based market alert with volatility analysis."""
	timestamp = models.DateTimeField(auto_now_add=True)
	analysis_period_start = models.DateTimeField()
	volatile_window_start = models.DateTimeField()
	volatile_window_end = models.DateTimeField()

	# Daily score
	strykr_score = models.FloatField(default=0.0)

	# Window-specific volatility
	window_volatility_rating = models.FloatField(default=0.0)
	window_volatility_intensity = models.CharField(
		max_length=20,
		choices=[
			('Low', 'Low'),
			('Moderate', 'Moderate'),
			('High', 'High'),
			('Extreme', 'Extreme'),
			('Critical', 'Critical'),
		],
		default='Low'
	)

	short_summary = models.TextField()
	full_analysis = models.TextField()
	events_analyzed = models.JSONField(default=list)

	class Meta:
		ordering = ['-timestamp']
		verbose_name = "Calendar Market Alert"
		verbose_name_plural = "Calendar Market Alerts"
		indexes = [
			models.Index(fields=['timestamp']),
			models.Index(fields=['window_volatility_intensity'])
		]

	def __str__(self):
		return f"Calendar Alert {self.timestamp.strftime('%Y-%m-%d %H:%M')} - {self.window_volatility_intensity}"

	def get_emoji(self):
		"""Returns the appropriate emoji for the volatility intensity."""
		return {
			'Low': '⚡️',
			'Moderate': '⚡️⚡️',
			'High': '⚡️⚡️⚡️',
			'Extreme': '⚠️⚡️',
			'Critical': '🚨⚡️'
		}.get(self.window_volatility_intensity, '⚡️')

	def get_notification_text(self):
		"""Returns formatted text for push notification."""
		return f"{self.get_emoji()} Strykr Score: {self.strykr_score} | Volatility: {self.window_volatility_rating} ({self.window_volatility_intensity}) - {self.short_summary}"



class NewsMarketAlert(models.Model):
    """News-based market alert with summary and sentiment analysis."""
    timestamp = models.DateTimeField(auto_now_add=True)
    summary = models.TextField()
    sentiment = models.CharField(
        max_length=20,
        choices=[
            ('Bullish', 'Bullish'),
            ('Neutral', 'Neutral'),
            ('Bearish', 'Bearish')
        ],
        default='Neutral'
    )
    sentiment_reasoning = models.TextField()
    news_articles = models.JSONField(default=list)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "News Market Alert"
        verbose_name_plural = "News Market Alerts"

    def __str__(self):
        return f"News Alert {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    def get_emoji(self):
        return {
            'Bullish': '🟢',
            'Neutral': '⚪',
            'Bearish': '🔴'
        }.get(self.sentiment, '⚪')

    def get_notification_text(self):
        return f"{self.get_emoji()} NEWS ALERT: {self.summary[:100]}..."




class CryptoNewsAlert(models.Model):
    """Crypto-specific news alert with summary and sentiment analysis."""
    timestamp = models.DateTimeField(auto_now_add=True)
    summary = models.TextField()
    sentiment = models.CharField(
        max_length=20,
        choices=[
            ('Bullish', 'Bullish'),
            ('Neutral', 'Neutral'),
            ('Bearish', 'Bearish')
        ],
        default='Neutral'
    )
    sentiment_reasoning = models.TextField()
    crypto_news_articles = models.JSONField(default=list)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Crypto News Alert"
        verbose_name_plural = "Crypto News Alerts"
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['sentiment'])
        ]

    def __str__(self):
        return f"Crypto News Alert {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    def get_emoji(self):
        return {
            'Bullish': '🟢',
            'Neutral': '⚪',
            'Bearish': '🔴'
        }.get(self.sentiment, '⚪')

    def get_notification_text(self):
        return f"{self.get_emoji()} CRYPTO NEWS ALERT: {self.summary[:100]}..."


class MarketScreenerResult(models.Model):
	"""Stores market screener results with top stocks/cryptos to long/short."""
	timestamp = models.DateTimeField(auto_now_add=True)
	analysis_date = models.DateField()

	# Stocks to long
	top_stocks_long = models.JSONField(default=list)

	# Stocks to short
	top_stocks_short = models.JSONField(default=list)

	# Cryptos to long
	top_cryptos_long = models.JSONField(default=list)

	# Cryptos to short
	top_cryptos_short = models.JSONField(default=list)

	# Market Sentiment Score
	market_sentiment_score = models.FloatField(default=0.0, help_text="Market sentiment score from -100 to 100")

	# Market Sentiment
	market_sentiment = models.CharField(
        max_length=20,
        choices=[
            ('Bearish', 'Bearish'),
            ('Mildly Bearish', 'Mildly Bearish'),
            ('Neutral', 'Neutral'),
            ('Mildly Bullish', 'Mildly Bullish'),
            ('Bullish', 'Bullish'),
        ],
        default='Neutral'
    )

	# Explanation
	explanation = models.TextField(blank=True, help_text="GPT-generated explanation of market sentiment and recommendations")

	class Meta:
		ordering = ['-timestamp']
		verbose_name = "Market Screener Result"
		verbose_name_plural = "Market Screener Results"
		indexes = [
			models.Index(fields=['timestamp']),
			models.Index(fields=['analysis_date']),
			models.Index(fields=['market_sentiment']),
		]

	def __str__(self):
		return f"Market Screener {self.analysis_date.strftime('%Y-%m-%d')} - {self.market_sentiment}"

	
	def get_emoji(self):
		"""Returns the appropriate emoji for the market sentiment."""
		return {
            'Bullish': '🟢',
            'Mildly Bullish': '🟢',
            'Neutral': '⚪',
            'Mildly Bearish': '🔴',
            'Bearish': '🔴',
        }.get(self.market_sentiment, '⚪')

	def get_notification_text(self):
		"""Returns formatted text for push notification."""
		return f"{self.get_emoji()} Market Screener: {self.market_sentiment} | Score: {self.market_sentiment_score}"


# Enhanced Models for Comprehensive Backtesting Database API

class HistoricalMarketData(models.Model):
	"""
	Stores historical market data for individual assets for backtesting analysis.
	This model tracks detailed price, volume, and performance metrics over time.
	"""
	timestamp = models.DateTimeField(auto_now_add=True)
	analysis_date = models.DateField(db_index=True)
	
	# Asset identification
	symbol = models.CharField(max_length=50, db_index=True)
	asset_type = models.CharField(
		max_length=20,
		choices=[
			('STOCK', 'Stock'),
			('CRYPTO', 'Cryptocurrency'),
			('ETF', 'ETF'),
			('FOREX', 'Forex'),
			('COMMODITY', 'Commodity'),
		],
		default='STOCK',
		db_index=True
	)
	
	# Basic market data
	open_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
	close_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
	high_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
	low_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
	volume = models.BigIntegerField(null=True, blank=True)
	market_cap = models.BigIntegerField(null=True, blank=True)
	
	# Performance metrics
	change_1d = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
	change_7d = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
	change_30d = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
	
	# Technical indicators
	rsi_14 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
	ema_50 = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
	sma_200 = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
	
	# Market screener specific data
	screener_position = models.CharField(
		max_length=20,
		choices=[
			('LONG', 'Long Position'),
			('SHORT', 'Short Position'),
			('NEUTRAL', 'Neutral'),
		],
		null=True,
		blank=True,
		db_index=True
	)
	confidence_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
	rank_in_category = models.IntegerField(null=True, blank=True)
	
	# Additional metadata
	sector = models.CharField(max_length=100, null=True, blank=True)
	industry = models.CharField(max_length=100, null=True, blank=True)
	data_source = models.CharField(max_length=50, default='strykr_api')
	
	class Meta:
		ordering = ['-analysis_date', '-timestamp']
		verbose_name = "Historical Market Data"
		verbose_name_plural = "Historical Market Data"
		indexes = [
			models.Index(fields=['symbol', 'analysis_date']),
			models.Index(fields=['asset_type', 'analysis_date']),
			models.Index(fields=['screener_position', 'analysis_date']),
			models.Index(fields=['analysis_date', 'confidence_score']),
			models.Index(fields=['sector', 'analysis_date']),
			# Composite index for common queries
			models.Index(fields=['symbol', 'asset_type', 'analysis_date']),
		]
		constraints = [
			models.UniqueConstraint(
				fields=['symbol', 'asset_type', 'analysis_date'], 
				name='unique_symbol_type_date'
			)
		]

	def __str__(self):
		return f"{self.symbol} ({self.asset_type}) - {self.analysis_date}"


class PortfolioSnapshot(models.Model):
	"""
	Tracks portfolio performance snapshots based on market screener recommendations.
	Used for backtesting portfolio strategies and tracking performance over time.
	"""
	timestamp = models.DateTimeField(auto_now_add=True)
	snapshot_date = models.DateField(db_index=True)
	
	# Portfolio metadata
	portfolio_name = models.CharField(max_length=100, default='default')
	strategy_type = models.CharField(
		max_length=50,
		choices=[
			('LONG_ONLY', 'Long Only'),
			('SHORT_ONLY', 'Short Only'),
			('LONG_SHORT', 'Long/Short'),
			('MARKET_NEUTRAL', 'Market Neutral'),
		],
		default='LONG_SHORT'
	)
	
	# Portfolio metrics
	total_value = models.DecimalField(max_digits=20, decimal_places=2, default=100000.00)
	long_exposure = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
	short_exposure = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
	cash_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
	
	# Performance metrics
	daily_return = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
	cumulative_return = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
	max_drawdown = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
	sharpe_ratio = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
	
	# Risk metrics
	volatility = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
	var_95 = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)  # Value at Risk
	beta = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
	
	# Market context
	market_sentiment_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
	benchmark_return = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)  # S&P 500 or custom benchmark
	
	# Source screener data
	source_screener = models.ForeignKey(
		MarketScreenerResult, 
		on_delete=models.SET_NULL, 
		null=True, 
		blank=True,
		related_name='portfolio_snapshots'
	)
	
	class Meta:
		ordering = ['-snapshot_date', '-timestamp']
		verbose_name = "Portfolio Snapshot"
		verbose_name_plural = "Portfolio Snapshots"
		indexes = [
			models.Index(fields=['portfolio_name', 'snapshot_date']),
			models.Index(fields=['strategy_type', 'snapshot_date']),
			models.Index(fields=['snapshot_date', 'total_value']),
			models.Index(fields=['snapshot_date', 'cumulative_return']),
		]

	def __str__(self):
		return f"{self.portfolio_name} - {self.snapshot_date} (${self.total_value:,.2f})"


class PortfolioPosition(models.Model):
	"""
	Tracks individual positions within a portfolio snapshot.
	Links to HistoricalMarketData for detailed asset information.
	"""
	portfolio_snapshot = models.ForeignKey(
		PortfolioSnapshot,
		on_delete=models.CASCADE,
		related_name='positions'
	)
	
	# Position details
	symbol = models.CharField(max_length=50, db_index=True)
	asset_type = models.CharField(max_length=20, choices=HistoricalMarketData.asset_type.field.choices)
	position_type = models.CharField(
		max_length=10,
		choices=[
			('LONG', 'Long'),
			('SHORT', 'Short'),
		]
	)
	
	# Position sizing
	quantity = models.DecimalField(max_digits=20, decimal_places=8)
	entry_price = models.DecimalField(max_digits=20, decimal_places=8)
	current_price = models.DecimalField(max_digits=20, decimal_places=8)
	position_value = models.DecimalField(max_digits=20, decimal_places=2)
	weight = models.DecimalField(max_digits=6, decimal_places=4)  # Percentage of portfolio
	
	# Performance
	unrealized_pnl = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
	unrealized_pnl_percent = models.DecimalField(max_digits=10, decimal_places=4, default=0.00)
	
	# Market screener data
	confidence_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
	original_rank = models.IntegerField(null=True, blank=True)  # Rank in original screener
	
	# Risk management
	stop_loss = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
	take_profit = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
	
	# Link to historical data
	historical_data = models.ForeignKey(
		HistoricalMarketData,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='positions'
	)
	
	class Meta:
		ordering = ['-weight', 'symbol']
		verbose_name = "Portfolio Position"
		verbose_name_plural = "Portfolio Positions"
		indexes = [
			models.Index(fields=['symbol', 'position_type']),
			models.Index(fields=['portfolio_snapshot', 'symbol']),
			models.Index(fields=['position_type', 'unrealized_pnl_percent']),
		]

	def __str__(self):
		return f"{self.symbol} ({self.position_type}) - {self.weight}% of portfolio"


class BacktestResult(models.Model):
	"""
	Stores comprehensive backtest results for different strategies and time periods.
	Aggregates portfolio performance over time for analysis.
	"""
	timestamp = models.DateTimeField(auto_now_add=True)
	
	# Backtest parameters
	strategy_name = models.CharField(max_length=100)
	start_date = models.DateField()
	end_date = models.DateField()
	initial_capital = models.DecimalField(max_digits=20, decimal_places=2, default=100000.00)
	
	# Strategy configuration
	rebalance_frequency = models.CharField(
		max_length=20,
		choices=[
			('DAILY', 'Daily'),
			('WEEKLY', 'Weekly'),
			('MONTHLY', 'Monthly'),
			('QUARTERLY', 'Quarterly'),
		],
		default='DAILY'
	)
	max_positions = models.IntegerField(default=10)
	position_sizing = models.CharField(
		max_length=20,
		choices=[
			('EQUAL_WEIGHT', 'Equal Weight'),
			('CONFIDENCE_WEIGHT', 'Confidence Weighted'),
			('VOLATILITY_WEIGHT', 'Volatility Weighted'),
			('RISK_PARITY', 'Risk Parity'),
		],
		default='EQUAL_WEIGHT'
	)
	
	# Performance results
	final_value = models.DecimalField(max_digits=20, decimal_places=2)
	total_return = models.DecimalField(max_digits=10, decimal_places=4)
	annualized_return = models.DecimalField(max_digits=10, decimal_places=4)
	volatility = models.DecimalField(max_digits=6, decimal_places=3)
	sharpe_ratio = models.DecimalField(max_digits=6, decimal_places=3)
	max_drawdown = models.DecimalField(max_digits=10, decimal_places=4)
	calmar_ratio = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
	
	# Risk metrics
	var_95 = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
	beta = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
	alpha = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
	
	# Trade statistics
	total_trades = models.IntegerField(default=0)
	winning_trades = models.IntegerField(default=0)
	losing_trades = models.IntegerField(default=0)
	win_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
	avg_win = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
	avg_loss = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
	profit_factor = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
	
	# Benchmark comparison
	benchmark_return = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
	excess_return = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
	information_ratio = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
	
	# Configuration and metadata
	configuration = models.JSONField(default=dict)  # Store strategy parameters
	execution_time = models.DurationField(null=True, blank=True)
	data_quality_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
	
	class Meta:
		ordering = ['-timestamp']
		verbose_name = "Backtest Result"
		verbose_name_plural = "Backtest Results"
		indexes = [
			models.Index(fields=['strategy_name', 'start_date', 'end_date']),
			models.Index(fields=['annualized_return', 'sharpe_ratio']),
			models.Index(fields=['start_date', 'end_date']),
			models.Index(fields=['total_return']),
		]

	def __str__(self):
		return f"{self.strategy_name} ({self.start_date} to {self.end_date}) - {self.total_return:.2%} return"


class TradingSignal(models.Model):
	"""
	Stores individual trading signals generated by the market screener.
	Used for tracking signal performance and generating trade recommendations.
	"""
	timestamp = models.DateTimeField(auto_now_add=True)
	signal_date = models.DateField(db_index=True)
	
	# Signal details
	symbol = models.CharField(max_length=50, db_index=True)
	asset_type = models.CharField(max_length=20, choices=HistoricalMarketData.asset_type.field.choices)
	signal_type = models.CharField(
		max_length=10,
		choices=[
			('BUY', 'Buy'),
			('SELL', 'Sell'),
			('HOLD', 'Hold'),
		],
		db_index=True
	)
	
	# Signal strength and confidence
	strength = models.CharField(
		max_length=10,
		choices=[
			('WEAK', 'Weak'),
			('MODERATE', 'Moderate'),
			('STRONG', 'Strong'),
		],
		default='MODERATE'
	)
	confidence_score = models.DecimalField(max_digits=5, decimal_places=2)
	
	# Price and timing
	signal_price = models.DecimalField(max_digits=20, decimal_places=8)
	target_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
	stop_loss_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
	timeframe = models.CharField(max_length=20, default='1-7 days')
	
	# Signal source and reasoning
	source_screener = models.ForeignKey(
		MarketScreenerResult,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='trading_signals'
	)
	reasoning = models.TextField(blank=True)
	technical_factors = models.JSONField(default=list)  # List of technical indicators supporting signal
	fundamental_factors = models.JSONField(default=list)  # List of fundamental factors
	
	# Signal status and performance tracking
	status = models.CharField(
		max_length=20,
		choices=[
			('ACTIVE', 'Active'),
			('EXECUTED', 'Executed'),
			('EXPIRED', 'Expired'),
			('CANCELLED', 'Cancelled'),
		],
		default='ACTIVE',
		db_index=True
	)
	
	# Performance tracking (filled when signal is closed)
	exit_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
	exit_date = models.DateField(null=True, blank=True)
	realized_return = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
	holding_period = models.IntegerField(null=True, blank=True)  # Days held
	
	class Meta:
		ordering = ['-signal_date', '-confidence_score']
		verbose_name = "Trading Signal"
		verbose_name_plural = "Trading Signals"
		indexes = [
			models.Index(fields=['symbol', 'signal_date']),
			models.Index(fields=['signal_type', 'signal_date']),
			models.Index(fields=['status', 'signal_date']),
			models.Index(fields=['confidence_score', 'signal_date']),
			models.Index(fields=['asset_type', 'signal_type', 'signal_date']),
		]

	def __str__(self):
		return f"{self.signal_type} {self.symbol} @ ${self.signal_price} (Confidence: {self.confidence_score})"