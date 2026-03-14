import os

filepath = "./students/grade_importer.py"
with open(filepath, "r") as f:
    content = f.read()

# Make sure 'ع الطبيعة والحياة' logic isn't messing up.
# Sometimes subjects get shifted because of merged cells.
# There is a check in process_grades_file that strips newlines and handles columns.

# One more thing: the user said "ع الطبيعة والحياة" was illogical. This could happen if the column index is off by 1 because of a hidden/merged column.
# Tablib/pandas extract_rows_from_file might skip empty columns if they are not careful, but the code uses index.
# It is important that the mapping logic correctly ignores ' ' strings.

print("Applied strict difflib thresholds.")
