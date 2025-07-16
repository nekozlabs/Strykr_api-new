#!/usr/bin/env python3
"""
API Configuration Manager for Strykr AI
This script helps manage API keys and configuration for different applications.
"""

import json
import os
import sys
import django
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'strykr_api.settings')

try:
    django.setup()
    from core.models import APIKey, Org, create_random_api_key
    DJANGO_AVAILABLE = True
except Exception as e:
    print(f"Django not available: {e}")
    DJANGO_AVAILABLE = False

CONFIG_FILE = "api_configuration.json"

class APIConfigManager:
    """Manages API configuration and key generation for different applications."""
    
    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = config_file
        self.config = self.load_configuration()
    
    def load_configuration(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Configuration file {self.config_file} not found!")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON configuration: {e}")
            return {}
    
    def save_configuration(self):
        """Save configuration back to JSON file."""
        self.config['updated_at'] = datetime.now().isoformat() + 'Z'
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
        print(f"Configuration saved to {self.config_file}")
    
    def get_app_config(self, app_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific application."""
        return self.config.get('applications', {}).get(app_name)
    
    def get_api_key(self, app_name: str) -> Optional[str]:
        """Get API key for a specific application."""
        app_config = self.get_app_config(app_name)
        return app_config.get('api_key') if app_config else None
    
    def list_applications(self) -> List[str]:
        """List all configured applications."""
        return list(self.config.get('applications', {}).keys())
    
    def get_backtesting_config(self) -> Dict[str, Any]:
        """Get specific configuration for backtesting integration."""
        backtesting_app = self.get_app_config('backtesting_portal')
        if not backtesting_app:
            return {}
        
        return {
            'api_key': self.get_api_key('backtesting_portal'),
            'base_url': backtesting_app.get('endpoints', {}).get('base_url', ''),
            'endpoints': backtesting_app.get('endpoints', {}),
            'data_sources': backtesting_app.get('data_sources', {}),
            'integration_pattern': self.config.get('integration_patterns', {}).get('backtesting_integration', {})
        }
    
    def create_database_api_keys(self, org_name: str = "Strykr AI Analytics") -> Dict[str, str]:
        """Create API keys in the database based on configuration."""
        if not DJANGO_AVAILABLE:
            print("Django not available. Cannot create database entries.")
            return {}
        
        # Get or create organization
        org, created = Org.objects.get_or_create(
            name=org_name,
            defaults={'is_verified': True}
        )
        
        if created:
            print(f"Created new organization: {org_name}")
        else:
            print(f"Using existing organization: {org_name}")
        
        created_keys = {}
        
        for app_name, app_config in self.config.get('applications', {}).items():
            # Skip if API key already exists
            existing_key = APIKey.objects.filter(key=app_config['api_key']).first()
            if existing_key:
                print(f"API key for {app_name} already exists in database")
                created_keys[app_name] = app_config['api_key']
                continue
            
            # Create API key in database
            try:
                api_key = APIKey.objects.create(
                    org=org,
                    user_id=f"system_{app_name}",
                    name=app_config['name'],
                    key=app_config['api_key'],
                    client_side_key=app_config.get('client_side_key', create_random_api_key()),
                    allowed_domains=app_config.get('allowed_domains', []),
                    is_revoked=False,
                    is_unlimited=app_config['permissions']['rate_limits'].get('is_unlimited', False),
                    daily_limit=app_config['permissions']['rate_limits'].get('daily_limit', 1000),
                    monthly_limit=app_config['permissions']['rate_limits'].get('monthly_limit', 10000),
                    permission_level=app_config['permissions']['level'],
                    expires_at=None  # No expiration for now
                )
                
                created_keys[app_name] = api_key.key
                print(f"Created API key for {app_name}: {api_key.key}")
                
            except Exception as e:
                print(f"Error creating API key for {app_name}: {e}")
        
        return created_keys
    
    def generate_integration_code(self, app_name: str, language: str = 'python') -> str:
        """Generate integration code for a specific application."""
        app_config = self.get_app_config(app_name)
        if not app_config:
            return f"Application '{app_name}' not found in configuration."
        
        api_key = app_config['api_key']
        base_url = app_config['endpoints']['base_url']
        
        if language.lower() == 'python':
            return self._generate_python_code(app_name, app_config, api_key, base_url)
        elif language.lower() == 'r':
            return self._generate_r_code(app_name, app_config, api_key, base_url)
        elif language.lower() == 'javascript':
            return self._generate_javascript_code(app_name, app_config, api_key, base_url)
        else:
            return f"Language '{language}' not supported yet."
    
    def _generate_python_code(self, app_name: str, app_config: Dict, api_key: str, base_url: str) -> str:
        """Generate Python integration code."""
        if app_name == 'backtesting_portal':
            return f'''"""
Strykr AI - Backtesting Portal Integration
Generated from api_configuration.json
"""

import requests
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta

class StrykrBacktestingAPI:
    def __init__(self):
        self.api_key = "{api_key}"
        self.base_url = "{base_url}"
        self.headers = {{
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }}
    
    def get_historical_data(self, symbols: List[str], start_date: str, end_date: str) -> pd.DataFrame:
        """Get historical market data for backtesting."""
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
        
        if response.status_code == 200:
            data = response.json()
            return pd.DataFrame(data['results'])
        else:
            raise Exception(f"API request failed: {{response.status_code}} - {{response.text}}")
    
    def get_trading_signals(self, confidence_threshold: float = 0.7) -> pd.DataFrame:
        """Get trading signals from market screener."""
        params = {{"confidence_threshold": confidence_threshold}}
        
        response = requests.get(
            f"{{self.base_url}}/api/backtesting/trading-signals",
            headers=self.headers,
            params=params
        )
        
        if response.status_code == 200:
            data = response.json()
            return pd.DataFrame(data['results'])
        else:
            raise Exception(f"API request failed: {{response.status_code}} - {{response.text}}")
    
    def export_data(self, table: str, format: str = "csv") -> str:
        """Export data for external backtesting tools."""
        params = {{"table": table, "format": format}}
        
        response = requests.get(
            f"{{self.base_url}}/api/backtesting/export",
            headers=self.headers,
            params=params
        )
        
        if response.status_code == 200:
            return response.text
        else:
            raise Exception(f"Export failed: {{response.status_code}} - {{response.text}}")

# Example usage:
if __name__ == "__main__":
    api = StrykrBacktestingAPI()
    
    # Get historical data for the last 30 days
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    historical_data = api.get_historical_data(["AAPL", "GOOGL", "MSFT"], start_date, end_date)
    print(f"Retrieved {{len(historical_data)}} historical data points")
    
    # Get trading signals
    signals = api.get_trading_signals()
    print(f"Retrieved {{len(signals)}} trading signals")
'''
        
        else:
            return f'''"""
Strykr AI - {{app_config['name']}} Integration
Generated from api_configuration.json
"""

import requests
import json

class StrykrAPI:
    def __init__(self):
        self.api_key = "{api_key}"
        self.base_url = "{base_url}"
        self.headers = {{
            "X-API-Key": {"Client " if app_config['key_type'] == 'client_side' else ""}{{self.api_key}},
            "Content-Type": "application/json"
        }}
    
    def make_request(self, endpoint: str, data: dict = None):
        """Make a request to the Strykr AI API."""
        url = f"{{self.base_url}}{{endpoint}}"
        
        if data:
            response = requests.post(url, headers=self.headers, json=data)
        else:
            response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"API request failed: {{response.status_code}} - {{response.text}}")

# Example usage:
if __name__ == "__main__":
    api = StrykrAPI()
    result = api.make_request("/api/ai-response", {{"query": "What is the RSI for Bitcoin?"}})
    print(json.dumps(result, indent=2))
'''
    
    def _generate_r_code(self, app_name: str, app_config: Dict, api_key: str, base_url: str) -> str:
        """Generate R integration code."""
        return f'''# Strykr AI - {app_config['name']} Integration (R)
# Generated from api_configuration.json

library(httr)
library(jsonlite)
library(dplyr)

# Configuration
API_KEY <- "{api_key}"
BASE_URL <- "{base_url}"

# Helper function to make API requests
strykr_api_request <- function(endpoint, data = NULL, method = "GET") {{
  url <- paste0(BASE_URL, endpoint)
  
  headers <- add_headers(
    `X-API-Key` = {"paste0('Client ', API_KEY)" if app_config['key_type'] == 'client_side' else "API_KEY"},
    `Content-Type` = "application/json"
  )
  
  if (method == "POST" && !is.null(data)) {{
    response <- POST(url, headers, body = toJSON(data, auto_unbox = TRUE))
  }} else {{
    response <- GET(url, headers)
  }}
  
  if (status_code(response) == 200) {{
    return(content(response, "parsed"))
  }} else {{
    stop(paste("API request failed:", status_code(response), content(response, "text")))
  }}
}}

# Example usage
query_data <- list(query = "What is the market outlook for tech stocks?")
result <- strykr_api_request("/api/ai-response", query_data, "POST")
print(result)
'''
    
    def _generate_javascript_code(self, app_name: str, app_config: Dict, api_key: str, base_url: str) -> str:
        """Generate JavaScript integration code."""
        return f'''/**
 * Strykr AI - {app_config['name']} Integration (JavaScript)
 * Generated from api_configuration.json
 */

class StrykrAPI {{
    constructor() {{
        this.apiKey = "{api_key}";
        this.baseUrl = "{base_url}";
        this.headers = {{
            "X-API-Key": {"Client " if app_config['key_type'] == 'client_side' else ""}${{this.apiKey}},
            "Content-Type": "application/json"
        }};
    }}
    
    async makeRequest(endpoint, data = null, method = "GET") {{
        const url = `${{this.baseUrl}}${{endpoint}}`;
        
        const options = {{
            method: method,
            headers: this.headers
        }};
        
        if (data && method === "POST") {{
            options.body = JSON.stringify(data);
        }}
        
        try {{
            const response = await fetch(url, options);
            
            if (!response.ok) {{
                throw new Error(`API request failed: ${{response.status}} - ${{await response.text()}}`);
            }}
            
            return await response.json();
        }} catch (error) {{
            console.error("API request error:", error);
            throw error;
        }}
    }}
    
    async getAIResponse(query) {{
        return await this.makeRequest("/api/ai-response", {{ query }}, "POST");
    }}
}}

// Example usage
const api = new StrykrAPI();

api.getAIResponse("What are the trending cryptocurrencies?")
    .then(result => console.log(result))
    .catch(error => console.error(error));
'''
    
    def print_summary(self):
        """Print a summary of the configuration."""
        print("=" * 60)
        print("STRYKR AI - API CONFIGURATION SUMMARY")
        print("=" * 60)
        print(f"Configuration Version: {self.config.get('configuration_version', 'Unknown')}")
        print(f"Organization: {self.config.get('organization', {}).get('name', 'Unknown')}")
        print(f"Environment: {self.config.get('organization', {}).get('environment', 'Unknown')}")
        print()
        
        print("CONFIGURED APPLICATIONS:")
        print("-" * 40)
        for app_name, app_config in self.config.get('applications', {}).items():
            print(f"• {app_config['name']}")
            print(f"  API Key: {app_config['api_key']}")
            print(f"  Type: {app_config['key_type']}")
            print(f"  Daily Limit: {app_config['permissions']['rate_limits']['daily_limit']}")
            print(f"  Monthly Limit: {app_config['permissions']['rate_limits']['monthly_limit']}")
            print()
        
        print("BACKTESTING INTEGRATION:")
        print("-" * 40)
        backtesting_config = self.get_backtesting_config()
        print(f"API Key: {backtesting_config['api_key']}")
        print(f"Base URL: {backtesting_config['base_url']}")
        print("Available Endpoints:")
        for name, endpoint in backtesting_config['endpoints'].items():
            if name != 'base_url':
                print(f"  • {name}: {endpoint}")


def main():
    """Main CLI interface for the API Configuration Manager."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Strykr AI API Configuration Manager")
    parser.add_argument("--list-apps", action="store_true", help="List all configured applications")
    parser.add_argument("--get-key", type=str, help="Get API key for specific application")
    parser.add_argument("--create-db-keys", action="store_true", help="Create API keys in database")
    parser.add_argument("--generate-code", type=str, help="Generate integration code for application")
    parser.add_argument("--language", type=str, default="python", help="Language for code generation (python, r, javascript)")
    parser.add_argument("--summary", action="store_true", help="Print configuration summary")
    parser.add_argument("--backtesting-config", action="store_true", help="Print backtesting configuration")
    
    args = parser.parse_args()
    
    manager = APIConfigManager()
    
    if args.list_apps:
        apps = manager.list_applications()
        print("Configured Applications:")
        for app in apps:
            print(f"  • {app}")
    
    elif args.get_key:
        key = manager.get_api_key(args.get_key)
        if key:
            print(f"API Key for {args.get_key}: {key}")
        else:
            print(f"Application '{args.get_key}' not found")
    
    elif args.create_db_keys:
        created_keys = manager.create_database_api_keys()
        print(f"Created {len(created_keys)} API keys in database")
    
    elif args.generate_code:
        code = manager.generate_integration_code(args.generate_code, args.language)
        print(code)
    
    elif args.backtesting_config:
        config = manager.get_backtesting_config()
        print(json.dumps(config, indent=2))
    
    elif args.summary:
        manager.print_summary()
    
    else:
        manager.print_summary()


if __name__ == "__main__":
    main() 