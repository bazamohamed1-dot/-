from django.db.models import Transform
from django.db.models.lookups import IContains
import re

# Custom Lookup for Arabic Normalization (Optional but ideal if DB supports it)
# SQLite doesn't natively support complex string manip inside queries easily without custom functions.
# Instead, we will normalize the query and use Q objects for variations OR implement a Python-side filter if dataset is small.
# Given the likely dataset size (few thousands), a robust Q object approach is safer and portable.

def normalize_arabic(text):
    if not text:
        return ""
    text = re.sub("[أإآ]", "ا", text)
    text = re.sub("ة", "ه", text)
    text = re.sub("ى", "ي", text)
    # Remove Tashkeel
    text = re.sub("[\u064B-\u065F]", "", text)
    return text

def get_arabic_variations(text):
    """
    Returns a list of regex patterns or strings to search for,
    accounting for common Arabic misspellings/variations.
    """
    if not text:
        return []

    # Base normalization
    norm = normalize_arabic(text)

    # Generate variations for specific chars
    # This is complex to do purely with Q objects for every char.
    # A simpler approach: Search for the normalized version AND the original.
    # But strict normalization on both sides (DB and Query) is best.
    # Since we can't easily normalize DB side in SQLite without custom function,
    # we will construct a regex or multiple Qs.

    return [text, norm]
