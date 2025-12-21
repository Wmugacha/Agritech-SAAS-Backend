from django.contrib import admin
from .models import SoilSample


@admin.register(SoilSample)
class SoilSampleAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "organization",
        "uploaded_by",
        "ph",
        "created_at",
    )
    list_filter = ("organization", "crop_type")
    search_fields = ("label",)
