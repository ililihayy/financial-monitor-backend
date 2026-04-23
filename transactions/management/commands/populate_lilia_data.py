"""
Realistic USD financial data generator for liliapush04@gmail.com.

Generates 60 days of transactions with authentic US market prices,
merchant names, and spending patterns suitable for RAG/AI advisor demos.
"""

import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from accounts.models import CustomUser
from transactions.models import Category, Transaction

random.seed(42)


class Command(BaseCommand):
    help = 'Fills liliapush04@gmail.com with realistic USD test data (last 60 days)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete existing transactions for the user before populating',
        )

    def handle(self, *args, **options):
        email = 'liliapush04@gmail.com'

        try:
            user = CustomUser.objects.get(email=email)
            self.stdout.write(f'Found user: {email}')
        except CustomUser.DoesNotExist:
            self.stdout.write(self.style.WARNING(
                f'User {email} does not exist. Creating account...'
            ))
            user = CustomUser.objects.create_user(
                email=email,
                password='TestPass123!',
                nickname='Lilia',
                currency_preference='USD',
                is_active=True,
            )
            self.stdout.write(self.style.SUCCESS(f'Created user: {email}'))

        # Ensure currency is USD
        if user.currency_preference != 'USD':
            user.currency_preference = 'USD'
            user.save(update_fields=['currency_preference'])
            self.stdout.write('Updated currency preference to USD.')

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
        start = today - timedelta(days=59)  # 60-day window

        self.stdout.write(
            'Generating 60 days of realistic USD transaction history...')

        def tx(cat_key, amount, desc, day_offset):
            d = start + timedelta(days=day_offset)
            if d <= today:
                Transaction.objects.create(
                    user=user,
                    category=cats[cat_key],
                    amount=round(amount, 2),
                    date=d,
                    description=desc,
                )

        # ================================================================== #
        # INCOME                                                               #
        # ================================================================== #
        for offset in range(60):
            d = start + timedelta(days=offset)
            if d.day == 1 and d <= today:
                Transaction.objects.create(
                    user=user, category=cats['Salary'],
                    amount=4200.00, date=d,
                    description='Direct Deposit — Employer Payroll',
                )
            if d.day == 15 and d <= today:
                Transaction.objects.create(
                    user=user, category=cats['Salary'],
                    amount=4200.00, date=d,
                    description='Direct Deposit — Employer Payroll',
                )

        tx('Freelance', 850.00, 'Upwork — UI Design Project', 18)

        # ================================================================== #
        # MONTHLY FIXED EXPENSES                                               #
        # ================================================================== #
        for offset in range(60):
            d = start + timedelta(days=offset)
            if d.day == 1 and d <= today:
                Transaction.objects.create(
                    user=user, category=cats['Rent'],
                    amount=1850.00, date=d,
                    description='Rent — 1420 Maple Ave Apt 3B',
                )
            if d.day == 5 and d <= today:
                Transaction.objects.create(
                    user=user, category=cats['Utilities'],
                    amount=round(random.uniform(82, 118), 2), date=d,
                    description='ConEd — Electric Bill',
                )
            if d.day == 7 and d <= today:
                Transaction.objects.create(
                    user=user, category=cats['Utilities'],
                    amount=59.99, date=d,
                    description='Xfinity — Internet Service',
                )
            if d.day == 10 and d <= today:
                Transaction.objects.create(
                    user=user, category=cats['Utilities'],
                    amount=54.00, date=d,
                    description='T-Mobile — Monthly Plan',
                )
            if d.day == 3 and d <= today:
                Transaction.objects.create(
                    user=user, category=cats['Entertainment'],
                    amount=15.99, date=d,
                    description='Netflix — Monthly Subscription',
                )
            if d.day == 12 and d <= today:
                Transaction.objects.create(
                    user=user, category=cats['Entertainment'],
                    amount=9.99, date=d,
                    description='Spotify Premium',
                )
            if d.day == 20 and d <= today:
                Transaction.objects.create(
                    user=user, category=cats['Entertainment'],
                    amount=13.99, date=d,
                    description='Hulu — Monthly Subscription',
                )

        # ================================================================== #
        # DAILY EXPENSES — coffee & lunch on weekdays                         #
        # ================================================================== #
        coffee_places = [
            ('Starbucks — Caramel Macchiato', 6.45),
            ("Dunkin' Donuts — Medium Coffee", 3.79),
            ('Blue Bottle Coffee', 5.50),
            ('Starbucks — Iced Latte', 5.95),
            ('Local Café — Flat White', 4.75),
            ('Starbucks — Cold Brew', 5.25),
            ("Peet's Coffee", 4.95),
        ]
        lunch_places = [
            ('Chipotle — Burrito Bowl', 13.50),
            ('Sweetgreen — Salad', 14.50),
            ("Subway — 12'' Sub + Drink", 11.50),
            ('Panera Bread — Soup & Sandwich', 14.25),
            ('Shake Shack — Burger', 15.50),
            ('Thai Kitchen — Lunch Special', 12.50),
            ("McDonald's — Lunch Combo", 10.50),
            ('Olive Garden — Lunch Menu', 16.00),
        ]
        dinner_places = [
            ('The Capital Grille — Dinner', 68.00),
            ('Cheesecake Factory — Dinner', 42.00),
            ('Local Sushi Bar — Dinner', 48.00),
            ('Pizza Hut — Delivery', 28.00),
            ("Domino's — Pizza Order", 23.00),
            ('DoorDash — Italian Takeout', 36.00),
            ('Uber Eats — Thai Delivery', 32.00),
            ("Chili's — Dinner", 30.00),
        ]

        for offset in range(60):
            d = start + timedelta(days=offset)
            if d.weekday() < 5 and d <= today:
                if random.random() < 0.85:
                    name, price = random.choice(coffee_places)
                    Transaction.objects.create(
                        user=user, category=cats['Food'],
                        amount=round(price + random.uniform(-0.30, 0.50), 2),
                        date=d, description=name,
                    )
                if random.random() < 0.75:
                    name, price = random.choice(lunch_places)
                    Transaction.objects.create(
                        user=user, category=cats['Food'],
                        amount=round(price + random.uniform(-1.00, 2.00), 2),
                        date=d, description=name,
                    )
            if d <= today and random.random() < 0.38:
                name, price = random.choice(dinner_places)
                Transaction.objects.create(
                    user=user, category=cats['Food'],
                    amount=round(price + random.uniform(-5.00, 10.00), 2),
                    date=d, description=name,
                )

        # ================================================================== #
        # WEEKLY EXPENSES — groceries, gas, transit, rides                    #
        # ================================================================== #
        grocery_stores = [
            'Whole Foods Market',
            "Trader Joe's",
            'Costco — Weekly Groceries',
            'Kroger — Grocery Run',
            'Safeway — Weekly Shop',
            'Aldi — Grocery Run',
        ]
        for offset in range(0, 60, 7):
            d = start + timedelta(days=offset)
            if d <= today:
                Transaction.objects.create(
                    user=user, category=cats['Food'],
                    amount=round(random.uniform(72, 148), 2),
                    date=d, description=random.choice(grocery_stores),
                )
            d2 = start + timedelta(days=offset + 3)
            if d2 <= today and random.random() < 0.55:
                Transaction.objects.create(
                    user=user, category=cats['Food'],
                    amount=round(random.uniform(25, 65), 2),
                    date=d2, description=random.choice(grocery_stores),
                )
            d3 = start + timedelta(days=offset + 2)
            if d3 <= today and random.random() < 0.70:
                Transaction.objects.create(
                    user=user, category=cats['Transport'],
                    amount=round(random.uniform(42, 68), 2),
                    date=d3, description='Shell — Gas Station',
                )
            d4 = start + timedelta(days=offset + 1)
            if d4 <= today:
                Transaction.objects.create(
                    user=user, category=cats['Transport'],
                    amount=round(random.choice([2.75, 5.50, 33.00]), 2),
                    date=d4,
                    description=random.choice([
                        'MTA Metro Card Refill',
                        'NYC Transit — Weekly Pass',
                        'Metro — Single Ride',
                    ]),
                )

        ride_services = [
            ('Uber — Trip to Downtown', 16.50),
            ('Lyft — Airport Ride', 36.00),
            ('Uber — Evening Ride', 14.00),
            ('Lyft — Ride Share', 11.50),
        ]
        for offset in range(60):
            d = start + timedelta(days=offset)
            if d <= today and random.random() < 0.25:
                name, price = random.choice(ride_services)
                Transaction.objects.create(
                    user=user, category=cats['Transport'],
                    amount=round(price + random.uniform(-2, 4), 2),
                    date=d, description=name,
                )

        # ================================================================== #
        # SHOPPING                                                             #
        # ================================================================== #
        shopping_items = [
            ('Amazon — Household Supplies', 48.99),
            ('Target — Personal Care & Home', 62.50),
            ('Amazon — Book Order', 18.99),
            ('Zara — Clothing', 82.00),
            ('H&M — Seasonal Sale', 55.00),
            ('Best Buy — Phone Accessories', 38.00),
            ('Amazon — Kitchen Gadget', 42.00),
            ("Macy's — Sale Items", 75.00),
            ('IKEA — Home Decor', 65.00),
            ('Sephora — Skincare', 52.00),
            ('CVS — Personal Care', 27.50),
            ('Walgreens — Essentials', 22.00),
        ]
        for offset in range(0, 60, 5):
            d = start + timedelta(days=offset + random.randint(0, 4))
            if d <= today and random.random() < 0.55:
                name, price = random.choice(shopping_items)
                Transaction.objects.create(
                    user=user, category=cats['Shopping'],
                    amount=round(price + random.uniform(-5, 10), 2),
                    date=d, description=name,
                )

        # ================================================================== #
        # ENTERTAINMENT (non-subscription)                                    #
        # ================================================================== #
        entertainment_items = [
            ('AMC Theaters — Movie Ticket', 16.50),
            ('Live Nation — Concert Ticket', 85.00),
            ('Steam — Game Purchase', 29.99),
            ('Barnes & Noble — Books', 22.00),
            ('Eventbrite — Workshop', 45.00),
            ('Bowling Night with Friends', 26.00),
            ('Escape Room — Group Activity', 38.00),
        ]
        for offset in range(0, 60, 10):
            d = start + timedelta(days=offset + random.randint(0, 9))
            if d <= today and random.random() < 0.65:
                name, price = random.choice(entertainment_items)
                Transaction.objects.create(
                    user=user, category=cats['Entertainment'],
                    amount=round(price + random.uniform(-3, 5), 2),
                    date=d, description=name,
                )

        # ================================================================== #
        # HEALTH / MEDICAL                                                     #
        # ================================================================== #
        tx('Medical', 185.00, 'Dr. Sarah Kim — Annual Checkup (Copay)',   8)
        tx('Medical',  24.50, 'CVS Pharmacy — Vitamins & Supplements',   12)
        tx('Medical',  38.75, 'Walgreens — Cold Medicine & Allergy Rx',  31)
        tx('Medical', 160.00, 'Dental Arts NYC — Cleaning & X-Ray',      45)
        tx('Medical',  18.99, 'Amazon — Melatonin & Sleep Aids',          52)

        # ================================================================== #
        # EDUCATION                                                            #
        # ================================================================== #
        tx('Education',  29.00, 'Coursera — Monthly Subscription',        5)
        tx('Education', 199.00, 'Udemy — Data Science Bootcamp',          22)
        tx('Education',  29.00, 'Coursera — Monthly Subscription',        35)
        tx('Education',  14.99, 'Kindle — Atomic Habits (eBook)',          41)

        count = Transaction.objects.filter(user=user).count()
        self.stdout.write(self.style.SUCCESS(
            f'Done! Total transactions for {email}: {count}'
        ))
