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

    name = models.TextField(
        verbose_name='Category Name',
        help_text='Name of the category (Encrypted at rest)'
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

    @property
    def decrypted_name(self):
        """Розшифровує назву для відображення."""
        from accounts.services.encryption_service import EncryptionService
        if self.name and self.name.startswith('gAAAA'):
            try:
                return EncryptionService.decrypt(self.name)
            except Exception:
                return "[Decryption Error]"
        return self.name

    def __str__(self):
        """String representation of the category."""
        owner = self.user.decrypted_email if self.user else 'System'
        return f"{self.decrypted_name} ({self.type}) - {owner}"

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
    amount = models.TextField(
        verbose_name='Amount',
        help_text='Transaction amount (Encrypted at rest).'
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
    is_suspicious = models.BooleanField(
        default=False,
        verbose_name='Is Suspicious',
        help_text='Flagged by Isolation Forest anomaly detection.'
    )
    anomaly_score = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Anomaly Score',
        help_text='Isolation Forest anomaly score (lower = more anomalous).'
    )
    predicted_category = models.ForeignKey(
        'Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='predicted_transactions',
        verbose_name='Predicted Category',
        help_text='ML-predicted category from auto-categorization service.'
    )
    is_encrypted = models.BooleanField(
        default=False,
        verbose_name='Is Encrypted',
        help_text='Whether the description field is Fernet-encrypted at rest.'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Created At',
        help_text='Timestamp when the transaction was created in the system.'
    )

    @property
    def decrypted_amount(self):
        """Дешифрує суму та повертає її як Decimal."""
        from accounts.services.encryption_service import EncryptionService
        from decimal import Decimal
        if self.amount and self.amount.startswith('gAAAA'):
            try:
                dec_str = EncryptionService.decrypt(self.amount)
                return Decimal(dec_str)
            except Exception:
                return Decimal('0.00')
        return Decimal(self.amount) if self.amount else Decimal('0.00')

    @property
    def decrypted_description(self):
        """Розшифровує опис для відображення в інтерфейсі."""
        from accounts.services.encryption_service import EncryptionService
        if not self.description:
            return ""
        try:
            return EncryptionService.decrypt(self.description)
        except Exception:
            return "[Error: Decryption Failed]"

    def save(self, *args, **kwargs):
        """Шифрування всіх полів перед записом у БД."""
        from accounts.services.encryption_service import EncryptionService
        
        # Шифруємо суму (перетворюємо Decimal у рядок перед шифруванням)
        amount_str = str(self.amount)
        if not amount_str.startswith('gAAAA'):
            self.amount = EncryptionService.encrypt(amount_str)

        # Шифруємо опис
        if self.description and not self.description.startswith('gAAAA'):
            self.description = EncryptionService.encrypt(self.description)
            
        self.is_encrypted = True
        super().save(*args, **kwargs)

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
        return f"{self.user.decrypted_email} - {self.category.decrypted_name} - {self.decrypted_amount} ({self.date})"


class AdvisorConversation(models.Model):
    """
    A named conversation thread between a user and the AI Financial Advisor.

    The title is auto-generated from the first user message and can hold
    up to 100 characters.  All messages in the thread are stored as related
    AdvisorMessage instances.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='advisor_conversations',
        verbose_name='User',
    )
    title = models.CharField(
        max_length=100,
        verbose_name='Title',
        help_text='Auto-generated from the first user message.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Advisor Conversation'
        verbose_name_plural = 'Advisor Conversations'

    def __str__(self) -> str:
        return f"{self.user.email} — {self.title[:40]}"


class AdvisorMessage(models.Model):
    """
    A single message turn (user or assistant) within an AdvisorConversation.
    """

    ROLE_USER = 'user'
    ROLE_ASSISTANT = 'assistant'
    ROLE_CHOICES = [
        (ROLE_USER, 'User'),
        (ROLE_ASSISTANT, 'Assistant'),
    ]

    conversation = models.ForeignKey(
        AdvisorConversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    # status mirrors the service response status; empty for user messages.
    status = models.CharField(max_length=20, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Advisor Message'
        verbose_name_plural = 'Advisor Messages'

    def __str__(self) -> str:
        return f"[{self.role}] {self.content[:60]}"
