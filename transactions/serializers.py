"""
Serializers for the transactions app with strict input validation.

Includes category and transaction serializers with field-level validation.
"""

from rest_framework import serializers
from django.core.validators import MinValueValidator
from django.utils import timezone
from datetime import datetime, date
from .models import Category, Transaction, AdvisorConversation, AdvisorMessage
from accounts.services.pii_detection_service import PIIDetectionService


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for Category model with strict validation.

    Validates category name, type, and ensures proper user assignment.
    Includes is_system (computed field) and icon (mapping from icon_identifier).
    """

    user = serializers.PrimaryKeyRelatedField(
        read_only=True,
        help_text='Owner of the category (automatically set from authenticated user).'
    )
    is_system = serializers.SerializerMethodField(
        read_only=True,
        help_text='Whether this is a system-default category (user is None).'
    )
    icon = serializers.CharField(
        source='icon_identifier',
        required=False,
        allow_blank=True,
        help_text='Icon identifier for the category (aliased as "icon" for frontend compatibility).'
    )

    class Meta:
        model = Category
        fields = ('id', 'name', 'user', 'type', 'icon_identifier',
                  'icon', 'is_system', 'is_active', 'created_at')
        read_only_fields = ('id', 'user', 'created_at', 'is_system')
        extra_kwargs = {
            'name': {'required': True, 'allow_blank': False},
            'type': {'required': True},
            'icon_identifier': {'required': False, 'allow_blank': True},
            'is_active': {'required': False},
        }

    def get_is_system(self, obj):
        """Return True if this is a system category (user is None)."""
        return obj.user is None

    def validate_name(self, value):
        """
        Validate category name.

        Args:
            value: Category name to validate

        Returns:
            str: Validated category name

        Raises:
            serializers.ValidationError: If name is invalid
        """
        if not value or not value.strip():
            raise serializers.ValidationError("Category name cannot be empty.")

        # Check length
        if len(value.strip()) > 100:
            raise serializers.ValidationError(
                "Category name cannot exceed 100 characters.")

        return value.strip()

    def validate(self, attrs):
        """
        Validate category data including uniqueness constraints.

        Args:
            attrs: Dictionary of serializer fields

        Returns:
            dict: Validated attributes

        Raises:
            serializers.ValidationError: If validation fails
        """
        user = self.context['request'].user
        name = attrs.get('name')
        category_type = attrs.get('type')

        # Check for duplicate category name for the same user and type
        if name and category_type:
            existing = Category.objects.filter(
                user=user,
                name=name,
                type=category_type
            )
            # Exclude current instance if updating
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise serializers.ValidationError(
                    f"A category with name '{name}' and type '{category_type}' already exists."
                )

        return attrs

    def to_representation(self, instance):
        """Дешифруємо назву категорії перед відправкою на фронтенд."""
        representation = super().to_representation(instance)
        representation['name'] = instance.decrypted_name # Використовуємо властивість з моделі
        return representation


class TransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for Transaction model with strict validation.

    Validates amount (no negative values), date ranges, and ensures proper relationships.
    """

    user = serializers.PrimaryKeyRelatedField(
        read_only=True,
        help_text='Owner of the transaction (automatically set from authenticated user).'
    )
    category_name = serializers.CharField(
        source='category.decrypted_name', 
        read_only=True
    )
    category_type = serializers.CharField(
        source='category.type',
        read_only=True,
        help_text='Type of the associated category (read-only).'
    )
    predicted_category_name = serializers.CharField(
        source='predicted_category.decrypted_name',
        read_only=True,
        default=None,
        help_text='ML-predicted category name (read-only).'
    )
    pii_warnings = serializers.SerializerMethodField(
        read_only=True,
        help_text='PII warnings detected in description (read-only).'
    )
    description = serializers.CharField(
        required=False, 
        allow_blank=True,
        help_text='Transaction description (will be encrypted on save).'
    )

    class Meta:
        model = Transaction
        fields = (
            'id', 'user', 'category', 'category_name', 'category_type',
            'amount', 'date', 'description', 'is_suspicious', 'anomaly_score',
            'predicted_category', 'predicted_category_name',
            'is_encrypted', 'pii_warnings', 'created_at'
        )
        read_only_fields = ('id', 'user', 'created_at', 'is_suspicious',
                            'anomaly_score', 'predicted_category', 'is_encrypted')
        extra_kwargs = {
            'amount': {'required': True},
            'date': {'required': True},
            'description': {'required': False, 'allow_blank': True},
        }

    _pii_warnings = None

    def get_pii_warnings(self, obj):
        """Return PII warnings if they were detected during validation."""
        if hasattr(self, '_pii_warnings') and self._pii_warnings:
            return self._pii_warnings
        return None

    def validate_amount(self, value):
        """
        Validate transaction amount (must be positive).

        Args:
            value: Amount to validate

        Returns:
            decimal.Decimal: Validated amount

        Raises:
            serializers.ValidationError: If amount is negative or zero
        """
        if value <= 0:
            raise serializers.ValidationError(
                "Transaction amount must be greater than zero."
            )

        # Maximum amount check (optional security measure)
        if value > 9999999999.99:  # 10 billion with 2 decimal places
            raise serializers.ValidationError(
                "Transaction amount exceeds maximum allowed value."
            )

        return value

    def validate_date(self, value):
        """
        Validate transaction date.

        Args:
            value: Date to validate

        Returns:
            date: Validated date

        Raises:
            serializers.ValidationError: If date is invalid
        """
        today = date.today()

        # Prevent future dates (optional business rule)
        if value > today:
            raise serializers.ValidationError(
                "Transaction date cannot be in the future."
            )

        # Optional: Prevent very old dates (e.g., more than 50 years ago)
        min_date = date(today.year - 50, 1, 1)
        if value < min_date:
            raise serializers.ValidationError(
                "Transaction date is too far in the past."
            )

        return value

    def validate_category(self, value):
        """
        Validate that category belongs to the user or is a system category.

        Args:
            value: Category instance to validate

        Returns:
            Category: Validated category

        Raises:
            serializers.ValidationError: If category is invalid
        """
        user = self.context['request'].user

        # Allow system categories (user=None) or user's own categories
        if value.user is not None and value.user != user:
            raise serializers.ValidationError(
                "You can only use your own categories or system default categories."
            )

        return value
    
    def to_representation(self, instance):
        """Дешифруємо всі чутливі поля транзакції."""
        representation = super().to_representation(instance)
        
        # 1. Дешифруємо суму та перетворюємо її на число для фронтенду
        representation['amount'] = float(instance.decrypted_amount)
        
        # 2. Дешифруємо опис
        representation['description'] = instance.decrypted_description
        
        return representation

    def validate_description(self, value):
        """
        Validate description length and scan for PII.
        """
        if value and len(value) > 5000:
            raise serializers.ValidationError(
                "Description cannot exceed 5000 characters."
            )

        # PII detection: warn (don't block) — include findings in context
        if value:
            pii_findings = PIIDetectionService.scan(value)
            if pii_findings:
                # Store findings in the serializer context so the view can
                # include the warning in the response without blocking save.
                self._pii_warnings = pii_findings

        return value


class TransactionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing transactions (optimized for list views).
    """

    category_name = serializers.CharField(
        source='category.decrypted_name', read_only=True)
    category_type = serializers.CharField(
        source='category.type', read_only=True)

    class Meta:
        model = Transaction
        fields = (
            'id', 'category', 'category_name', 'category_type',
            'amount', 'date', 'description', 'created_at'
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['amount'] = float(instance.decrypted_amount)
        representation['description'] = instance.decrypted_description
        return representation


# ── Advisor conversation serializers ─────────────────────────────────────────

class AdvisorMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdvisorMessage
        fields = ['id', 'role', 'content', 'status', 'created_at']


class AdvisorConversationSerializer(serializers.ModelSerializer):
    """Compact representation used in the conversations list."""
    message_count = serializers.IntegerField(
        source='messages.count', read_only=True)

    class Meta:
        model = AdvisorConversation
        fields = ['id', 'title', 'created_at', 'updated_at', 'message_count']


class AdvisorConversationDetailSerializer(serializers.ModelSerializer):
    """Full representation including all messages, used for detail / continue views."""
    messages = AdvisorMessageSerializer(many=True, read_only=True)

    class Meta:
        model = AdvisorConversation
        fields = ['id', 'title', 'created_at', 'updated_at', 'messages']
