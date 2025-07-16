"""
Shared utilities and constants for the API module.
This module contains common utilities used across different API services.
"""

import httpx
from openai import OpenAI
from django.conf import settings
from ninja.errors import HttpError
from .models import APIKey

# Shared HTTP client for connection pooling
http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(30.0),
    limits=httpx.Limits(max_keepalive_connections=15, max_connections=50)
)

# OpenAI client
client = OpenAI(timeout=30.0)

# Month as number mapping
month_numbers = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


async def validate_api_key(api_key, domain, is_client_side_key, user=None):
    """
    Validate API key for authentication.
    This function is needed because request.user is an instance of AnonymousUser,
    which is not a valid user object.
    
    Args:
        api_key: The API key to validate
        domain: The domain making the request
        is_client_side_key: Whether this is a client-side key
        user: Optional user object
        
    Returns:
        APIKey object if valid
        
    Raises:
        HttpError: If API key is invalid or not authorized
    """
    try:
        if is_client_side_key:
            api_key_obj = await APIKey.objects.aget(
                client_side_key=api_key,
                allowed_domains__contains=[domain],
            )
        else:
            api_key_obj = await APIKey.objects.aget(
                key=api_key
            )
        if not api_key_obj.is_valid():
            raise HttpError(403, "Not authorized")
        return api_key_obj
    except APIKey.DoesNotExist:
        raise HttpError(403, "Not authorized") 


# Additional imports for JSON response utilities
import json
import logging
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from django.utils import timezone
from django.http import JsonResponse
from django.core.serializers.json import DjangoJSONEncoder


class TimestampJSONEncoder(DjangoJSONEncoder):
    """
    Custom JSON encoder that automatically converts timestamps to real timestamps.
    Handles various timestamp formats and converts them to ISO format with timezone info.
    """
    
    def default(self, obj):
        if isinstance(obj, datetime):
            # Convert to real timestamp with timezone info
            if obj.tzinfo is None:
                obj = timezone.make_aware(obj)
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class JSONResponseFormatter:
    """
    Handles automatic timestamp switching and JSON response formatting
    for different endpoint configurations.
    """
    
    @staticmethod
    def format_timestamps_recursive(data: Any, use_real_timestamps: bool = True) -> Any:
        """
        Recursively format timestamps in nested data structures.
        
        Args:
            data: The data to process (dict, list, or primitive)
            use_real_timestamps: Whether to convert to real timestamps
        
        Returns:
            Data with formatted timestamps
        """
        if isinstance(data, dict):
            formatted_data = {}
            for key, value in data.items():
                # Check if this is a timestamp field
                if any(ts_field in key.lower() for ts_field in ['date', 'timestamp', 'time', 'created', 'updated']):
                    if isinstance(value, str):
                        try:
                            # Try to parse as datetime string
                            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                            if use_real_timestamps:
                                # Convert to current timezone and format
                                if dt.tzinfo is None:
                                    dt = timezone.make_aware(dt)
                                formatted_data[key] = dt.isoformat()
                            else:
                                formatted_data[key] = value
                        except (ValueError, AttributeError):
                            formatted_data[key] = value
                    elif isinstance(value, datetime):
                        if use_real_timestamps:
                            if value.tzinfo is None:
                                value = timezone.make_aware(value)
                            formatted_data[key] = value.isoformat()
                        else:
                            formatted_data[key] = value
                    else:
                        formatted_data[key] = value
                else:
                    # Recursively process nested data
                    formatted_data[key] = JSONResponseFormatter.format_timestamps_recursive(
                        value, use_real_timestamps
                    )
            return formatted_data
        elif isinstance(data, list):
            return [
                JSONResponseFormatter.format_timestamps_recursive(item, use_real_timestamps) 
                for item in data
            ]
        else:
            return data
    
    @staticmethod
    def create_json_response(
        data: Dict[str, Any], 
        api_key_config: Optional[Dict] = None,
        auto_timestamp_switch: bool = True,
        status: int = 200
    ) -> JsonResponse:
        """
        Create a JSON response with automatic timestamp switching.
        
        Args:
            data: The response data
            api_key_config: API key configuration from the JSON config
            auto_timestamp_switch: Whether to automatically switch timestamps
            status: HTTP status code
        
        Returns:
            JsonResponse with properly formatted timestamps
        """
        # Determine if we should use real timestamps based on configuration
        use_real_timestamps = True
        
        if api_key_config and auto_timestamp_switch:
            # Check if this is a backtesting or historical data endpoint
            permissions = api_key_config.get('permissions', {})
            endpoints = permissions.get('endpoints', [])
            
            # For backtesting endpoints, we might want to preserve historical timestamps
            if any('/backtesting/' in endpoint for endpoint in endpoints):
                use_real_timestamps = False
            
            # For real-time market picks, always use real timestamps
            data_access = api_key_config.get('data_access', {})
            if data_access.get('real_time_market_picks', False):
                use_real_timestamps = True
        
        # Add metadata about timestamp handling
        formatted_data = {
            'data': JSONResponseFormatter.format_timestamps_recursive(data, use_real_timestamps),
            'metadata': {
                'timestamp_format': 'real_time' if use_real_timestamps else 'preserved',
                'response_generated_at': timezone.now().isoformat(),
                'timezone': str(timezone.get_current_timezone())
            }
        }
        
        return JsonResponse(
            formatted_data,
            encoder=TimestampJSONEncoder,
            safe=False,
            status=status
        )


