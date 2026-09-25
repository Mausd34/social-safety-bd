from django.contrib import admin
from .models import Area, Case, ChatMessage, ChatThread, City, SafetyReport, Upazila

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "division", "reported_cases", "under_investigation", "under_trial", "convicted", "acquitted")
    list_filter = ("division",)
    search_fields = ("name", "division")
    prepopulated_fields = {"slug": ("name",)}

@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "reported_cases", "under_investigation", "under_trial", "convicted")
    list_filter = ("city",)
    search_fields = ("name", "city__name")

@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("case_id", "city", "area", "status", "verified", "incident_date", "last_updated")
    list_filter = ("status", "verified", "city")
    search_fields = ("case_id", "city__name", "area__name", "source_name")
    readonly_fields = ("last_updated",)

@admin.register(Upazila)
class UpazilaAdmin(admin.ModelAdmin):
    list_display = ("name", "district", "latitude", "longitude")
    list_filter = ("district",)
    search_fields = ("name", "district__name")
    prepopulated_fields = {"slug": ("name",)}

@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "upazila", "status", "user", "created_at", "last_activity")
    list_filter = ("status", "upazila__district")
    search_fields = ("upazila__name", "subject")
    readonly_fields = ("created_at", "last_activity")

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "sender", "created_at")
    list_filter = ("sender",)
    search_fields = ("body", "thread__upazila__name")
    readonly_fields = ("created_at",)

@admin.register(SafetyReport)
class SafetyReportAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "location", "status", "created_at")
    list_filter = ("status", "category")
    search_fields = ("location", "category", "description")
    readonly_fields = ("created_at",)
