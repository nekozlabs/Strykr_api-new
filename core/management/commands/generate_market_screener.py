import logging
import requests
import os
import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from openai import OpenAI

from core.models import MarketScreenerResult

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Generate market screener recommendations for top stocks to long and short.
    
    This command analyzes market data to identify the strongest stocks to go long
    on and the weakest stocks to short. It uses technical and fundamental factors 
    to rank stocks by confidence score.
    
    Note: Cryptocurrency screening is not yet implemented in this version.
    Implementation is pending decision on which cryptocurrency data API to use.
    
    It can operate in the following modes:
    - Normal mode: Fetch data from APIs and save screener to the database
    - Dry-run mode: Display screener results without saving to database
    
    In dry-run mode, data can be sourced from:
    - FMP API directly (when USE_MOCK_DATA_FOR_DRYRUN=false)
    - Mock data (when USE_MOCK_DATA_FOR_DRYRUN=true or --mock-data flag is used)
    
    Output format includes:
    - List of top 5 stocks to long (with confidence scores)
    - List of top 5 stocks to short (with confidence scores)
    - Brief explanation of the market sentiment
    """

    help = 'Generate market screener for top stocks to long and short'

    def add_arguments(self, parser):
        """Define command line arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Test without creating screener in database'
        )
        parser.add_argument(
            '--mock-data',
            action='store_true',
            help='Use mock data instead of API data (useful for testing)'
        )
    
    def fetch_crypto_data_from_fmp(self):
        api_key = os.environ.get('FMP_API_KEY')
        if not api_key:
            raise ValueError("FMP_API_KEY not found in environment variables")
        
        def fetch_cryptocurrencies():
            url = f'https://financialmodelingprep.com/api/v3/symbol/available-cryptocurrencies?apikey={api_key}'
            response = requests.get(url)
            print(f"Total how many crypto: {len(response.json())}")
            if response.status_code != 200:
                print(f"Error fetching cryptocurrency list: {response.status_code}")
                return []
            return response.json()

        def fetch_crypto_quotes():
            url = f'https://financialmodelingprep.com/api/v3/quotes/crypto?apikey={api_key}'
            response = requests.get(url)
            if response.status_code != 200:
                print(f"Error fetching cryptocurrency quotes: {response.status_code}")
                return []
            return response.json()

        cryptocurrencies = fetch_cryptocurrencies()
        if not cryptocurrencies:
            print("No cryptocurrencies found.")
            return

        # Fetch real-time quotes
        quotes = fetch_crypto_quotes()
        if not quotes:
            print("No cryptocurrency quotes found.")
            return

        # Filter for USD pairs
        usd_quotes = [quote for quote in quotes if quote['symbol'].endswith('USD')]
        print(f"Total USD quotes: {len(usd_quotes)}")

        # Separate into "long" and "short" based on percentage change
        top_long = sorted(
            [quote for quote in usd_quotes if quote['changesPercentage'] > 0],
            key=lambda x: x['changesPercentage'],
            reverse=True
        )[:5]

        top_short = sorted(
            [quote for quote in usd_quotes if quote['changesPercentage'] < 0],
            key=lambda x: x['changesPercentage']
        )[:5]

        crypto_data = {
            "top_crypto_long": top_long,
            "top_crypto_short": top_short,
        }

        return crypto_data 


    def fetch_stock_data_from_fmp(self):
        """
        Fetch stock performance data from Financial Model Prep API.
        
        Returns:
            dict: Stock data organized by ticker symbol
            
        Raises:
            ValueError: If API key is not found
            Exception: For any API request failures or parsing errors
        """
        api_key = os.environ.get('FMP_API_KEY')
        if not api_key:
            raise ValueError("FMP_API_KEY not found in environment variables")

        # Fetch S&P 500 constituents
        sp500_url = f"https://financialmodelingprep.com/api/v3/sp500_constituent?apikey={api_key}"
        self.stdout.write(f"Fetching S&P 500 constituents")

        try:
            response = requests.get(sp500_url, timeout=15)
            if response.status_code != 200:
                self.stdout.write(f"API returned status code {response.status_code}: {response.text}")
                return None

            constituents = response.json()
            tickers = [stock['symbol'] for stock in constituents[:50]]  # Limit to first 50 for performance

            # Fetch quote data for all symbols
            if not tickers:
                self.stdout.write("No tickers found in S&P 500 constituents")
                return None

            tickers_str = ','.join(tickers)
            quote_url = f"https://financialmodelingprep.com/api/v3/quote/{tickers_str}?apikey={api_key}"
            self.stdout.write(f"Fetching quotes for {len(tickers)} stocks")

            response = requests.get(quote_url, timeout=15)
            if response.status_code != 200:
                self.stdout.write(f"API returned status code {response.status_code}: {response.text}")
                return None

            quotes = response.json()

            # Format the data
            stock_data = {}
            for quote in quotes:
                if isinstance(quote, dict):
                    ticker = quote.get('symbol')
                    if ticker:
                        # Calculate performance metrics
                        price = quote.get('price', 0)
                        change = quote.get('change', 0)
                        change_percent = quote.get('changesPercentage', 0)

                        # Calculate a simple strength score (-100 to 100)
                        volume = quote.get('volume', 0)
                        avg_volume = quote.get('avgVolume', 1)  # Avoid div by zero
                        volume_ratio = volume / avg_volume if avg_volume else 1

                        # Score is based on price change and abnormal volume
                        strength_score = change_percent * (0.7 + 0.3 * min(volume_ratio, 3))

                        # Clip to range -100 to 100
                        strength_score = max(-100, min(100, strength_score))

                        stock_data[ticker] = {
                            'ticker': ticker,
                            'company_name': quote.get('name', ''),
                            'price': price,
                            'change': change,
                            'change_percent': change_percent,
                            'volume': volume,
                            'volume_ratio': volume_ratio,
                            'strength_score': round(strength_score, 2),
                            'sector': '',  # Would need another API call to get sector
                            'market_cap': quote.get('marketCap', 0)
                        }

            return stock_data

        except Exception as e:
            self.stdout.write(f"Error fetching stock data: {str(e)}")
            return None

    def get_stock_data(self, dry_run=False):
        """
        Get stock data from API or database.
        
        Args:
            dry_run (bool): Whether this is a dry run
            
        Returns:
            dict: Stock data organized by ticker
            
        Raises:
            ValueError: If unable to get stock data
        """
        # In a real implementation, we might get this from a database
        # For now, we'll always fetch from the API
        stock_data = self.fetch_stock_data_from_fmp()

        if not stock_data:
            raise ValueError("Unable to get stock data")

        return stock_data

    def generate_mock_crypto_data(self):
        """
        Generate mock cryptocurrency data for testing.
        
        Returns:
            dict: Mock crypto data organized by symbol
        """
        # This is a placeholder that can be expanded later
        crypto_symbols = ["BTC", "ETH", "SOL", "ADA", "DOT", "AVAX", "MATIC", "LINK", "XRP", "DOGE"]

        crypto_data = {}
        for symbol in crypto_symbols:
            # Generate random performance data
            change_percent = random.uniform(-10, 10)  # Cryptos often have higher volatility
            price = random.uniform(0.1, 50000)  # Wide price range for different cryptos

            # More extreme for testing
            strength_score = random.uniform(-100, 100)

            crypto_data[symbol] = {
                'symbol': symbol,
                'name': f"{symbol}-USD",
                'price': round(price, 2),
                'change_percent': round(change_percent, 2),
                'volume': random.randint(1000000, 10000000000),
                'strength_score': round(strength_score, 2),
                'market_cap': random.randint(10000000, 500000000000)
            }

        return crypto_data

    def generate_mock_stock_data(self):
        """
        Generate mock stock data for testing.
        
        Returns:
            dict: Mock stock data organized by ticker
        """
        tickers = [
            "AAPL", "MSFT", "AMZN", "GOOGL", "META", 
            "TSLA", "NVDA", "JPM", "V", "UNH",
            "WMT", "PG", "XOM", "JNJ", "BAC"
        ]

        sectors = [
            "Technology", "Healthcare", "Financial Services", 
            "Consumer Cyclical", "Energy", "Industrials"
        ]

        stock_data = {}
        for ticker in tickers:
            # Generate random performance data
            change_percent = random.uniform(-5, 5)
            price = random.uniform(50, 500)
            change = price * (change_percent / 100)

            # More extreme for testing
            strength_score = random.uniform(-100, 100)

            stock_data[ticker] = {
                'ticker': ticker,
                'company_name': f"{ticker} Corporation",
                'price': round(price, 2),
                'change': round(change, 2),
                'change_percent': round(change_percent, 2),
                'volume': random.randint(1000000, 10000000),
                'volume_ratio': random.uniform(0.5, 2.5),
                'strength_score': round(strength_score, 2),
                'sector': random.choice(sectors),
                'market_cap': random.randint(1000000000, 2000000000000)
            }

        return stock_data

    def generate_screener(self, stock_data, crypto_data=None):
        """
        Generate stock screener from stock data.
        
        Args:
            stock_data (dict): Stock data organized by ticker
            crypto_data (dict, optional): Crypto data organized by symbol
            
        Returns:
            dict: Screener data with top long and short recommendations
        """
        # Sort stocks by strength score
        stocks = list(stock_data.values())
        stocks.sort(key=lambda x: x['strength_score'], reverse=True)

        # Get top 5 to long (highest scores)
        top_long = stocks[:5] if len(stocks) >= 5 else stocks

        # Get top 5 to short (lowest scores)
        stocks.sort(key=lambda x: x['strength_score'])
        top_short = stocks[:5] if len(stocks) >= 5 else stocks

        # TODO: Process crypto data when API is selected
        crypto_data = self.fetch_crypto_data_from_fmp()
        crypto_top_long = crypto_data["top_crypto_long"]
        crypto_top_short = crypto_data["top_crypto_short"]


        # Calculate market sentiment score (-100 to 100) - for stocks.
        if stocks:
            sentiment_score = sum(stock['strength_score'] for stock in stocks) / len(stocks)
        else:
            sentiment_score = 0

        if sentiment_score > 30:
            sentiment = "Bullish"
        elif sentiment_score > 10:
            sentiment = "Mildly Bullish"
        elif sentiment_score > -10:
            sentiment = "Neutral"
        elif sentiment_score > -30:
            sentiment = "Mildly Bearish"
        else:
            sentiment = "Bearish"        

        # Format the screener data
        screener_data = {
            'timestamp': timezone.now().isoformat(),
            'market_sentiment_score': round(sentiment_score, 2),
            'market_sentiment': sentiment,
            'top_long': [
                {
                    'ticker': stock['ticker'],
                    'company_name': stock['company_name'],
                    'confidence_score': min(100, abs(stock['strength_score'])),
                    'price': stock['price'],
                    'change_percent': stock['change_percent']
                } for stock in top_long
            ],
            'top_short': [
                {
                    'ticker': stock['ticker'],
                    'company_name': stock['company_name'],
                    'confidence_score': min(100, abs(stock['strength_score'])),
                    'price': stock['price'],
                    'change_percent': stock['change_percent']
                } for stock in top_short
            ],
            # TODO: Add these when crypto API is integrated
            'top_crypto_long': [
                {
                    'symbol': crypto['symbol'],
                    'name': crypto['name'],
                    'price': crypto['price'],
                    'market_cap': crypto['marketCap'],
                    'change_percent': crypto['changesPercentage'],
                    # 'average_volume': crypto['avgVolume'],
                } for crypto in crypto_top_long
            ],
            'top_crypto_short': [
                {
                    'symbol': crypto['symbol'],
                    'name': crypto['name'],
                    'price': crypto['price'],
                    'market_cap': crypto['marketCap'],
                    'change_percent': crypto['changesPercentage'],
                    # 'average_volume': crypto['avgVolume'],
                } for crypto in crypto_top_short
            ],
        }

        return screener_data

    def generate_gpt_explanation(self, screener_data, client):
        """
        Generate explanation of market sentiment using GPT-4.
        
        Args:
            screener_data (dict): Screener data with top long and short recommendations
            client: OpenAI client
            
        Returns:
            str: Explanation of market sentiment
        """
        top_long_str = []
        for stock in screener_data['top_long']:
            top_long_str.append(f"{stock['ticker']} ({stock['company_name']}): {stock['change_percent']}% today, confidence score {stock['confidence_score']}")

        top_short_str = []
        for stock in screener_data['top_short']:
            top_short_str.append(f"{stock['ticker']} ({stock['company_name']}): {stock['change_percent']}% today, confidence score {stock['confidence_score']}")

        prompt = f"""Market sentiment: {screener_data['market_sentiment']} (score: {screener_data['market_sentiment_score']})
        Top stocks to LONG:
        {chr(10).join(top_long_str)}
        Top stocks to SHORT:
        {chr(10).join(top_short_str)}"""

        try:
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": """You are a market analyst expert. Analyze the market screener results and provide a brief explanation (around 100 words) of the market sentiment and why these stocks were recommended for long and short positions. 
                    
                    Focus on:
                    - General market sentiment
                    - Any patterns in the recommended stocks (sectors, market caps, etc.)
                    - Brief rationale for the recommendations
                    
                    Your response should be direct and informative without any introduction or conclusion."""},
                    {"role": "user", "content": f"Analyze these market screener results:\n\n{prompt}"}
                ]
            )

            explanation = response.choices[0].message.content.strip()

            # Fall back to a generic explanation if the LLM gives us something weird
            if not explanation or len(explanation) < 10:
                explanation = self.generate_fallback_explanation(screener_data)

            return explanation
        except Exception as e:
            self.stdout.write(f"Error generating GPT explanation: {str(e)}")
            return self.generate_fallback_explanation(screener_data)

    def generate_fallback_explanation(self, screener_data):
        """
        Generate a fallback explanation when GPT fails.
        
        Args:
            screener_data (dict): Screener data
            
        Returns:
            str: Fallback explanation
        """
        sentiment = screener_data['market_sentiment']
        score = screener_data['market_sentiment_score']

        top_long_tickers = ", ".join([stock['ticker'] for stock in screener_data['top_long']])
        top_short_tickers = ", ".join([stock['ticker'] for stock in screener_data['top_short']])

        return f"Market sentiment is currently {sentiment} with a score of {score}. Top stocks to consider for long positions include {top_long_tickers}, while potential short candidates include {top_short_tickers}. This analysis is based on technical factors including price momentum and volume patterns."

    def handle(self, *args, **options):
        """
        Execute the command logic.
        
        Args:
            *args: Variable length argument list
            **options: Arbitrary keyword arguments (includes command line args)
            
        Returns:
            None
        """
        try:
            client = OpenAI(timeout=30.0)  # Add 30-second timeout

            # Determine if we should use mock data
            use_mock = options.get('mock_data', False) or (options['dry_run'] and os.environ.get('USE_MOCK_DATA_FOR_DRYRUN', 'true').lower() == 'true')

            # Get stock data
            try:
                self.stdout.write("Fetching stock data...")
                if use_mock:
                    self.stdout.write("Using mock stock data")
                    stock_data = self.generate_mock_stock_data()
                else:
                    stock_data = self.get_stock_data(options['dry_run'])
                self.stdout.write(f"Got data for {len(stock_data)} stocks")
            except Exception as e:
                import traceback
                self.stdout.write(self.style.ERROR(f"Error fetching stock data: {str(e)}"))
                self.stdout.write(self.style.ERROR(traceback.format_exc()))
                return

            # TODO: Get crypto data when API is selected
            # Placeholder for future crypto data integration
            crypto_data = {}
            # try:
            #     self.stdout.write("Fetching cryptocurrency data...")
            #     if use_mock:
            #         self.stdout.write("Using mock crypto data")
            #         crypto_data = self.generate_mock_crypto_data()
            #     else:
            #         crypto_data = self.fetch_crypto_data_from_api()
            #     self.stdout.write(f"Got data for {len(crypto_data)} cryptocurrencies")
            # except NotImplementedError:
            #     self.stdout.write("Crypto data fetching not yet implemented - using empty data")
            # except Exception as e:
            #     self.stdout.write(self.style.WARNING(f"Error fetching crypto data: {str(e)}"))
            #     self.stdout.write("Continuing with empty crypto data")

            # Generate screener
            screener_data = self.generate_screener(stock_data)

            # Generate explanation
            explanation = self.generate_gpt_explanation(screener_data, client)
            screener_data['explanation'] = explanation

            # If dry run, just print the screener
            if options['dry_run']:
                self.stdout.write(self.style.SUCCESS(
                    f"Dry run - Market Screener Results\n"
                    f"Market Sentiment: {screener_data['market_sentiment']} (score: {screener_data['market_sentiment_score']})\n\n"
                    f"Top stocks to LONG:\n"
                ))

                for stock in screener_data['top_long']:
                    self.stdout.write(f"  {stock['ticker']} ({stock['company_name']}): {stock['confidence_score']}% confidence")

                self.stdout.write("\nTop stocks to SHORT:")
                for stock in screener_data['top_short']:
                    self.stdout.write(f"  {stock['ticker']} ({stock['company_name']}): {stock['confidence_score']}% confidence")

                # TODO: Add dry run crypto output when implemented
                # if crypto_data:
                #     self.stdout.write("\nTop cryptocurrencies to LONG:")
                #     for crypto in crypto_top_long:
                #         self.stdout.write(f"  {crypto['symbol']} ({crypto['name']}): {crypto['confidence_score']}% confidence")
                #     
                #     self.stdout.write("\nTop cryptocurrencies to SHORT:")
                #     for crypto in crypto_top_short:
                #         self.stdout.write(f"  {crypto['symbol']} ({crypto['name']}): {crypto['confidence_score']}% confidence")

                self.stdout.write(f"\nExplanation:\n{explanation}")
                return

            # Create screener in database
            try:
                today = timezone.now().date()
                screener = MarketScreenerResult.objects.create(
                    analysis_date=today,
                    top_stocks_long=screener_data['top_long'],
                    top_stocks_short=screener_data['top_short'],
                    top_cryptos_long=screener_data['top_crypto_long'],  # Crypto screening pending API selection decision
                    top_cryptos_short=screener_data['top_crypto_short'],  # Crypto screening pending API selection decision
                    market_sentiment_score = screener_data['market_sentiment_score'],
                    market_sentiment = screener_data['market_sentiment'],
                    explanation = screener_data['explanation']

                )

                self.stdout.write(f"Successfully created market screener with ID {screener.id}")
                logger.info(f"Market screener created - ID: {screener.id}, Sentiment: {screener_data['market_sentiment']}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error creating market screener: {str(e)}"))
                logger.error("Failed to create market screener", exc_info=True)

        except Exception as e:
            self.stderr.write(f"Error generating market screener: {str(e)}")
            logger.error("Failed to generate market screener", exc_info=True) 