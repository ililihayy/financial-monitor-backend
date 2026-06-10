"""
Realistic UKRAINE-based financial data generator (in UAH) for lilipushkar15@gmail.com.
Covers 9 months (270 days) of transactions with local merchants in Ukrainian Hryvnia.
"""

import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import CustomUser
from transactions.models import Category, Transaction

random.seed(42)


class Command(BaseCommand):
    help = 'Fills lilipushkar15@gmail.com with 9 months of Ukraine-based UAH data'

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
            if user.currency_preference != 'UAH':
                user.currency_preference = 'UAH'
                user.save()
        except CustomUser.DoesNotExist:
            user = CustomUser.objects.create_user(
                email=email,
                password='TestPass123!',
                nickname='Lilia',
                currency_preference='UAH',
                is_active=True,
            )
            self.stdout.write(self.style.SUCCESS(f'Created user: {email}'))

        if options['clear']:
            deleted, _ = Transaction.objects.filter(user=user).delete()
            self.stdout.write(f'Deleted {deleted} existing transactions.')

        # Synchronize with frontend (category types: 'income' and 'expense')
        def get_cat(name, c_type, icon):
            return Category.objects.get_or_create(
                name=name,
                user=None,
                defaults={'type': c_type.lower(), 'icon_identifier': icon},
            )[0]

        cats = {
            'Salary':        get_cat('Salary',        'income',  'Briefcase'),
            'Freelance':     get_cat('Freelance',     'income',  'Laptop'),
            'Rent':          get_cat('Rent',          'expense', 'Home'),
            'Food':          get_cat('Food',          'expense', 'UtensilsCrossed'),
            'Transport':     get_cat('Transport',     'expense', 'Car'),
            'Shopping':      get_cat('Shopping',      'expense', 'ShoppingBag'),
            'Medical':       get_cat('Medical',       'expense', 'Heart'),
            'Utilities':     get_cat('Utilities',     'expense', 'Zap'),
            'Entertainment': get_cat('Entertainment', 'expense', 'Music'),
            'Education':     get_cat('Education',     'expense', 'BookOpen'),
        }

        today = date.today()
        start_date = today - timedelta(days=270)

        self.stdout.write(f'Generating data from {start_date} to {today}...')

        ukraine_food = [
            ('Сільпо — Продукти', 1450.00),
            ('АТБ-Маркет — Щоденні закупи', 620.00),
            ('Новус — Супермаркет', 2100.00),
            ('Aroma Kava — Флет Вайт', 85.00),
            ('Idealist Coffee — Сніданок', 360.00),
            ('Пузата Хата — Обід', 240.00),
            ('Milk Bar — Десерти', 480.00),
            ('Glovo — Доставка McDonalds', 450.00),
            ('Bolt Food — Суші сет', 890.00),
            ('Львівські Круасани', 180.00),
        ]

        ukraine_transport = [
            ('Bolt — Поїздка на роботу', 180.00),
            ('Uklon — Вечірня поїздка', 240.00),
            ('Київський Метрополітен — Поповнення', 200.00),
            ('ОККО — Паливо (А-95)', 1800.00),
            ('WOG — Паливо та кава', 1950.00),
        ]

        ukraine_utilities = [
            ('Yasno — Електроенергія', 750.00),
            ('Нафтогаз — Газопостачання', 480.00),
            ('Київводоканал — Водопостачання', 420.00),
            ('Київстар — Мобільний тариф', 275.00),
            ('Ланет — Інтернет 1 Гбіт/с', 330.00),
        ]

        shopping_items = [
            ('Rozetka — Товари для дому', 1100.00),
            ('Zara — Ocean Plaza', 2600.00),
            ('Епіцентр — Матеріали/Побут', 1650.00),
            ('Makeup.com.ua — Косметика', 1200.00),
            ('Prom.ua — Замовлення', 600.00),
        ]

        current_date = start_date
        while current_date <= today:
            if current_date.day == 1 or current_date.day == 15:
                Transaction.objects.create(
                    user=user, category=cats['Salary'],
                    amount=36000.00, date=current_date,
                    description='Заробітна плата — ІТ Компанія'
                )

            if current_date.day == 1:
                Transaction.objects.create(
                    user=user, category=cats['Rent'],
                    amount=18000.00, date=current_date,
                    description='Оренда квартири'
                )

            if current_date.day == 10:
                for name, price in ukraine_utilities:
                    Transaction.objects.create(
                        user=user, category=cats['Utilities'],
                        amount=round(price + random.uniform(-40, 60), 2),
                        date=current_date, description=name
                    )

            if random.random() < 0.85:
                name, price = random.choice(ukraine_food[:5])
                Transaction.objects.create(
                    user=user, category=cats['Food'],
                    amount=round(price + random.uniform(-30, 80), 2),
                    date=current_date, description=name
                )

            if random.random() < 0.45:
                name, price = random.choice(ukraine_transport)
                Transaction.objects.create(
                    user=user, category=cats['Transport'],
                    amount=round(price + random.uniform(-25, 150), 2),
                    date=current_date, description=name
                )

            if current_date.weekday() >= 5 and random.random() < 0.75:
                Transaction.objects.create(
                    user=user, category=cats['Food'],
                    amount=round(random.uniform(1600, 3800), 2),
                    date=current_date, description='Сільпо — Щотижневі закупи'
                )

            if current_date.day in [14, 28] and random.random() < 0.5:
                name, price = random.choice(shopping_items)
                Transaction.objects.create(
                    user=user, category=cats['Shopping'],
                    amount=round(price + random.uniform(-200, 700), 2),
                    date=current_date, description=name
                )

            if random.random() < 0.03:
                Transaction.objects.create(
                    user=user, category=cats['Medical'],
                    amount=round(random.uniform(400, 4500), 2),
                    date=current_date, description='Клініка Добробут — Консультація та ліки'
                )

            if random.random() < 0.05:
                Transaction.objects.create(
                    user=user, category=cats['Entertainment'],
                    amount=round(random.uniform(500, 2200), 2),
                    date=current_date, description='Планета Кіно — Квитки та попкорн'
                )

            current_date += timedelta(days=1)

        final_count = Transaction.objects.filter(user=user).count()
        self.stdout.write(self.style.SUCCESS(
            f'Successfully generated {final_count} transactions in UAH currency for 9 months.'
        ))
