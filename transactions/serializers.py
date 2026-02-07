"""
Serializers for the transactions app with strict input validation.

Includes category and transaction serializers with field-level validation.
"""

from rest_framework import serializers
from django.core.validators import MinValueValidator
from django.utils import timezone
from datetime import datetime, date
from .models import Category, Transaction


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
        source='category.name',
        read_only=True,
        help_text='Name of the associated category (read-only).'
    )
    category_type = serializers.CharField(
        source='category.type',
        read_only=True,
        help_text='Type of the associated category (read-only).'
    )

    class Meta:
        model = Transaction
        fields = (
            'id', 'user', 'category', 'category_name', 'category_type',
            'amount', 'date', 'description', 'created_at'
        )
        read_only_fields = ('id', 'user', 'created_at')
        extra_kwargs = {
            'amount': {'required': True},
            'date': {'required': True},
            'description': {'required': False, 'allow_blank': True},
        }

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

    def validate_description(self, value):
        """
        Validate description length.

        Args:
            value: Description text to validate

        Returns:
            str: Validated description

        Raises:
            serializers.ValidationError: If description is too long
        """
        if value and len(value) > 5000:
            raise serializers.ValidationError(
                "Description cannot exceed 5000 characters."
            )

        return value


class TransactionListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing transactions (optimized for list views).
    """

    category_name = serializers.CharField(
        source='category.name', read_only=True)
    category_type = serializers.CharField(
        source='category.type', read_only=True)

    class Meta:
        model = Transaction
        fields = (
            'id', 'category', 'category_name', 'category_type',
            'amount', 'date', 'description', 'created_at'
        )
