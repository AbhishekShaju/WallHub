# Generated by Django 5.0.2 on 2025-04-01 13:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_remove_wallpaper_category_alter_wallpaper_options_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='purchase',
            name='invoice_number',
        ),
        migrations.RemoveField(
            model_name='purchase',
            name='razorpay_order_id',
        ),
        migrations.RemoveField(
            model_name='purchase',
            name='razorpay_payment_id',
        ),
        migrations.RemoveField(
            model_name='purchase',
            name='razorpay_signature',
        ),
        migrations.AlterField(
            model_name='purchase',
            name='transaction_id',
            field=models.CharField(max_length=100),
        ),
    ]
