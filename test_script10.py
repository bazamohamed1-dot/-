import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'School_Management.settings')
django.setup()

arabic_level_map = {
    'أولى': '1', 'الاولى': '1', 'الأولى': '1', 'اولى': '1',
    'ثانية': '2', 'الثانية': '2', 'ثانيه': '2', 'الثانيه': '2',
    'ثالثة': '3', 'الثالثة': '3', 'ثالثه': '3', 'الثالثه': '3',
    'رابعة': '4', 'الرابعة': '4', 'رابعه': '4', 'الرابعه': '4'
}

candidates = [
    {'name': 'Test1', 'classes': ['4م1', '4م2', '3م3', '1م4', 'أولى 2']},
]

normalized_all_classes = {'1م1': '1م1', '4م2': '4م2', '3م1': '3م1', '1م3': '1م3'}

import re
for c in candidates:
    mapped_classes = []
    for cl in c.get('classes', []):
        cl_orig = cl.strip()
        cl_norm = cl_orig.replace(" ", "")

        # Perfect Match
        if cl_norm in normalized_all_classes:
            mapped_classes.append(normalized_all_classes[cl_norm])
            continue

        # Heuristic extraction for common formats (e.g. "أولى 1", "4 متوسط 2")
        # Try finding a digit representing the class number
        match_num = re.search(r'\d+', cl_orig)
        class_num = match_num.group() if match_num else ""

        mapped_digit = None

        # Find Arabic words representing the level
        for arb_word, digit in arabic_level_map.items():
            if arb_word in cl_orig:
                mapped_digit = digit
                break

        # Or find a starting digit for the level
        if not mapped_digit:
            match_level = re.search(r'^\s*(\d)', cl_orig)
            if match_level:
                # If two digits exist in the string (e.g., "1متوسط2" -> Level 1, Class 2)
                # Ensure we don't accidentally treat class_num as mapped_digit if they are the same
                all_nums = re.findall(r'\d+', cl_orig)
                if len(all_nums) >= 2:
                     mapped_digit = all_nums[0]
                     class_num = all_nums[1]
                else:
                     mapped_digit = match_level.group(1)
                     if mapped_digit == class_num and len(cl_orig) > 1:
                         # Edge case where string is something like "أولى 1", and re.findall only saw '1'
                         pass

        if mapped_digit and class_num:
            constructed_shortcut = f"{mapped_digit}م{class_num}"
            if constructed_shortcut in normalized_all_classes:
                mapped_classes.append(normalized_all_classes[constructed_shortcut])
            else:
                mapped_classes.append(constructed_shortcut)
        else:
            mapped_classes.append(cl_orig)

    c['classes'] = mapped_classes
    print(mapped_classes)
