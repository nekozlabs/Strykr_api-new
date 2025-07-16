#!/usr/bin/env python3
"""
Simple API Configuration Viewer for Strykr AI
View configuration without Django dependencies.
"""

import json
from datetime import datetime

CONFIG_FILE = "api_configuration.json"

def load_configuration():
    """Load configuration from JSON file."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Configuration file {CONFIG_FILE} not found!")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON configuration: {e}")
        return {}

def print_summary(config):
    """Print a summary of the configuration."""
    print("=" * 60)
    print("STRYKR AI - API CONFIGURATION SUMMARY")
    print("=" * 60)
    print(f"Configuration Version: {config.get('configuration_version', 'Unknown')}")
    print(f"Organization: {config.get('organization', {}).get('name', 'Unknown')}")
    print(f"Environment: {config.get('organization', {}).get('environment', 'Unknown')}")
    print()
    
    print("CONFIGURED APPLICATIONS:")
    print("-" * 40)
    for app_name, app_config in config.get('applications', {}).items():
        print(f"• {app_config['name']}")
        print(f"  Application ID: {app_name}")
        print(f"  API Key: {app_config['api_key']}")
        print(f"  Type: {app_config['key_type']}")
        print(f"  Daily Limit: {app_config['permissions']['rate_limits']['daily_limit']}")
        print(f"  Monthly Limit: {app_config['permissions']['rate_limits']['monthly_limit']}")
        if app_config.get('allowed_domains'):
            print(f"  Allowed Domains: {', '.join(app_config['allowed_domains'])}")
        print()
    
    # Backtesting specific info
    backtesting_app = config.get('applications', {}).get('backtesting_portal')
    if backtesting_app:
        print("BACKTESTING INTEGRATION DETAILS:")
        print("-" * 40)
        print(f"API Key: {backtesting_app['api_key']}")
        print(f"Base URL: {backtesting_app['endpoints']['base_url']}")
        print("Available Endpoints:")
        for name, endpoint in backtesting_app['endpoints'].items():
            if name != 'base_url':
                print(f"  • {name}: {endpoint}")
        print()
        
        print("Data Sources:")
        for source_name, source_config in backtesting_app.get('data_sources', {}).items():
            print(f"  • {source_name}: {source_config['table']} ({source_config['frequency']})")
        print()

def get_backtesting_config(config):
    """Get and display backtesting-specific configuration."""
    backtesting_app = config.get('applications', {}).get('backtesting_portal')
    if not backtesting_app:
        print("Backtesting portal configuration not found!")
        return
    
    integration_pattern = config.get('integration_patterns', {}).get('backtesting_integration', {})
    
    backtesting_config = {
        'api_key': backtesting_app['api_key'],
        'base_url': backtesting_app['endpoints']['base_url'],
        'endpoints': backtesting_app['endpoints'],
        'data_sources': backtesting_app['data_sources'],
        'integration_pattern': integration_pattern
    }
    
    print("BACKTESTING PORTAL CONFIGURATION:")
    print("=" * 50)
    print(json.dumps(backtesting_config, indent=2))

def generate_simple_python_client():
    """Generate a simple Python client for the backtesting API."""
    config = load_configuration()
    backtesting_app = config.get('applications', {}).get('backtesting_portal')
    
    if not backtesting_app:
        print("Backtesting configuration not found!")
        return
    
    client_code = f'''"""
