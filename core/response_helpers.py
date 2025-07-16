"""
Response Helper Decorators for Automatic Timestamp Switching
Provides decorators and middleware for JSON endpoints to automatically handle timestamps
"""

import functools
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional
from django.http import JsonResponse, HttpRequest
from django.utils import timezone
from .api_utils import (
    JSONResponseFormatter, 
    get_api_key_config, 
    enhance_json_endpoint_response,
    TimestampJSONEncoder
)


def auto_timestamp_json_response(
    enable_auto_switching: bool = True,
    force_real_timestamps: bool = False
):
    """
    Decorator that automatically switches timestamps in JSON responses based on 
    API configuration and endpoint context.
    
    Args:
        enable_auto_switching: Whether to enable automatic timestamp switching
        force_real_timestamps: Force all timestamps to be real-time (overrides auto logic)
    
    Usage:
        @auto_timestamp_json_response()
        def my_endpoint(request):
            return {"data": "value", "timestamp": "2024-01-01T12:00:00Z"}
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            # Get the original response
            response = view_func(request, *args, **kwargs)
            
            # Only process JSON responses
            if not isinstance(response, (JsonResponse, dict)):
                return response
            
            # Extract API key from request
            api_key = request.headers.get("X-API-KEY", "").replace("Client ", "", 1)
            endpoint_path = request.path
            
            # Get API configuration
            api_config = get_api_key_config(api_key) if api_key else None
            
            # Handle dict responses (convert to JsonResponse)
            if isinstance(response, dict):
                # Enhance the response with automatic timestamp switching
                if enable_auto_switching:
                    enhanced_data = enhance_json_endpoint_response(
                        endpoint_path=endpoint_path,
                        response_data=response,
                        api_key=api_key,
                        request_timestamp=timezone.now()
                    )
                else:
                    enhanced_data = response
                
                # Create JSON response with proper encoding
                return JSONResponseFormatter.create_json_response(
                    data=enhanced_data,
                    api_key_config=api_config,
                    auto_timestamp_switch=enable_auto_switching and not force_real_timestamps
                )
            
            return response
        return wrapper
    return decorator


def json_endpoint_with_real_timestamps(view_func: Callable) -> Callable:
    """
    Decorator that forces all JSON endpoints to use real timestamps.
    This is useful for real-time market data endpoints.
    
    Usage:
        @json_endpoint_with_real_timestamps
        def market_screener_endpoint(request):
            return {"picks": [...], "generated_at": "2024-01-01T12:00:00Z"}
    """
    return auto_timestamp_json_response(
        enable_auto_switching=True,
        force_real_timestamps=True
    )(view_func)


def preserve_historical_timestamps(view_func: Callable) -> Callable:
    """
    Decorator that preserves historical timestamps for backtesting endpoints.
    
    Usage:
        @preserve_historical_timestamps
        def backtesting_data_endpoint(request):
            return {"historical_data": [...], "backtest_date": "2023-01-01T12:00:00Z"}
    """
    return auto_timestamp_json_response(
        enable_auto_switching=False
    )(view_func)


class JSONTimestampMiddleware:
    """
    Middleware that automatically handles timestamp conversion for all JSON responses
    based on the API configuration and endpoint type.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Only process JSON responses
        content_type = getattr(response, 'content_type', '') or response.get('Content-Type', '') if hasattr(response, 'get') else ''
        if hasattr(response, 'content') and content_type.startswith('application/json'):
            
            try:
                # Parse the JSON content
                content = json.loads(response.content.decode('utf-8'))
                
                # Get API key and configuration
                api_key = request.headers.get("X-API-KEY", "").replace("Client ", "", 1)
                api_config = get_api_key_config(api_key) if api_key else None
                
                # Apply automatic timestamp switching
                if api_config and self._should_auto_switch_timestamps(request.path, api_config):
                    enhanced_content = enhance_json_endpoint_response(
                        endpoint_path=request.path,
                        response_data=content,
                        api_key=api_key,
                        request_timestamp=timezone.now()
                    )
                    
                    # Update the response content
                    response.content = json.dumps(
                        enhanced_content, 
                        cls=TimestampJSONEncoder
                    ).encode('utf-8')
                    
                    # Add metadata headers
                    response['X-Timestamp-Mode'] = enhanced_content.get('metadata', {}).get('timestamp_mode', 'default')
                    response['X-Response-Enhanced'] = 'true'
                
            except (json.JSONDecodeError, AttributeError) as e:
                logging.warning(f"Could not process JSON response for timestamp switching: {e}")
        
        return response
    
    def _should_auto_switch_timestamps(self, endpoint_path: str, api_config: Dict) -> bool:
        """
        Determine if automatic timestamp switching should be applied based on 
        endpoint path and API configuration.
        """
        # Check if this endpoint supports real-time data
        data_access = api_config.get('data_access', {})
        
        # Real-time endpoints should use real timestamps
        if any(keyword in endpoint_path for keyword in ['market-screener', 'alerts', 'real-time']):
            return data_access.get('real_time_market_picks', False)
        
        # Backtesting endpoints should preserve historical timestamps
        if 'backtesting' in endpoint_path:
            return False
        
        # Default behavior based on API key type
        return api_config.get('key_type') == 'client_side'


def format_response_timestamps(data: Dict[str, Any], mode: str = 'auto') -> Dict[str, Any]:
    """
    Utility function to format timestamps in response data.
    
    Args:
        data: The response data to format
        mode: Timestamp formatting mode ('auto', 'real', 'preserve')
    
    Returns:
        Data with formatted timestamps
    """
    if mode == 'real':
        return JSONResponseFormatter.format_timestamps_recursive(data, use_real_timestamps=True)
    elif mode == 'preserve':
        return JSONResponseFormatter.format_timestamps_recursive(data, use_real_timestamps=False)
    else:  # auto mode
        # Determine automatically based on data context
        has_historical_markers = any(
            key in str(data).lower() 
            for key in ['historical', 'backtest', 'past', 'archive']
        )
        use_real = not has_historical_markers
        return JSONResponseFormatter.format_timestamps_recursive(data, use_real_timestamps=use_real)


# Convenience function for manual response enhancement
def create_enhanced_json_response(
    data: Dict[str, Any], 
    request: HttpRequest,
    timestamp_mode: str = 'auto'
) -> JsonResponse:
    """
    Create an enhanced JSON response with automatic timestamp handling.
    
    Args:
        data: Response data
        request: HTTP request object
        timestamp_mode: How to handle timestamps ('auto', 'real', 'preserve')
    
    Returns:
        Enhanced JsonResponse with proper timestamp formatting
    """
    api_key = request.headers.get("X-API-KEY", "").replace("Client ", "", 1)
    api_config = get_api_key_config(api_key) if api_key else None
    
    # Format timestamps based on mode
    formatted_data = format_response_timestamps(data, timestamp_mode)
    
    # Enhance with metadata
    enhanced_data = enhance_json_endpoint_response(
        endpoint_path=request.path,
        response_data=formatted_data,
        api_key=api_key,
        request_timestamp=timezone.now()
    )
    
    return JSONResponseFormatter.create_json_response(
        data=enhanced_data,
        api_key_config=api_config,
        auto_timestamp_switch=(timestamp_mode == 'auto')
    )
