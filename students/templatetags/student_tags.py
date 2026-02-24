from django import template
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model
from django.forms.models import model_to_dict

register = template.Library()

@register.filter
def has_perm(user_or_profile, perm_name):
    """
    Template filter to check if a user or profile has a specific permission.
    Usage: {% if request.user.profile|has_perm:'access_hr' %}
    """
    if not user_or_profile:
        return False

    # Handle User object (check if profile exists)
    if hasattr(user_or_profile, 'profile'):
        return user_or_profile.profile.has_perm(perm_name)

    # Handle EmployeeProfile object
    if hasattr(user_or_profile, 'has_perm'):
        return user_or_profile.has_perm(perm_name)

    return False

@register.filter
def safe_json(value):
    """
    Safely serializes a value (model or dict) to JSON string for use in JS.
    """
    if isinstance(value, Model):
        # Convert model to dict
        data = model_to_dict(value)
        # Handle fields that model_to_dict might miss or handle poorly (like ImageField)
        if hasattr(value, 'photo') and value.photo:
            try:
                data['photo_url'] = value.photo.url
            except:
                data['photo_url'] = ""
        # Date fields need string conversion handled by DjangoJSONEncoder
        return json.dumps(data, cls=DjangoJSONEncoder)

    return json.dumps(value, cls=DjangoJSONEncoder)
