import re
import pandas as pd
def format_class_name(level, class_name):
    if pd.isna(level) or pd.isna(class_name):
        return f"{level} {class_name}"

    level = str(level).strip()
    class_name = str(class_name).strip()

    level_match = re.search(r'\d+', level)
    if not level_match:
        return class_name

    digits = re.findall(r'\d+', class_name)
    if len(digits) >= 2:
        return f"{digits[0]}م{digits[-1]}"
    elif len(digits) == 1:
        return f"{level_match.group()}م{digits[0]}"

    return f"{level_match.group()}م{class_name}"

print(format_class_name('1 متوسط', '1'))
print(format_class_name('1', '1AM 2'))
print(format_class_name('2AM', '2'))
print(format_class_name('3', '3 م 4'))
print(format_class_name('1', 'Section A'))
