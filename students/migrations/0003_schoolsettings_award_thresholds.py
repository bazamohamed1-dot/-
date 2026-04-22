# Generated manually for award thresholds

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0002_alter_subjectexemptionrule_scope_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='schoolsettings',
            name='award_thresholds',
            field=models.JSONField(blank=True, default=dict, help_text='مثال: {"امتياز": 16, "تهنئة": 14, "تشجيع": 12, "لوحة شرف": 10}', verbose_name='مجالات الإجازات (أدنى معدل فصلي)'),
        ),
    ]
