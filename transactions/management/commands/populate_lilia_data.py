import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from accounts.models import CustomUser
from transactions.models import Category, Transaction


class Command(BaseCommand):
    help = 'Fills liliapush04@gmail.com with realistic test expense/income data'

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
                currency_preference='UAH',
                is_active=True,
            )
            self.stdout.write(self.style.SUCCESS(f'Created user: {email}'))

        if options['clear']:
            deleted, _ = Transaction.objects.filter(user=user).delete()
            self.stdout.write(f'Deleted {deleted} existing transactions.')

        # System-default categories (user=None)
        def get_cat(name, c_type, icon):
            return Category.objects.get_or_create(
                name=name,
                user=None,
                defaults={'type': c_type, 'icon_identifier': icon},
            )[0]

        cats = {
            'Salary':      get_cat('Salary',      'Income',  'Briefcase'),
            'Freelance':   get_cat('Freelance',   'Income',  'Laptop'),
            'Rent':        get_cat('Rent',        'Expense', 'Home'),
            'Food':        get_cat('Food',        'Expense', 'UtensilsCrossed'),
            'Transport':   get_cat('Transport',   'Expense', 'Car'),
            'Shopping':    get_cat('Shopping',    'Expense', 'ShoppingBag'),
            'Medical':     get_cat('Medical',     'Expense', 'Heart'),
            'Utilities':   get_cat('Utilities',   'Expense', 'Zap'),
            'Entertainment': get_cat('Entertainment', 'Expense', 'Music'),
            'Vacation':    get_cat('Vacation',    'Expense', 'Plane'),
            'Education':   get_cat('Education',   'Expense', 'BookOpen'),
            'Beauty':      get_cat('Beauty',      'Expense', 'Sparkles'),
        }

        today = date.today()
        self.stdout.write('Generating 12 months of transaction history...')

        for m in range(12, -1, -1):
            month_start = (today.replace(day=1) -
                           timedelta(days=m * 30.44)).replace(day=1)

            # --- Income ---
            Transaction.objects.create(
                user=user, category=cats['Salary'],
                amount=18500,
                date=month_start + timedelta(days=0),
                description='Monthly salary',
            )
            if random.random() < 0.45:
                Transaction.objects.create(
                    user=user, category=cats['Freelance'],
                    amount=random.randint(2000, 6000),
                    date=month_start + timedelta(days=random.randint(5, 20)),
                    description='Freelance project payment',
                )

            # --- Fixed expenses ---
            Transaction.objects.create(
                user=user, category=cats['Rent'],
                amount=7500,
                date=month_start + timedelta(days=1),
                description='Apartment rent',
            )
            Transaction.objects.create(
                user=user, category=cats['Utilities'],
                amount=random.randint(900, 1800),
                date=month_start + timedelta(days=3),
                description='Utilities (electricity, water, internet)',
            )

            # --- Food (daily routine) ---
            for _ in range(random.randint(14, 22)):
                Transaction.objects.create(
                    user=user, category=cats['Food'],
                    amount=random.randint(120, 480),
                    date=month_start + timedelta(days=random.randint(0, 27)),
                    description=random.choice([
                        'Grocery store', 'Cafe', 'Restaurant',
                        'Supermarket', 'Bakery', 'Coffee',
                    ]),
                )

            # --- Transport ---
            for _ in range(random.randint(8, 15)):
                Transaction.objects.create(
                    user=user, category=cats['Transport'],
                    amount=random.randint(40, 350),
                    date=month_start + timedelta(days=random.randint(0, 27)),
                    description=random.choice([
                        'Taxi', 'Metro/bus pass', 'Fuel', 'Ride-share',
                    ]),
                )

            # --- Beauty & personal care ---
            if random.random() < 0.7:
                Transaction.objects.create(
                    user=user, category=cats['Beauty'],
                    amount=random.randint(300, 1200),
                    date=month_start + timedelta(days=random.randint(5, 25)),
                    description=random.choice([
                        'Hair salon', 'Nail studio', 'Cosmetics', 'Skincare',
                    ]),
                )

            # --- Shopping ---
            for _ in range(random.randint(1, 4)):
                Transaction.objects.create(
                    user=user, category=cats['Shopping'],
                    amount=random.randint(200, 2500),
                    date=month_start + timedelta(days=random.randint(0, 27)),
                    description=random.choice([
                        'Clothing', 'Online order', 'Home goods',
                        'Electronics accessory', 'Gift',
                    ]),
                )

            # --- Entertainment ---
            for _ in range(random.randint(1, 3)):
                Transaction.objects.create(
                    user=user, category=cats['Entertainment'],
                    amount=random.randint(100, 600),
                    date=month_start + timedelta(days=random.randint(0, 27)),
                    description=random.choice([
                        'Cinema', 'Concert', 'Streaming subscription',
                        'Books', 'Board games night',
                    ]),
                )

            # --- Education (occasional) ---
            if random.random() < 0.35:
                Transaction.objects.create(
                    user=user, category=cats['Education'],
                    amount=random.randint(500, 2500),
                    date=month_start + timedelta(days=random.randint(5, 20)),
                    description=random.choice([
                        'Online course', 'Language class', 'Workshop', 'Textbooks',
                    ]),
                )

            # --- Medical (occasional) ---
            if random.random() < 0.25:
                Transaction.objects.create(
                    user=user, category=cats['Medical'],
                    amount=random.randint(300, 1500),
                    date=month_start + timedelta(days=random.randint(5, 25)),
                    description=random.choice([
                        'Doctor visit', 'Pharmacy', 'Dentist', 'Lab tests',
                    ]),
                )

            # --- Vacation (twice a year anomaly) ---
            if m in [1, 6]:
                Transaction.objects.create(
                    user=user, category=cats['Vacation'],
                    amount=random.randint(8000, 22000),
                    date=month_start + timedelta(days=12),
                    description='Vacation (flights + hotel)',
                )

        count = Transaction.objects.filter(user=user).count()
        self.stdout.write(self.style.SUCCESS(
            f'Done! Created data for {email}. Total transactions: {count}'
        ))
