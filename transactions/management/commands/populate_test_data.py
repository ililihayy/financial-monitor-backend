"""
Management command to populate the database with test data.

Creates test users, categories, and transactions for development and testing.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta
from accounts.models import CustomUser
from transactions.models import Category, Transaction


class Command(BaseCommand):
    help = 'Populate the database with test data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before populating',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            Transaction.objects.all().delete()
            Category.objects.filter(user__isnull=False).delete()  # Only delete user categories
            CustomUser.objects.filter(is_superuser=False).delete()
            self.stdout.write('Existing data cleared.')

        # Create test users
        self.stdout.write('Creating test users...')
        users_data = [
            {
                'email': 'john.doe@example.com',
                'password': 'password123',
                'currency_preference': 'USD',
            },
            {
                'email': 'jane.smith@example.com',
                'password': 'password123',
                'currency_preference': 'EUR',
            },
            {
                'email': 'bob.johnson@example.com',
                'password': 'password123',
                'currency_preference': 'UAH',
            },
        ]

        users = []
        for user_data in users_data:
            user, created = CustomUser.objects.get_or_create(
                email=user_data['email'],
                defaults={
                    'currency_preference': user_data['currency_preference'],
                    'is_active': True,
                }
            )
            if created:
                user.set_password(user_data['password'])
                user.save()
                self.stdout.write(f'Created user: {user.email}')
            users.append(user)

        # Create system categories
        self.stdout.write('Creating system categories...')
        system_categories_data = [
            # Income categories
            {'name': 'Salary', 'type': 'Income', 'icon_identifier': 'Briefcase'},
            {'name': 'Freelance', 'type': 'Income', 'icon_identifier': 'Laptop'},
            {'name': 'Investment', 'type': 'Income', 'icon_identifier': 'TrendingUp'},
            {'name': 'Gift', 'type': 'Income', 'icon_identifier': 'Gift'},

            # Expense categories
            {'name': 'Food', 'type': 'Expense', 'icon_identifier': 'UtensilsCrossed'},
            {'name': 'Transport', 'type': 'Expense', 'icon_identifier': 'Car'},
            {'name': 'Housing', 'type': 'Expense', 'icon_identifier': 'Home'},
            {'name': 'Entertainment', 'type': 'Expense', 'icon_identifier': 'Film'},
            {'name': 'Shopping', 'type': 'Expense', 'icon_identifier': 'ShoppingBag'},
            {'name': 'Utilities', 'type': 'Expense', 'icon_identifier': 'Zap'},
            {'name': 'Healthcare', 'type': 'Expense', 'icon_identifier': 'Heart'},
            {'name': 'Education', 'type': 'Expense', 'icon_identifier': 'Book'},
        ]

        categories = []
        for cat_data in system_categories_data:
            category, created = Category.objects.get_or_create(
                name=cat_data['name'],
                user=None,  # System category
                defaults={
                    'type': cat_data['type'],
                    'icon_identifier': cat_data['icon_identifier'],
                }
            )
            categories.append(category)
            if created:
                self.stdout.write(f'Created system category: {category.name}')

        # Create user-specific categories
        self.stdout.write('Creating user-specific categories...')
        user_categories_data = [
            {'name': 'Business Travel', 'type': 'Expense', 'icon_identifier': 'Plane'},
            {'name': 'Consulting', 'type': 'Income', 'icon_identifier': 'Briefcase'},
        ]

        for user in users[:2]:  # Only for first 2 users
            for cat_data in user_categories_data:
                category, created = Category.objects.get_or_create(
                    name=cat_data['name'],
                    user=user,
                    defaults={
                        'type': cat_data['type'],
                        'icon_identifier': cat_data['icon_identifier'],
                    }
                )
                categories.append(category)
                if created:
                    self.stdout.write(f'Created user category: {category.name} for {user.email}')

        # Create transactions for each user
        self.stdout.write('Creating transactions...')
        today = date.today()

        # John Doe's transactions (USD)
        john = users[0]
        john_categories = [cat for cat in categories if cat.user is None or cat.user == john]

        john_transactions = [
            # Current month (January 2025)
            {'category': 'Salary', 'amount': Decimal('5000.00'), 'date': today, 'description': 'Monthly salary'},
            {'category': 'Food', 'amount': Decimal('450.00'), 'date': today - timedelta(days=2), 'description': 'Groceries and dining'},
            {'category': 'Transport', 'amount': Decimal('300.00'), 'date': today - timedelta(days=5), 'description': 'Gas and car maintenance'},
            {'category': 'Housing', 'amount': Decimal('1200.00'), 'date': today - timedelta(days=1), 'description': 'Rent payment'},
            {'category': 'Entertainment', 'amount': Decimal('150.00'), 'date': today - timedelta(days=7), 'description': 'Movies and games'},
            {'category': 'Utilities', 'amount': Decimal('180.00'), 'date': today - timedelta(days=10), 'description': 'Electricity and water'},
            {'category': 'Shopping', 'amount': Decimal('200.00'), 'date': today - timedelta(days=12), 'description': 'Clothes and household items'},
            {'category': 'Healthcare', 'amount': Decimal('120.00'), 'date': today - timedelta(days=15), 'description': 'Doctor visit and medication'},
            {'category': 'Education', 'amount': Decimal('300.00'), 'date': today - timedelta(days=20), 'description': 'Online courses'},

            # Previous month (December 2024)
            {'category': 'Salary', 'amount': Decimal('5000.00'), 'date': today - timedelta(days=32), 'description': 'Monthly salary'},
            {'category': 'Food', 'amount': Decimal('380.00'), 'date': today - timedelta(days=35), 'description': 'Groceries and dining'},
            {'category': 'Transport', 'amount': Decimal('280.00'), 'date': today - timedelta(days=40), 'description': 'Gas and car maintenance'},
            {'category': 'Housing', 'amount': Decimal('1200.00'), 'date': today - timedelta(days=33), 'description': 'Rent payment'},
            {'category': 'Entertainment', 'amount': Decimal('100.00'), 'date': today - timedelta(days=38), 'description': 'Movies and games'},
            {'category': 'Utilities', 'amount': Decimal('170.00'), 'date': today - timedelta(days=42), 'description': 'Electricity and water'},
            {'category': 'Shopping', 'amount': Decimal('150.00'), 'date': today - timedelta(days=45), 'description': 'Clothes and household items'},
            {'category': 'Healthcare', 'amount': Decimal('80.00'), 'date': today - timedelta(days=48), 'description': 'Doctor visit'},
            {'category': 'Freelance', 'amount': Decimal('800.00'), 'date': today - timedelta(days=50), 'description': 'Web development project'},

            # Two months ago (November 2024)
            {'category': 'Salary', 'amount': Decimal('4800.00'), 'date': today - timedelta(days=62), 'description': 'Monthly salary'},
            {'category': 'Food', 'amount': Decimal('420.00'), 'date': today - timedelta(days=65), 'description': 'Groceries and dining'},
            {'category': 'Transport', 'amount': Decimal('320.00'), 'date': today - timedelta(days=70), 'description': 'Gas and car maintenance'},
            {'category': 'Housing', 'amount': Decimal('1200.00'), 'date': today - timedelta(days=63), 'description': 'Rent payment'},
            {'category': 'Entertainment', 'amount': Decimal('180.00'), 'date': today - timedelta(days=68), 'description': 'Movies and games'},
            {'category': 'Utilities', 'amount': Decimal('190.00'), 'date': today - timedelta(days=72), 'description': 'Electricity and water'},
            {'category': 'Shopping', 'amount': Decimal('250.00'), 'date': today - timedelta(days=75), 'description': 'Clothes and household items'},
            {'category': 'Investment', 'amount': Decimal('500.00'), 'date': today - timedelta(days=80), 'description': 'Stock dividends'},
        ]

        # Create transactions for John
        for tx_data in john_transactions:
            category = next((cat for cat in john_categories if cat.name == tx_data['category']), None)
            if category:
                Transaction.objects.create(
                    user=john,
                    category=category,
                    amount=tx_data['amount'],
                    date=tx_data['date'],
                    description=tx_data['description'],
                )

        # Jane Smith's transactions (EUR) - smaller amounts
        jane = users[1]
        jane_categories = [cat for cat in categories if cat.user is None or cat.user == jane]

        jane_transactions = [
            # Current month
            {'category': 'Salary', 'amount': Decimal('3500.00'), 'date': today, 'description': 'Monthly salary'},
            {'category': 'Food', 'amount': Decimal('320.00'), 'date': today - timedelta(days=3), 'description': 'Groceries and dining'},
            {'category': 'Transport', 'amount': Decimal('180.00'), 'date': today - timedelta(days=6), 'description': 'Public transport'},
            {'category': 'Housing', 'amount': Decimal('850.00'), 'date': today - timedelta(days=2), 'description': 'Rent payment'},
            {'category': 'Entertainment', 'amount': Decimal('120.00'), 'date': today - timedelta(days=8), 'description': 'Cinema and concerts'},
            {'category': 'Shopping', 'amount': Decimal('150.00'), 'date': today - timedelta(days=14), 'description': 'Clothes shopping'},
            {'category': 'Utilities', 'amount': Decimal('120.00'), 'date': today - timedelta(days=11), 'description': 'Electricity and internet'},

            # Previous month
            {'category': 'Salary', 'amount': Decimal('3500.00'), 'date': today - timedelta(days=32), 'description': 'Monthly salary'},
            {'category': 'Food', 'amount': Decimal('280.00'), 'date': today - timedelta(days=36), 'description': 'Groceries and dining'},
            {'category': 'Transport', 'amount': Decimal('170.00'), 'date': today - timedelta(days=38), 'description': 'Public transport'},
            {'category': 'Housing', 'amount': Decimal('850.00'), 'date': today - timedelta(days=33), 'description': 'Rent payment'},
            {'category': 'Entertainment', 'amount': Decimal('90.00'), 'date': today - timedelta(days=40), 'description': 'Movies'},
            {'category': 'Shopping', 'amount': Decimal('120.00'), 'date': today - timedelta(days=44), 'description': 'Clothes shopping'},
            {'category': 'Utilities', 'amount': Decimal('110.00'), 'date': today - timedelta(days=42), 'description': 'Electricity and internet'},
            {'category': 'Consulting', 'amount': Decimal('600.00'), 'date': today - timedelta(days=48), 'description': 'Design consulting'},
        ]

        # Create transactions for Jane
        for tx_data in jane_transactions:
            category = next((cat for cat in jane_categories if cat.name == tx_data['category']), None)
            if category:
                Transaction.objects.create(
                    user=jane,
                    category=category,
                    amount=tx_data['amount'],
                    date=tx_data['date'],
                    description=tx_data['description'],
                )

        # Bob Johnson's transactions (UAH) - different scale
        bob = users[2]
        bob_categories = [cat for cat in categories if cat.user is None or cat.user == bob]

        bob_transactions = [
            # Current month
            {'category': 'Salary', 'amount': Decimal('45000.00'), 'date': today, 'description': 'Monthly salary'},
            {'category': 'Food', 'amount': Decimal('8500.00'), 'date': today - timedelta(days=2), 'description': 'Groceries and dining'},
            {'category': 'Transport', 'amount': Decimal('3200.00'), 'date': today - timedelta(days=5), 'description': 'Taxi and metro'},
            {'category': 'Housing', 'amount': Decimal('15000.00'), 'date': today - timedelta(days=1), 'description': 'Rent payment'},
            {'category': 'Entertainment', 'amount': Decimal('1800.00'), 'date': today - timedelta(days=7), 'description': 'Movies and games'},
            {'category': 'Utilities', 'amount': Decimal('2200.00'), 'date': today - timedelta(days=10), 'description': 'Electricity and water'},
            {'category': 'Shopping', 'amount': Decimal('3500.00'), 'date': today - timedelta(days=12), 'description': 'Clothes and household items'},
            {'category': 'Healthcare', 'amount': Decimal('1200.00'), 'date': today - timedelta(days=15), 'description': 'Medical checkup'},

            # Previous month
            {'category': 'Salary', 'amount': Decimal('45000.00'), 'date': today - timedelta(days=32), 'description': 'Monthly salary'},
            {'category': 'Food', 'amount': Decimal('7800.00'), 'date': today - timedelta(days=35), 'description': 'Groceries and dining'},
            {'category': 'Transport', 'amount': Decimal('2900.00'), 'date': today - timedelta(days=40), 'description': 'Taxi and metro'},
            {'category': 'Housing', 'amount': Decimal('15000.00'), 'date': today - timedelta(days=33), 'description': 'Rent payment'},
            {'category': 'Entertainment', 'amount': Decimal('1600.00'), 'date': today - timedelta(days=38), 'description': 'Movies and games'},
            {'category': 'Utilities', 'amount': Decimal('2100.00'), 'date': today - timedelta(days=42), 'description': 'Electricity and water'},
            {'category': 'Shopping', 'amount': Decimal('2800.00'), 'date': today - timedelta(days=45), 'description': 'Clothes and household items'},
            {'category': 'Gift', 'amount': Decimal('5000.00'), 'date': today - timedelta(days=50), 'description': 'Birthday gift from family'},
        ]

        # Create transactions for Bob
        for tx_data in bob_transactions:
            category = next((cat for cat in bob_categories if cat.name == tx_data['category']), None)
            if category:
                Transaction.objects.create(
                    user=bob,
                    category=category,
                    amount=tx_data['amount'],
                    date=tx_data['date'],
                    description=tx_data['description'],
                )

        # Count created objects
        user_count = CustomUser.objects.filter(is_superuser=False).count()
        category_count = Category.objects.count()
        transaction_count = Transaction.objects.count()

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully populated database with:\n'
                f'- {user_count} users\n'
                f'- {category_count} categories\n'
                f'- {transaction_count} transactions'
            )
        )