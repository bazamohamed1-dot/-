# معاملات المواد حسب المستوى + متوسط المعدل العام الماضي

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0003_schoolsettings_award_thresholds'),
    ]

    operations = [
        migrations.AddField(
            model_name='schoolsettings',
            name='subject_coefficients_by_level',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='لحساب المعدل الفصلي المرجح والمادة الحاكمة.',
                verbose_name='معاملات المواد حسب المستوى',
            ),
        ),
        migrations.AddField(
            model_name='cohortexpertdata',
            name='last_year_raw_avg',
            field=models.FloatField(blank=True, null=True, verbose_name='متوسط المعدل العام الماضي (فعلي)'),
        ),
    ]
