from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_merge_20241003_0307'),  # Make sure this matches your last migration
    ]

    operations = [
        migrations.RunSQL(
            "DROP TABLE IF EXISTS core_asset CASCADE;",
            reverse_sql=migrations.RunSQL.noop
        ),
        migrations.CreateModel(
            name='Asset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('asset_number', models.CharField(editable=False, max_length=255, unique=True)),
                ('asset_type', models.CharField(choices=[('hotel', 'Hotel'), ('vehicle', 'Vehicle')], max_length=10)),
                ('asset_name', models.CharField(max_length=100)),
                ('location', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('total_revenue', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('details', models.JSONField()),
                ('account_number', models.CharField(max_length=10)),
                ('bank', models.CharField(max_length=20)),
            ],
        ),
    ]
