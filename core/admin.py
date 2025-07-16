from django.contrib import admin

from .models import Org, APIKey, AIQuery, EconomicEvents, BellwetherAsset, MarketScreenerResult, CalendarMarketAlert


@admin.register(Org)
class OrgAdmin(admin.ModelAdmin):
	list_display = ["name", "is_verified"]
	search_fields = ["name"]


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
	list_display = [
		"org",
		"name",
		"key",
		"client_side_key",
		"allowed_domains",
		"is_revoked",
		"is_unlimited",
		"daily_limit",
		"expires_at",
		"monthly_limit",
		"permission_level",
		"created_at",
		"updated_at",
	]
	search_fields = ["org__name", "name", "key", "client_side_key", "allowed_domains"]


@admin.register(AIQuery)
class AIQueryAdmin(admin.ModelAdmin):
	list_display = ["query"]
	search_fields = ["query", "user__email", "api_key__name", "third_party_user_id"]


@admin.register(EconomicEvents)
class EconomicEventsAdmin(admin.ModelAdmin):
	list_display = ["month", "year", "updated_at"]
	search_fields = ["month", "year"]


@admin.register(BellwetherAsset)
class BellwetherAssetAdmin(admin.ModelAdmin):
	list_display = ["name", "symbol", "data_type", "updated_at"]
	search_fields = ["name", "symbol", "data_type"]

@admin.register(MarketScreenerResult)
class MarketScreenerResultAdmin(admin.ModelAdmin):
	list_display = ["id", "timestamp", "analysis_date"]
	list_filter = ["analysis_date"]
	search_fields = ["id", "analysis_date"]
	date_hierarchy = "analysis_date"

@admin.register(CalendarMarketAlert)
class CalendarMarketAlertAdmin(admin.ModelAdmin):
	list_display = ["id", "timestamp", "short_summary", "full_analysis", "window_volatility_intensity"]