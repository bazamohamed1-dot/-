from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0006_employeeprofile_client_cache_clear_required'),
    ]

    operations = [
        migrations.AddField(
            model_name='canteenattendance',
            name='registration_method',
            field=models.CharField(
                choices=[('scan', 'مسح البطاقة'), ('manual', 'إدخال يدوي')],
                default='scan',
                max_length=20,
                verbose_name='طريقة التسجيل',
            ),
        ),
        migrations.AddField(
            model_name='schoolsettings',
            name='canteen_meals_by_date',
            field=models.JSONField(blank=True, default=dict, verbose_name='وصف الوجبات حسب اليوم'),
        ),
        migrations.CreateModel(
            name='CanteenDailySummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(unique=True, verbose_name='التاريخ')),
                ('meal_description', models.TextField(blank=True, verbose_name='مكونات الوجبة')),
                ('student_count', models.PositiveIntegerField(default=0, verbose_name='عدد التلاميذ')),
                ('supervisors_count', models.PositiveIntegerField(default=0, verbose_name='المشرفون المرافقون')),
                ('staff_count', models.PositiveIntegerField(default=0, verbose_name='الموظفون')),
                ('teachers_count', models.PositiveIntegerField(default=0, verbose_name='الأساتذة')),
                ('workers_count', models.PositiveIntegerField(default=0, verbose_name='العمال')),
                ('guests_count', models.PositiveIntegerField(default=0, verbose_name='الضيوف')),
                ('notes', models.TextField(blank=True, verbose_name='ملاحظات')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'ملخص يومي للمطعم',
                'verbose_name_plural': 'ملخصات المطعم اليومية',
                'ordering': ['-date'],
            },
        ),
    ]
