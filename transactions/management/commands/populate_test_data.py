import random
from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from accounts.models import CustomUser
from transactions.models import Category, Transaction

class Command(BaseCommand):
    help = 'Заповнює базу реалістичними даними з "фінансовим хаосом"'

    def add_arguments(self, parser):
        # Додаємо підтримку прапорця --clear
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистити базу перед заповненням',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Очищення бази даних...')
            Transaction.objects.all().delete()

        email = 'john.doe@example.com'
        user, created = CustomUser.objects.get_or_create(
            email=email,
            defaults={
                'nickname': 'JohnDoe',
                'currency_preference': 'USD',
                'is_active': True
            }
        )

        # Створюємо або отримуємо категорії
        def get_cat(name, c_type, icon):
            return Category.objects.get_or_create(
                name=name, user=None, 
                defaults={'type': c_type, 'icon_identifier': icon}
            )[0]

        cats = {
            'Salary': get_cat('Salary', 'Income', 'Briefcase'),
            'Rent': get_cat('Rent', 'Expense', 'Home'),
            'Food': get_cat('Food', 'Expense', 'UtensilsCrossed'),
            'Medical': get_cat('Medical', 'Expense', 'Heart'),
            'Vacation': get_cat('Vacation', 'Expense', 'Plane'),
            'Shopping': get_cat('Shopping', 'Expense', 'ShoppingBag'),
        }

        today = date.today()
        self.stdout.write('Генерація 12 місяців "життя"...')

        for m in range(12, -1, -1):
            # Розраховуємо дату початку місяця
            month_start = (today.replace(day=1) - timedelta(days=m * 30.44)).replace(day=1)
            
            # --- 1. Стабільні потоки ---
            Transaction.objects.create(user=user, category=cats['Salary'], amount=5500, 
                                     date=month_start + timedelta(days=0), description="Зарплата")
            Transaction.objects.create(user=user, category=cats['Rent'], amount=1300, 
                                     date=month_start + timedelta(days=1), description="Оренда")

            # --- 2. Щоденна рутина (Food) ---
            for _ in range(random.randint(12, 18)):
                Transaction.objects.create(
                    user=user, category=cats['Food'],
                    amount=random.randint(25, 85),
                    date=month_start + timedelta(days=random.randint(2, 27)),
                    description="Супермаркет"
                )

            # --- 3. АНОМАЛІЇ (Те, що створює сигму для Монте-Карло) ---
            # Відпустка (раз на пів року)
            if m in [1, 7]:
                Transaction.objects.create(user=user, category=cats['Vacation'], 
                                         amount=random.randint(1800, 3000), 
                                         date=month_start + timedelta(days=10), 
                                         description="Відпустка (квитки/готель)")

            # Лікування (випадково, раз на кілька місяців)
            if random.random() < 0.25:
                Transaction.objects.create(user=user, category=cats['Medical'], 
                                         amount=random.randint(400, 1200), 
                                         date=month_start + timedelta(days=15), 
                                         description="Стоматологія/Чекап")

            # Дні народження / Подарунки
            if random.random() < 0.3:
                Transaction.objects.create(user=user, category=cats['Shopping'], 
                                         amount=random.randint(300, 700), 
                                         date=month_start + timedelta(days=20), 
                                         description="Подарунок на ДН")

        self.stdout.write(self.style.SUCCESS("База заповнена реалістичним хаосом!"))