from django.contrib import admin
from .models_mapping import SubjectAlias, ClassAlias, ClassShortcut

admin.site.register(SubjectAlias)
admin.site.register(ClassAlias)
admin.site.register(ClassShortcut)
