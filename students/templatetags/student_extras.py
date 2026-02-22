from django import template
import re

register = template.Library()

@register.filter
def strip_level_from_class(class_name, level):
    """
    Strips the level from the class name robustly.
    Example: "1AM 1" with level "1AM" -> "1"
    """
    if not class_name or not level:
        return class_name

    # Escape special regex chars in level just in case
    level_escaped = re.escape(str(level))

    # Pattern: Level at start, followed by optional spaces
    # Case insensitive
    pattern = re.compile(f"^{level_escaped}\s*", re.IGNORECASE)

    return pattern.sub('', str(class_name)).strip()
