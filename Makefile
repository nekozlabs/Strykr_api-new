SHELL := /bin/bash

static:
	./manage.py collectstatic --no-input

run:
	uvicorn strykr_api.asgi:application --reload --port 5500

format:
	black manage.py
	black ./strykr_api
	black ./core