Simple Strykr AI Backtesting Client
Generated from api_configuration.json
"""

import requests
import pandas as pd
from datetime import datetime, timedelta

class StrykrBacktestingClient:
    def __init__(self):
        self.api_key = "{backtesting_app['api_key']}"
        self.base_url = "{backtesting_app['endpoints']['base_url']}"
        self.headers = {{
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }}
    
    def get_historical_data(self, symbols=None, start_date=None, end_date=None):
        """Get historical market data."""
        if symbols is None:
            symbols = ["AAPL", "GOOGL", "MSFT"]
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        params = {{
            "symbols": ",".join(symbols),
            "start_date": start_date,
            "end_date": end_date
        }}
        
        response = requests.get(
            f"{{self.base_url}}/api/backtesting/historical-data",
            headers=self.headers,
            params=params
        )
        
        return self._handle_response(response)
    
    def get_trading_signals(self, confidence_threshold=0.7):
        """Get trading signals from market screener."""
        params = {{"confidence_threshold": confidence_threshold}}
        
        response = requests.get(
            f"{{self.base_url}}/api/backtesting/trading-signals",
            headers=self.headers,
            params=params
        )
        
        return self._handle_response(response)
    
    def get_portfolio_snapshots(self, limit=100):
        """Get portfolio performance snapshots."""
        params = {{"limit": limit}}
        
        response = requests.get(
            f"{{self.base_url}}/api/backtesting/portfolio-snapshots",
            headers=self.headers,
            params=params
        )
        
        return self._handle_response(response)
    
    def _handle_response(self, response):
        """Handle API response."""
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API Error: {{response.status_code}} - {{response.text}}")
            return None

# Example usage:
if __name__ == "__main__":
    client = StrykrBacktestingClient()
    
    print("Testing Strykr AI Backtesting API...")
    print(f"API Key: {{client.api_key}}")
    print(f"Base URL: {{client.base_url}}")
    
    # Uncomment these lines to test actual API calls:
    # historical_data = client.get_historical_data()
    # print(f"Historical data response: {{historical_data}}")
    
    # signals = client.get_trading_signals()
    # print(f"Trading signals response: {{signals}}")
'''
    
    print("GENERATED PYTHON CLIENT:")
    print("=" * 50)
    print(client_code)

def show_market_picks_access():
    """Show how to access real-time market picks."""
    config = load_configuration()
    main_api = config.get('applications', {}).get('main_api', {})
    
    if not main_api:
        print("Main API configuration not found!")
        return
    
    api_key = main_api.get('api_key')
    base_url = main_api.get('endpoints', {}).get('base_url')
    
    print("🎯 REAL-TIME MARKET PICKS ACCESS")
    print("=" * 50)
    print(f"API Key: {api_key}")
    print(f"Base URL: {base_url}")
    print()
    
    print("📡 MARKET SCREENER ENDPOINTS:")
    print(f"• Get All Picks: {base_url}/api/alerts/market-screener")
    print(f"• Get Specific: {base_url}/api/alerts/market-screener/{{id}}")
    print()
    
    print("🔨 QUICK TEST WITH CURL:")
    print(f'''curl -X GET "{base_url}/api/alerts/market-screener" \\
  -H "X-API-Key: {api_key}" \\
  -H "Content-Type: application/json"''')
    print()
    
    print("📊 MARKET PICKS INCLUDE:")
    print("• Top 5 stocks to go LONG (with confidence scores)")
    print("• Top 5 stocks to go SHORT (with confidence scores)")
    print("• Top cryptocurrencies LONG/SHORT recommendations")
    print("• Market sentiment analysis with numerical scoring")
    print("• AI-generated explanations of market conditions")
    print()
    
    print("🚀 TO GENERATE NEW PICKS:")
    print("python manage.py generate_market_screener")
    print()
    
    print("📖 For detailed examples, see: REAL_TIME_MARKET_PICKS_GUIDE.md")

def main():
    """Main function."""
    import sys
    
    config = load_configuration()
    if not config:
        return
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--summary":
            print_summary(config)
        elif command == "--backtesting-config":
            get_backtesting_config(config)
        elif command == "--generate-client":
            generate_simple_python_client()
        elif command == "--market-picks":
            show_market_picks_access()
        elif command == "--list-apps":
            print("Configured Applications:")
            for app_name, app_config in config.get('applications', {}).items():
                print(f"  • {app_name}: {app_config['name']}")
        else:
            print(f"Unknown command: {command}")
            print("Available commands: --summary, --backtesting-config, --generate-client, --market-picks, --list-apps")
    else:
        print_summary(config)

if __name__ == "__main__":
    main() 