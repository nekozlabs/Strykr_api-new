#!/usr/bin/env bash
python manage.py generate_market_alert
python manage.py generate_calendar_alert
# Removed: python manage.py generate_market_screener  - Not currently used and causing DB crashes
python manage.py generate_news_alert
python manage.py generate_crypto_news_alert