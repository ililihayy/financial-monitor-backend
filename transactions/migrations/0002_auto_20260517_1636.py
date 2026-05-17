from django.db import migrations
from accounts.services.encryption_service import EncryptionService


def add_default_categories(apps, schema_editor):
    # Retrieve the historical version of the Category model
    Category = apps.get_model('transactions', 'Category')

    # List of default system-wide categories in English
    # Format: (Name, Django Category Type, Frontend Icon Identifier)
    default_categories = [
        ('Groceries', 'Expense', 'UtensilsCrossed'),
        ('Transport', 'Expense', 'Car'),
        ('Utilities', 'Expense', 'Zap'),
        ('Entertainment', 'Expense', 'Film'),
        ('Shopping', 'Expense', 'ShoppingBag'),
        ('Healthcare', 'Expense', 'Heart'),
        ('Salary', 'Income', 'Briefcase'),
        ('Freelance & Investments', 'Income', 'TrendingUp'),
        ('Gifts', 'Income', 'Gift'),
    ]

    for name, cat_type, icon in default_categories:
        # Encrypt the English name before storing it, as the database expects AES-GCM cipher text
        encrypted_name = EncryptionService.encrypt(name)

        # user=None defines this row as a system-default category accessible by all users
        Category.objects.get_or_create(
            name=encrypted_name,
            type=cat_type,
            user=None,
            defaults={'icon_identifier': icon}
        )


def remove_default_categories(apps, schema_editor):
    Category = apps.get_model('transactions', 'Category')
    # Clean up system-default categories if this migration is ever rolled back
    Category.objects.filter(user=None).delete()


class Migration(migrations.Migration):

    dependencies = [
        # This must match the name of your initial migration file
        ('transactions', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_default_categories,
                             remove_default_categories),
    ]
