from django.contrib import admin

from models import BadWord

@admin.register(BadWord)
class BadWordAdmin(admin.ModelAdmin):
    list_display = ['text',]