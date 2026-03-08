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

        # What if it's already properly formatted but just missing from normalized_all_classes?
        if re.match(r'^\d+م\d+$', cl_norm):
             mapped_classes.append(cl_norm)
             continue

        # Heuristic extraction
        all_nums = re.findall(r'\d+', cl_orig)
        mapped_digit = None
        class_num = None

        for arb_word, digit in arabic_level_map.items():
            if arb_word in cl_orig:
                mapped_digit = digit
                break

        if mapped_digit:
             class_num = all_nums[0] if len(all_nums) > 0 else None
        else:
             if len(all_nums) >= 2:
                  mapped_digit = all_nums[0]
                  class_num = all_nums[1]
             elif len(all_nums) == 1:
                  mapped_digit = all_nums[0]
                  class_num = all_nums[0]

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
