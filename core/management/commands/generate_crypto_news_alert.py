from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from openai import OpenAI
from core.models import CryptoNewsAlert
import json
import logging
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Generate crypto news alerts based on recent crypto news'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Test without creating alert'
        )

    def generate_gpt_analysis(self, crypto_news_articles, client):
        """Generate analysis using GPT-4.1-mini with crypto-specific prompts."""
        prompt = {
            "crypto_news_articles": crypto_news_articles,
            "current_date": timezone.now().strftime("%Y-%m-%d")
        }
        
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": """You are a cryptocurrency market expert analyzing recent crypto news. Your task is to analyze recent cryptocurrency news articles and provide actionable insights for crypto traders.
                
                GUIDELINES:
                1. FOCUS ON MAJOR THEMES: Identify the key narratives across multiple crypto news stories
                2. ASSET SPECIFICITY: Note which cryptocurrencies and blockchain networks are most affected
                3. NUMBER FORMATTING: Format all numeric values with proper commas for thousands (e.g., $1,500 not $1500)
                
                OUTPUTS REQUIRED:
                1. SUMMARY: Concise summary of key crypto market developments
                2. SENTIMENT: Overall crypto market sentiment (Bullish, Bearish, or Neutral)
                3. SENTIMENT REASONING: Brief explanation of your sentiment analysis
                
                Provide your response in JSON format only: {"summary": "<SUMMARY>", "sentiment": "<BULLISH/BEARISH/NEUTRAL>", "sentiment_reasoning": "<REASONING>"}
                """},
                {"role": "user", "content": f"Analyze these recent crypto news articles: {json.dumps(prompt, indent=2)}"}
            ],
            response_format = {"type": "json_object"}
        )

        response_content = response.choices[0].message.content
        analysis = json.loads(response_content)
        
        summary = analysis.get("summary", "")
        sentiment = analysis.get("sentiment", "Neutral")
        sentiment_reasoning = analysis.get("sentiment_reasoning", "")
        
        return summary, sentiment, sentiment_reasoning

    def fetch_crypto_news(self, api_key, limit=20):
        """Fetch recent crypto news from FMP crypto-latest endpoint."""
        if not api_key:
            print("[CRYPTO NEWS INTEGRATION] No API key provided for crypto news fetching")
            logging.error("No API key provided for crypto news fetching")
            return []
            
        # Use the crypto-latest endpoint
        url = f"https://financialmodelingprep.com/stable/news/crypto-latest?page=0&limit={limit}&apikey={api_key}"
        
        try:
            print(f"[CRYPTO NEWS INTEGRATION] Attempting to fetch crypto news from FMP API")
            response = requests.get(url)
            
            if response.status_code != 200:
                print(f"[CRYPTO NEWS INTEGRATION] Failed to fetch crypto news: HTTP {response.status_code}")
                logging.error(f"Failed to fetch crypto news: HTTP {response.status_code}")
                return []
                
            news_data = response.json()
            
            if not isinstance(news_data, list):
                print("[CRYPTO NEWS INTEGRATION] No valid crypto news data received from API")
                logging.warning("No valid crypto news data received from API")
                return []
            
            # Filter for recent news (last 24 hours)
            cutoff_time = datetime.now() - timedelta(hours=24)
            print(f"[CRYPTO NEWS INTEGRATION] Filtering crypto news since {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")
            recent_news = []
            
            for item in news_data:
                try:
                    if not isinstance(item, dict):
                        continue
                        
                    pub_date_str = item.get("publishedDate", "")
                    if not pub_date_str:
                        continue
                        
                    pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d %H:%M:%S")
                    if pub_date >= cutoff_time:
                        headline = item.get("title", "")
                        source = item.get("site", "") or item.get("publisher", "")
                        date = item.get("publishedDate", "")
                        text_snippet = item.get("text", "")
                        
                        # Ensure we have valid data
                        if headline and source:
                            # Truncate snippet if it's too long
                            if text_snippet and len(text_snippet) > 150:
                                text_snippet = text_snippet[:147] + "..."
                                
                            recent_news.append({
                                "headline": headline, 
                                "source": source,
                                "date": date,
                                "snippet": text_snippet
                            })
                except (ValueError, KeyError) as e:
                    # Skip items with invalid data format
                    logging.warning(f"Skipping crypto news item due to format error: {str(e)}")
                    continue
            
            # Sort by date (most recent first)
            recent_news.sort(key=lambda x: x.get("date", ""), reverse=True)
            return recent_news[:20]  # Return top 20 most recent crypto news items
                
        except Exception as e:
            logging.error(f"Error fetching crypto news: {str(e)}")
            return []
    
    def handle(self, *args, **options):
        try:
            client = OpenAI(timeout=30.0)
            
            # Fetch recent crypto news
            api_key = settings.FMP_API_KEY
            crypto_news_articles = self.fetch_crypto_news(api_key)
            
            if not crypto_news_articles:
                self.stdout.write("No crypto news articles found")
                return
                
            # Generate analysis
            summary, sentiment, sentiment_reasoning = self.generate_gpt_analysis(crypto_news_articles, client)
            
            if options['dry_run']:
                self.stdout.write(f"\nWould create crypto news alert with summary: {summary}")
                self.stdout.write(f"Sentiment: {sentiment}")
                self.stdout.write(f"Reasoning: {sentiment_reasoning}")
                return
                                 
            # Create alert (no sent field needed)
            alert = CryptoNewsAlert.objects.create(
                summary=summary,
                sentiment=sentiment,
                sentiment_reasoning=sentiment_reasoning,
                crypto_news_articles=crypto_news_articles
            )
            
            self.stdout.write(f"Created crypto news alert: {summary}")
            self.stdout.write(f"Sentiment: {sentiment}")
            
        except Exception as e:
            self.stderr.write(f"Error generating crypto news alert: {str(e)}")
            logger.error("Failed to generate crypto news alert", exc_info=True) 