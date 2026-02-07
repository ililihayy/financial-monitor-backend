# Generated migration for adding is_active field to Category

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0001_initial'),
    ]

    operations = [
        # Add is_active field to Category
        migrations.AddField(
            model_name='category',
            name='is_active',
            field=models.BooleanField(
                default=True,
                help_text='Whether this category is active and can be used for new transactions.',
                verbose_name='Is Active'
            ),
        ),
    ]
