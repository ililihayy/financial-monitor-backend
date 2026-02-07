"""
Models for financial transactions and categories.

Includes Category (Income/Expense) and Transaction models with proper relationships.
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone


class Category(models.Model):
    """
    Category model for organizing transactions.

    Supports both system-default categories (user=None) and user-created categories.
    Categories can be either Income or Expense type.
    """

    TYPE_CHOICES = [
        ('Income', 'Income'),
        ('Expense', 'Expense'),
    ]

    name = models.CharField(
        max_length=100,
        verbose_name='Category Name',
        help_text='Name of the category (e.g., "Food", "Salary")'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='categories',
        verbose_name='User',
        help_text='Owner of the category. Null for system-default categories.'
    )
    type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES,
        verbose_name='Category Type',
        help_text='Whether this category is for Income or Expense transactions.'
    )
    icon_identifier = models.CharField(
        max_length=50,
        default='default',
        verbose_name='Icon Identifier',
        help_text='Identifier for the icon to display (e.g., "food", "shopping")'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Is Active',
        help_text='Whether this category is active and can be used for new transactions.'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At',
        help_text='Timestamp when the category was created.'
    )

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['type', 'name']
        # Ensure unique category names per user (or system-default)
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'user', 'type'],
                name='unique_category_per_user_type'
            )
        ]

    def __str__(self):
        """String representation of the category."""
        owner = self.user.email if self.user else 'System'
        return f"{self.name} ({self.type}) - {owner}"

    def delete(self, *args, **kwargs):
        """
        Override delete to implement soft-delete logic.

        If the category has linked transactions, set is_active=False instead of deleting.
        Otherwise, perform actual deletion.
        """
        if self.transactions.exists():
            # Soft delete: mark as inactive instead of removing from database
            self.is_active = False
            self.save(update_fields=['is_active'])
        else:
            # Hard delete: no linked transactions, safe to remove
            super().delete(*args, **kwargs)


class Transaction(models.Model):
    """
    Transaction model representing financial transactions.

    Each transaction belongs to a user and a category, with amount, date, and optional description.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name='User',
        help_text='User who owns this transaction.'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='transactions',
        verbose_name='Category',
        help_text='Category this transaction belongs to.'
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Amount',
        help_text='Transaction amount (must be positive).'
    )
    date = models.DateField(
        verbose_name='Transaction Date',
        help_text='Date when the transaction occurred.'
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='Description',
        help_text='Optional description or notes about the transaction.'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At',
        help_text='Timestamp when the transaction was created in the system.'
    )

    class Meta:
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['user', 'category', 'date']),
        ]

    def __str__(self):
        """String representation of the transaction."""
        return f"{self.user.email} - {self.category.name} - {self.amount} ({self.date})"
