from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('campaigns', '0001_initial'),
        ('analytics', '0002_automationemailclick_automationemailopen'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailbounce',
            name='campaign',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='bounces', to='campaigns.campaign',
            ),
        ),
    ]
