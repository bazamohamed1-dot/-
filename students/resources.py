from import_export import resources, fields
from import_export.widgets import DateWidget
from .models import Student

class StudentResource(resources.ModelResource):
    # Map fields explicitly to ensure control, though automatic mapping works if names match
    student_id_number = fields.Field(attribute='student_id_number', column_name='student_id_number')
    last_name = fields.Field(attribute='last_name', column_name='last_name')
    first_name = fields.Field(attribute='first_name', column_name='first_name')
    gender = fields.Field(attribute='gender', column_name='gender')

    # Date fields need widgets if the format varies, but we will pre-parse dates in utils
    # so they come as date objects or ISO strings which import-export handles well.
    date_of_birth = fields.Field(attribute='date_of_birth', column_name='date_of_birth')
    place_of_birth = fields.Field(attribute='place_of_birth', column_name='place_of_birth')
    academic_year = fields.Field(attribute='academic_year', column_name='academic_year')
    class_name = fields.Field(attribute='class_name', column_name='class_name')
    attendance_system = fields.Field(attribute='attendance_system', column_name='attendance_system')
    enrollment_number = fields.Field(attribute='enrollment_number', column_name='enrollment_number')
    enrollment_date = fields.Field(attribute='enrollment_date', column_name='enrollment_date')

    class Meta:
        model = Student
        exclude = ('id',)
        import_id_fields = ('student_id_number',)
        skip_unchanged = True
        report_skipped = True
        use_bulk = True
        batch_size = 1000
