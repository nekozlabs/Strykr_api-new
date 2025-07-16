from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
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
	allowed_domains = ArrayField(
		models.CharField(max_length=255), blank=True, null=True, default=list
	)
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