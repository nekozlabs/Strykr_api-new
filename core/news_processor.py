import requests
import logging
import json
from datetime import datetime, timedelta
from asgiref.sync import sync_to_async

async def fetch_market_news(api_key, limit=30):
    """
    Fetch recent market news from Financial Modeling Prep API.
    Returns a list of news items with headline, source, date and snippet.
    This function is completely isolated from other functionality.
    """
    if not api_key:
        print("[NEWS INTEGRATION] No API key provided for news fetching")
        logging.error("No API key provided for news fetching")
        return []
        
    # Use the general-latest news endpoint which provides more comprehensive news coverage
    url = f"https://financialmodelingprep.com/stable/news/general-latest?apikey={api_key}&limit={limit}"
    
    try:
        print(f"[NEWS INTEGRATION] Attempting to fetch market news from FMP API")
        # Use sync_to_async to make the requests call non-blocking
        @sync_to_async
        def make_request():
            response = requests.get(url)
            if response.status_code == 200:
                print(f"[NEWS INTEGRATION] Successfully received response from FMP API")
                return response.json()
            else:
                print(f"[NEWS INTEGRATION] Failed to fetch market news: HTTP {response.status_code}")
                logging.error(f"Failed to fetch market news: HTTP {response.status_code}")
                return None
        
        news_data = await make_request()
        if news_data is None:
            return []
            
        if not isinstance(news_data, list):
            print("[NEWS INTEGRATION] No valid news data received from API")
            logging.warning("No valid news data received from API")
            return []
        
        # Filter for recent news (last 24 hours to get more items)
        try:
            cutoff_time = datetime.now() - timedelta(hours=24)
            print(f"[NEWS INTEGRATION] Filtering news since {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}")
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
                    logging.warning(f"Skipping news item due to format error: {str(e)}")
                    continue
            
            # Sort by date (most recent first)
            recent_news.sort(key=lambda x: x.get("date", ""), reverse=True)
            return recent_news[:30]  # Return top 30 most recent news items
            
        except Exception as e:
            logging.error(f"Error processing news data: {str(e)}")
            return []
                    
    except Exception as e:
        logging.error(f"Error fetching market news: {str(e)}")
        return []
