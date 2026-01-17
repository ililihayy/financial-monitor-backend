"""
Admin configuration for the transactions app.
"""

from django.contrib import admin
from .models import Category, Transaction


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for Category model."""
    
    list_display = ('name', 'type', 'user', 'icon_identifier', 'created_at')
    list_filter = ('type', 'user', 'created_at')
    search_fields = ('name', 'icon_identifier')
    ordering = ('type', 'name')
    readonly_fields = ('created_at',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Admin interface for Transaction model."""
    
    list_display = ('user', 'category', 'amount', 'date', 'created_at')
    list_filter = ('category', 'date', 'created_at', 'category__type')
    search_fields = ('user__email', 'category__name', 'description')
    ordering = ('-date', '-created_at')
    readonly_fields = ('created_at',)
    date_hierarchy = 'date'
