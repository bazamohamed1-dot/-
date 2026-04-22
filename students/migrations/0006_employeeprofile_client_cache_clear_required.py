from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0005_alter_schoolsettings_subject_coefficients_by_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='employeeprofile',
            name='client_cache_clear_required',
            field=models.BooleanField(default=False, verbose_name='إجبار تفريغ التخزين على العميل'),
        ),
    ]