def get_api_key_config(api_key: str) -> Optional[Dict]:
    """
    Retrieve API key configuration from the configuration file.
    
    Args:
        api_key: The API key to look up
    
    Returns:
        Configuration dict for the API key, or None if not found
    """
    try:
        with open('api_configuration.json', 'r') as f:
            config = json.load(f)
            
        applications = config.get('applications', {})
        
        for app_name, app_config in applications.items():
            if app_config.get('api_key') == api_key:
                return app_config
                
        return None
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading API configuration: {e}")
        return None


def enhance_json_endpoint_response(
    endpoint_path: str,
    response_data: Dict[str, Any],
    api_key: str,
    request_timestamp: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Enhance JSON endpoint responses with automatic timestamp switching
    and additional metadata based on the endpoint configuration.
    
    Args:
        endpoint_path: The API endpoint path
        response_data: The original response data
        api_key: The API key used for the request
        request_timestamp: When the request was made
    
    Returns:
        Enhanced response data with proper timestamp handling
    """
    api_config = get_api_key_config(api_key)
    
    # Enhanced response structure
    enhanced_response = {
        'success': True,
        'data': response_data,
        'metadata': {
            'endpoint': endpoint_path,
            'request_timestamp': (request_timestamp or timezone.now()).isoformat(),
            'api_version': '1.0',
            'timestamp_handling': 'automatic'
        }
    }
    
    # Add configuration-specific enhancements
    if api_config:
        enhanced_response['metadata']['application'] = api_config.get('name', 'Unknown')
        enhanced_response['metadata']['access_level'] = api_config.get('permissions', {}).get('level', 'unknown')
        
        # Automatic timestamp switching based on endpoint and configuration
        if 'backtesting' in endpoint_path:
            enhanced_response['metadata']['timestamp_mode'] = 'historical_preserved'
        elif 'real-time' in endpoint_path or 'market-screener' in endpoint_path:
            enhanced_response['metadata']['timestamp_mode'] = 'real_time_converted'
            # Convert all timestamps to current time context
            enhanced_response['data'] = JSONResponseFormatter.format_timestamps_recursive(
                response_data, use_real_timestamps=True
            )
        else:
            enhanced_response['metadata']['timestamp_mode'] = 'context_aware'
    
    return enhanced_response 