"""
Realistic UKRAINE-based financial data generator (in USD) for lilipushkar15@gmail.com.
Covers 9 months (270 days) of transactions with local merchants like Silpo, Bolt, and OKKO.
"""

import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from accounts.models import CustomUser
from transactions.models import Category, Transaction

random.seed(42)


class Command(BaseCommand):
    help = 'Fills lilipushkar15@gmail.com with 9 months of Ukraine-based USD data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete existing transactions for the user before populating',
        )

    def handle(self, *args, **options):
        email = 'lilipushkar15@gmail.com'

        try:
            user = CustomUser.objects.get_by_natural_key(email)
            self.stdout.write(f'Found user: {email}')
        except CustomUser.DoesNotExist:
            user = CustomUser.objects.create_user(
                email=email,
                password='TestPass123!',
                nickname='Lilia',
                currency_preference='USD',
                is_active=True,
            )
            self.stdout.write(self.style.SUCCESS(f'Created user: {email}'))

        if options['clear']:
            deleted, _ = Transaction.objects.filter(user=user).delete()
            self.stdout.write(f'Deleted {deleted} existing transactions.')

        def get_cat(name, c_type, icon):
            return Category.objects.get_or_create(
                name=name,
                user=None,
                defaults={'type': c_type, 'icon_identifier': icon},
            )[0]

        cats = {
            'Salary':        get_cat('Salary',        'Income',  'Briefcase'),
            'Freelance':     get_cat('Freelance',      'Income',  'Laptop'),
            'Rent':          get_cat('Rent',           'Expense', 'Home'),
            'Food':          get_cat('Food',           'Expense', 'UtensilsCrossed'),
            'Transport':     get_cat('Transport',      'Expense', 'Car'),
            'Shopping':      get_cat('Shopping',       'Expense', 'ShoppingBag'),
            'Medical':       get_cat('Medical',        'Expense', 'Heart'),
            'Utilities':     get_cat('Utilities',      'Expense', 'Zap'),
            'Entertainment': get_cat('Entertainment',  'Expense', 'Music'),
            'Education':     get_cat('Education',      'Expense', 'BookOpen'),
        }

        today = date.today()
        # 9 місяців = приблизно 270 днів
        start_date = today - timedelta(days=270)

        self.stdout.write(f'Generating data from {start_date} to {today}...')

        # --- Допоміжні списки ---
        ukraine_food = [
            ('Silpo — Groceries', 35.00),
            ('ATB-Market — Daily shopping', 15.00),
            ('Novus — Weekly groceries', 50.00),
            ('Aroma Kava — Flat White', 2.10),
            ('Idealist Coffee — Breakfast', 8.50),
            ('Puzata Hata — Lunch', 6.00),
            ('Milk Bar — Dessert', 12.00),
            ('Glovo — McDonalds Delivery', 11.00),
            ('Bolt Food — Sushi order', 22.00),
            ('Lviv Croissants', 4.50),
        ]

        ukraine_transport = [
            ('Bolt — Ride to work', 4.50),
            ('Uklon — Evening trip', 6.00),
            ('Kyiv Metro — Card Top-up', 5.00),
            ('OKKO — Fuel (A-95)', 45.00),
            ('WOG — Fuel & Coffee', 48.00),
        ]

        ukraine_utilities = [
            ('Yasno — Electricity bill', 18.00),
            ('Naftogaz — Gas bill', 12.00),
            ('Kyivvodokanal — Water service', 10.00),
            ('Kyivstar — Mobile plan', 6.50),
            ('Lanet — Internet 1Gbps', 8.00),
        ]

        shopping_items = [
            ('Rozetka — Household items', 25.00),
            ('Zara — Ocean Plaza', 65.00),
            ('Epicentr — Home improvement', 40.00),
            ('Makeup.com.ua — Cosmetics', 30.00),
            ('Prom.ua — Order', 15.00),
        ]

        # --- Генерація ---
        current_date = start_date
        while current_date <= today:
            # 1. ДОХОДИ (Зарплата 1 та 15 числа)
            if current_date.day == 1 or current_date.day == 15:
                Transaction.objects.create(
                    user=user, category=cats['Salary'],
                    amount=1800.00, date=current_date,
                    description='Monthly Salary — Tech Company'
                )

            # 2. ОРЕНДА (1 числа)
            if current_date.day == 1:
                Transaction.objects.create(
                    user=user, category=cats['Rent'],
                    amount=650.00, date=current_date,
                    description='Rent — Apartment in Kyiv'
                )

            # 3. КОМУНАЛКА (10 числа)
            if current_date.day == 10:
                for name, price in ukraine_utilities:
                    Transaction.objects.create(
                        user=user, category=cats['Utilities'],
                        amount=price + random.uniform(-2, 3),
                        date=current_date, description=name
                    )

            # 4. ЩОДЕННІ ВИТРАТИ (Їжа та Транспорт)
            # Кава або дрібна їжа майже щодня
            if random.random() < 0.8:
                name, price = random.choice(ukraine_food[:5])
                Transaction.objects.create(
                    user=user, category=cats['Food'],
                    amount=round(price + random.uniform(-1, 2), 2),
                    date=current_date, description=name
                )

            # Таксі або транспорт 3-4 рази на тиждень
            if random.random() < 0.4:
                name, price = random.choice(ukraine_transport)
                Transaction.objects.create(
                    user=user, category=cats['Transport'],
                    amount=round(price + random.uniform(-1, 5), 2),
                    date=current_date, description=name
                )

            # 5. ТИЖНЕВІ ВИТРАТИ
            # Великі закупи в Сільпо/Новус по вихідних
            if current_date.weekday() >= 5 and random.random() < 0.7:
                Transaction.objects.create(
                    user=user, category=cats['Food'],
                    amount=round(random.uniform(40, 90), 2),
                    date=current_date, description='Silpo — Weekly Groceries'
                )

            # Шопінг раз на два тижні
            if current_date.day in [14, 28] and random.random() < 0.5:
                name, price = random.choice(shopping_items)
                Transaction.objects.create(
                    user=user, category=cats['Shopping'],
                    amount=round(price + random.uniform(-5, 20), 2),
                    date=current_date, description=name
                )

            # 6. ВИПАДКОВІ ВИТРАТИ
            # Медицина (Добробут / Аптека)
            if random.random() < 0.03:
                Transaction.objects.create(
                    user=user, category=cats['Medical'],
                    amount=round(random.uniform(20, 150), 2),
                    date=current_date, description='Dobrobut Clinic — Consultation'
                )

            # Розваги (Кіно / Вечірка)
            if random.random() < 0.05:
                Transaction.objects.create(
                    user=user, category=cats['Entertainment'],
                    amount=round(random.uniform(15, 60), 2),
                    date=current_date, description='Multiplex — Movie & Popcorn'
                )

            current_date += timedelta(days=1)

        final_count = Transaction.objects.filter(user=user).count()
        self.stdout.write(self.style.SUCCESS(
            f'Successfully generated {final_count} transactions for 9 months.'
        ))
