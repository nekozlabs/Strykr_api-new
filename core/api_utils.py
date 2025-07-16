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