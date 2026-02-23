from django import template

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
