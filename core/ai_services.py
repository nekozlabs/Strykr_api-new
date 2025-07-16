"""
AI-related services for query processing and asset disambiguation.
This module handles AI-powered query intent classification and asset disambiguation.
"""

import json
import logging
from typing import List, Dict, Optional

from .api_utils import client


async def classify_query_intent(query: str) -> dict:
    """
    Ultra-fast, cost-effective intent classification with GPT-4.1 Nano.
    Determines what data is needed for the query to optimize API calls.
    
    Args:
        query: The user's query string
        
    Returns:
        Dictionary containing:
        - type: Query type (simple_price, technical_analysis, etc.)
        - needs_bellwether: Whether bellwether data is needed
        - needs_macro: Whether macro/economic data is needed
        - needs_technicals: Whether technical indicators are needed
        - needs_fundamentals: Whether fundamental data is needed
        - needs_news: Whether news data is needed
        - confidence: Confidence score (0.0-1.0)
    """
    try:
        completion = client.chat.completions.create(
            model="gpt-4.1-nano",  # Optimized for low-latency classification tasks
            messages=[{
                "role": "system", 
                "content": """Classify this financial query and return JSON:
                {
                    "type": "simple_price" | "technical_analysis" | "market_overview" | "crypto_lookup" | "economic_analysis" | "bellwether_analysis",
                    "needs_bellwether": true/false,
                    "needs_macro": true/false,
                    "needs_technicals": true/false,
                    "needs_fundamentals": true/false,
                    "needs_news": true/false,
                    "confidence": 0.0-1.0
                }
                
                Guidelines:
                - simple_price: Just asking for current price, basic info
                - technical_analysis: RSI, EMA, SMA, DEMA, support/resistance, chart patterns
                - market_overview: Market trends, gainers/losers, sector performance
                - crypto_lookup: Cryptocurrency specific queries, tokens, coins
                - economic_analysis: Economic events, calendar, Fed meetings, GDP, etc.
                - bellwether_analysis: Market sentiment, risk-on/risk-off, VIX, DXY, etc.
                
                Set needs_bellwether=true for: market sentiment, risk analysis, overall market questions
                Set needs_macro=true for: economic events, earnings, Fed meetings, calendar
                Set needs_technicals=true for: RSI, moving averages, technical indicators
                Set needs_fundamentals=true for: company info, PE ratio, financials, earnings
                Set needs_news=true for: recent events, news impact, market headlines"""
            }, {
                "role": "user", 
                "content": query
            }],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(completion.choices[0].message.content)
        
        # Log the classification for debugging
        logging.info(f"Query intent classification for '{query}': {result}")
        
        return result
        
    except Exception as e:
        logging.error(f"Error in classify_query_intent: {str(e)}")
        # Return default classification that enables everything (fallback to current behavior)
        return {
            "type": "market_overview",
            "needs_bellwether": True,
            "needs_macro": True,
            "needs_technicals": True,
            "needs_fundamentals": True,
            "needs_news": True,
            "confidence": 0.5
        }


async def smart_asset_disambiguation(found_assets: List[Dict], original_query: str) -> Dict:
    """
    Use GPT-4.1 Nano to score relevance and disambiguate when multiple assets are found.
    
    Args:
        found_assets: List of assets found from search
        original_query: The original user query
        
    Returns:
        Either a single best asset or a disambiguation response
    """
    
    if not found_assets:
        return None
    
    if len(found_assets) == 1:
        return found_assets[0]
    
    # Use GPT-4.1 Nano to score relevance
    try:
        # Prepare asset data for scoring
        assets_for_scoring = []
        for i, asset in enumerate(found_assets[:10]):  # Limit to top 10
            assets_for_scoring.append({
                "id": i,
                "name": asset.get("name", ""),
                "symbol": asset.get("symbol", ""),
                "type": asset.get("type", ""),
                "source": asset.get("source", ""),
                "confidence": asset.get("confidence", 0)
            })
        
        completion = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{
                "role": "system",
                "content": """Score how relevant each asset is to the query (0-1).
                Consider: exact name match, symbol match, asset type, user intent.
                Return JSON: {"scores": [{"asset_id": 0, "score": 0.95, "reason": "exact symbol match"}, ...]}"""
            }, {
                "role": "user",
                "content": f"Query: {original_query}\nAssets: {json.dumps(assets_for_scoring)}"
            }],
            response_format={"type": "json_object"}
        )
        
        scores_data = json.loads(completion.choices[0].message.content)
        scores = scores_data.get("scores", [])
        
        # Sort by score
        scores.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        if scores:
            top_score = scores[0].get("score", 0)
            top_asset_id = scores[0].get("asset_id", 0)
            
            # If top score is high enough and significantly better than second, auto-select
            if top_score > 0.8:
                if len(scores) == 1 or (len(scores) > 1 and top_score - scores[1].get("score", 0) > 0.2):
                    # Return the best matching asset
                    return found_assets[top_asset_id]
        
        # Otherwise, prepare disambiguation response
        return create_disambiguation_response(found_assets[:5], scores)
        
    except Exception as e:
        logging.error(f"Error in smart asset disambiguation: {str(e)}")
        # Fallback to simple disambiguation
        return create_disambiguation_response(found_assets[:5], None)


def create_disambiguation_response(assets: List[Dict], scores: Optional[List[Dict]] = None) -> Dict:
    """
    Create a user-friendly disambiguation response.
    
    Args:
        assets: List of assets to choose from
        scores: Optional relevance scores from GPT-4.1 Nano
        
    Returns:
        Disambiguation response dict
    """
    
    # Create score map if provided
    score_map = {}
    if scores:
        for score_data in scores:
            score_map[score_data.get("asset_id", 0)] = {
                "score": score_data.get("score", 0),
                "reason": score_data.get("reason", "")
            }
    
    options = []
    for i, asset in enumerate(assets):
        option = {
            "id": i + 1,
            "name": asset.get("name", "Unknown"),
            "symbol": asset.get("symbol", "N/A"),
            "type": asset.get("type", "Unknown"),
            "source": asset.get("source", "")
        }
        
        # Add score info if available
        if i in score_map:
            option["relevance_score"] = score_map[i]["score"]
            option["match_reason"] = score_map[i]["reason"]
        
        # Add additional context based on asset type
        if asset.get("type") == "crypto":
            if asset.get("market_cap_rank"):
                option["market_cap_rank"] = asset["market_cap_rank"]
        elif asset.get("type") == "stock":
            if asset.get("exchange"):
                option["exchange"] = asset["exchange"]
        
        options.append(option)
    
    return {
        "type": "disambiguation",
        "message": "I found multiple assets matching your query. Which one are you interested in?",
        "options": options,
        "query_context": {
            "requires_user_selection": True,
            "suggestion": "Please specify by number or provide more details about the asset you're looking for."
        }
    } 