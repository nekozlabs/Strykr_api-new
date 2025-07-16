import requests

from django.conf import settings
from django.core.management.base import BaseCommand

from core.bellwether_assets import BELLWETHER_ASSETS
from core.models import BellwetherAsset
from core.error_handlers import api_response_error_handler

class Command(BaseCommand):
	help = "Get and save the bellwether assets data every 10 minutes"

	def handle(self, *args, **kwargs):
		# Define technical indicators to fetch
		indicators = ["RSI", "EMA", "SMA", "DEMA"]

		# Dictionary to store metadata about technical indicators
		indicator_metadata = {
			"RSI": {"timeframe": "2-hour", "period": 28},
			"EMA": {"timeframe": "4-hour", "period": 50},
			"DEMA": {"timeframe": "4-hour", "period": 20},
			"SMA": {"timeframe": "4-hour", "period": 200},
		}

		for key, value in BELLWETHER_ASSETS.items():
			# Process each technical indicator
			for indicator in indicators:
				try:
					# Skip if indicator not defined in asset config
					if indicator not in value:
						continue

					# Fetch data from FMP API
					api_response = requests.get(
						value[indicator].replace("your_api_key", settings.FMP_API_KEY)
					)
					api_response_json = api_response.json()

					# Error handling
					api_response_error_handler(api_response_json)

					# Add metadata to response
					for item in api_response_json:
						item["metadata"] = indicator_metadata[indicator]

					# Store in database
					BellwetherAsset.objects.update_or_create(
						name=value["name"],
						symbol=value["symbol"],
						descriptors=value["descriptors"],
						api_type=value["api_type"],
						data_type=indicator,
						defaults={
							"name": value["name"],
							"symbol": value["symbol"],
							"descriptors": value["descriptors"],
							"api_type": value["api_type"],
							"data_type": indicator,
							"data": api_response_json,
						},
						create_defaults={
							"name": value["name"],
							"symbol": value["symbol"],
							"descriptors": value["descriptors"],
							"api_type": value["api_type"],
							"data_type": indicator,
							"data": api_response_json,
						},
					)
					self.stdout.write(f"Processed {indicator} for {value['symbol']}")
				except Exception as e:
					self.stdout.write(self.style.ERROR(
						f"[Bellwether Assets Command] - Error with {indicator} for {value['symbol']}: {e}"
					))
				
		self.stdout.write(self.style.SUCCESS("Technical indicators successfully updated"))
