import calendar as cal
import json
import logging
from ninja.errors import HttpError

def api_response_error_handler(api_response):
    FMP_API_ERRORS = {
    'Limit Reach': 'API rate limit exceeded',
    'Invalid API key': 'Invalid API credentials',
    'Permission Denied': 'Access denied to this endpoint'
    }
    
    if isinstance(api_response, dict) and 'Error Message' in api_response:
        error_msg = api_response['Error Message']
        
    # Log the specific error
        logging.error(f"FMP API Error: {error_msg}")

        # Check if it's a rate limit error
        if 'Limit Reach' in error_msg:
            raise HttpError(429, "API rate limit exceeded. Please try again later.")
        
        # Handle other known FMP errors
        for error_key, error_description in FMP_API_ERRORS.items():
            if error_key in error_msg:
                raise HttpError(400, error_description)
                
        # Generic error fallback
        raise HttpError(500, "External API error")

			# Validate that we got a list of events
    if not isinstance(api_response, list):
        logging.error(f"Unexpected API response format: {api_response}")
        raise HttpError(500, "Invalid response format from external API")