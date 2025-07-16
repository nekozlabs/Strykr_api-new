import calendar as cal
import json

from datetime import datetime, timedelta
from dateutil import relativedelta
from django.utils import timezone
from operator import itemgetter
from statistics import mean

from .country_data import COUNTRY_DATA


def calculate_thresholds(values):
	"""
	Calculate low, medium and high thresholds from a list of values.
	"""
	if not values:
		return {}

	# Calculate mean
	mean = sum(values) / len(values)

	# Calculate standard deviation
	squared_diff_sum = sum((x - mean) ** 2 for x in values)
	std = (squared_diff_sum / len(values)) ** 0.5

	# Calculate percentiles
	sorted_values = sorted(values)
	low_index = int(len(values) * 0.25)
	med_index = int(len(values) * 0.50)

	return {
		"low": sorted_values[low_index],
		"medium": sorted_values[med_index],
		"high": mean + 1.25 * std,
	}


def get_calendar_data(month, year, events, country_list):
	"""
	Create and get the calendar data.
	"""

	# Month as number
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

	# Convert month/year to datetime for easier manipulation
	current_month = datetime(int(year), int(month_numbers[month]), 1)

	# Get start date (3 days before month start) and end date (3 days after month end)
	start_date = current_month - timedelta(days=3)
	_, last_day = cal.monthrange(int(year), int(month_numbers[month]))
	end_date = datetime(int(year), int(month_numbers[month]), last_day) + timedelta(
		days=3
	)

	# Get today's date range for week view
	today = datetime.now()
	week_start = today - timedelta(days=3)
	week_end = today + timedelta(days=3)

	# Set up the structure
	calendar_data = {}
	current_date = start_date

	while current_date <= end_date:
		date_str = current_date.strftime("%Y-%m-%d")
		weekday = current_date.weekday()

		calendar_data[date_str] = {
			"date": str(current_date.day).zfill(2),
			"month": str(current_date.month).zfill(2),
			"year": str(current_date.year),
			"events": [],
			"base_score": 0,
			"display_score": 0,
			"event_scores": [],
			"context": "none",
			"volatility": "none",
			"is_current_month": current_date.month == int(month_numbers[month]),
		}
		# calendar_data[date_str]["weekday"] = weekday
		# calendar_data[date_str]["weekday_range"] = range(weekday)
		# calendar_data[date_str]["weekday_range_reverse"] = range(6 - weekday)

		# Calculate adjacent days
		next_day = current_date + timedelta(days=1)
		next_two_days = current_date + timedelta(days=2)
		prev_day = current_date - timedelta(days=1)
		prev_two_days = current_date - timedelta(days=2)

		calendar_data[date_str].update(
			{
				"t_plus_1": next_day.strftime("%Y-%m-%d"),
				"t_plus_2": next_two_days.strftime("%Y-%m-%d"),
				"t_minus_1": prev_day.strftime("%Y-%m-%d"),
				"t_minus_2": prev_two_days.strftime("%Y-%m-%d"),
			}
		)

		current_date += timedelta(days=1)

	# Add the events
	for index, event in enumerate(events):
		# Filter events using country data
		if len(country_list) > 0 and event["country"] not in country_list:
			continue

		# Format the date and add the id
		event["datetime"] = datetime.strptime((event["date"]), "%Y-%m-%d %H:%M:%S")
		event["datetime_str"] = event["datetime"].isoformat() + "Z"
		event_date = event["date"].split()[0]
		event["date"] = event_date
		event["id"] = f"{event_date}-{index}"

		# Get the slot (ignore events not in the extended range)
		if event["date"] not in calendar_data:
			continue
		calendar_slot = calendar_data[event["date"]]

		# Add the country name, flag and get the country score
		if event["country"] in COUNTRY_DATA:
			event["country_name"] = COUNTRY_DATA[event["country"]]["name"]
			event["flag"] = COUNTRY_DATA[event["country"]]["flag"]
			country_score = COUNTRY_DATA[event["country"]]["score"]
		else:
			event["country_name"] = ""
			event["flag"] = ""
			country_score = 0.0

		# Set the score using impact value and country score
		if event["impact"] == "Low":
			event["score"] = 1.0 if country_score == 0.0 else mean([1.0, country_score])
		elif event["impact"] == "Medium":
			event["score"] = 2.5 if country_score == 0.0 else mean([2.5, country_score])
		elif event["impact"] == "High":
			event["score"] = 4.0 if country_score == 0.0 else mean([4.0, country_score])
		else:
			event["score"] = 0.0

		# Append
		calendar_slot["events"].append(event)
		calendar_slot["event_scores"].append(event["score"])

	# Calculate the scores
	for k, v in calendar_data.items():
		calendar_slot = calendar_data[k]
		if len(calendar_slot["event_scores"]) > 0:
			calendar_slot["base_score"] = sum(calendar_slot["event_scores"])
			calendar_slot["display_score"] = calendar_slot["base_score"]

	# Add to scores using adjacent days
	display_scores = []
	for k, v in calendar_data.items():
		calendar_slot = calendar_data[k]
		if calendar_slot["t_plus_1"] in calendar_data:
			calendar_slot["display_score"] += (
				calendar_data[calendar_slot["t_plus_1"]]["base_score"] * 0.25
			)
		if calendar_slot["t_plus_2"] in calendar_data:
			calendar_slot["display_score"] += (
				calendar_data[calendar_slot["t_plus_2"]]["base_score"] * 0.125
			)
		if calendar_slot["t_minus_1"] in calendar_data:
			calendar_slot["display_score"] += (
				calendar_data[calendar_slot["t_minus_1"]]["base_score"] * 0.25
			)
		if calendar_slot["t_minus_2"] in calendar_data:
			calendar_slot["display_score"] += (
				calendar_data[calendar_slot["t_minus_2"]]["base_score"] * 0.125
			)
		display_scores.append(calendar_slot["display_score"])

	# Calculate the thresholds and set the context and volatility
	thresholds = calculate_thresholds(display_scores)
	for k, v in calendar_data.items():
		calendar_slot = calendar_data[k]
		if (
			calendar_slot["display_score"] > thresholds["low"]
			and calendar_slot["display_score"] < thresholds["medium"]
		):
			calendar_slot["context"] = "warning"
			calendar_slot["volatility"] = "low"
		if (
			calendar_slot["display_score"] >= thresholds["medium"]
			and calendar_slot["display_score"] < thresholds["high"]
		):
			calendar_slot["context"] = "info"
			calendar_slot["volatility"] = "medium"
		if calendar_slot["display_score"] >= thresholds["high"]:
			calendar_slot["context"] = "danger"
			calendar_slot["volatility"] = "high"

	# Create the week data dictionary
	# Only score and number of events are set
	# This is needed for the AI agent
	week_data = {}
	current_date = week_start
	while current_date <= week_end:
		date_str = current_date.strftime("%Y-%m-%d")
		if date_str in calendar_data:
			date_events = sorted(
				calendar_data[date_str]["events"], key=itemgetter("score"), reverse=True
			)
			top_10_events = []
			for event in date_events[:10]:
				top_10_events.append(
					{
						"name": event["event"],
						"country": event["country_name"],
						"currency": event["currency"],
						"impact": event["impact"],
					}
				)
			week_data[date_str] = {
				"volatility_score": calendar_data[date_str]["display_score"],
				"volatility": calendar_data[date_str]["volatility"],
				"top_10_events": top_10_events,
				"number_of_events": len(date_events),
			}
		current_date += timedelta(days=1)

	return {
		"month": {k: calendar_data[k] for k in list(calendar_data.keys())[3:-3]},
		"week": week_data,
		"thresholds": thresholds,
	}
