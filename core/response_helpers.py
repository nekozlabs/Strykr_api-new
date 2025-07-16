import logging

def get_helpful_fallback(query):
    """Generate a helpful fallback response when data retrieval fails"""
    query_lower = query.lower()
    
    # Base response
    response = "I don't have complete data to answer your question fully, but I can still help!\n\n"
    
    # Check for query types and add specific guidance
    if any(term in query_lower for term in ["economic", "calendar", "events", "news", "macro"]):
        response += "For economic calendar information:\n"
        response += "- Try specifying a time period like 'this week' or 'next month'\n"
        response += "- For more precise results, mention 'high impact events' or specific countries\n"
        response += "- Major economic events typically include central bank decisions, GDP releases, and employment reports\n\n"
        
    elif any(term in query_lower for term in ["short", "long", "buy", "sell", "entry", "exit", "price"]):
        response += "For entry/exit point questions:\n"
        response += "- Check if you're using a valid ticker symbol (e.g., BTC or ETH instead of Bitcoin/Ethereum)\n"
        response += "- Consider checking technical indicators like RSI, SMA or important support/resistance levels\n"
        response += "- Remember that effective entry points often align with key technical levels\n\n"
    
    elif any(term in query_lower for term in ["stop", "loss", "risk", "position", "sizing"]):
        response += "For risk management questions:\n"
        response += "- A common practice is setting stop losses at recent support/resistance levels\n"
        response += "- Consider the asset's volatility when determining stop loss distance\n" 
        response += "- Many traders use a position size of 1-2% of their total capital per trade\n\n"
    
    elif any(term in query_lower for term in ["technical", "indicator", "rsi", "ema", "sma", "dema"]):
        response += "For technical indicator questions:\n"
        response += "- Ensure you're using the correct ticker symbol format (e.g., 'AAPL' not 'Apple')\n"
        response += "- Try both with and without currency modifiers (ETH vs ETHUSD)\n"
        response += "- For cryptocurrency tickers, try using the format BTCUSD, ETHUSD, etc.\n\n"
        
    # Add general tips
    response += "General tips for better results:\n"
    response += "- Be specific about timeframes (this week vs next month)\n"
    response += "- Use standard ticker symbols (AAPL vs Apple)\n"
    response += "- For cryptocurrencies, try both formats (ETH or ETHUSD)\n\n"
    
    response += "Feel free to try your question again with these adjustments!"
    
    return response
