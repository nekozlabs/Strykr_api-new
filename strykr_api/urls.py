from django.contrib import admin
from django.urls import path, include
from core.api_endpoints import api

urlpatterns = [
	path("admin/", admin.site.urls),
	path("api/", api.urls, name="core"),
]

admin.site.site_header = "Strykr.ai API admin"
admin.site.site_title = "Strykr.ai API admin"
