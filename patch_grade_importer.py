import re

filepath = "./students/grade_importer.py"
with open(filepath, "r") as f:
    content = f.read()

# Fix the condition that excludes subjects shorter than 4 characters (e.g. "الرسم" is 5 chars so it should pass, but what if there's a weird mapping?)
# The user mentioned "الرسم" was extracted EVEN THOUGH it was NOT in the file.
# This means difflib is mapping some random column header (e.g. "الرقم", "المعدل", "المجموع") to "الرسم".
# Let's increase the cutoff for difflib to 0.85 to make it stricter and avoid false positives.

content = content.replace("matches = difflib.get_close_matches(mapped_subject, known_subjects, n=1, cutoff=0.7)",
                          "matches = difflib.get_close_matches(mapped_subject, known_subjects, n=1, cutoff=0.85)")

# Add "ت البدنية والرياضية", "التربية البدنية والرياضية" to known_subjects
if "'التربية البدنية والرياضية'" not in content:
    content = content.replace("'التربية البدنية', 'الرياضة',",
                              "'التربية البدنية', 'التربية البدنية والرياضية', 'ت البدنية والرياضية', 'الرياضة',")

# Fix the len(final_subject) > 3 filter which might exclude short valid subjects or allow bad ones.
# Also add 'المجموع', 'المعدل' to the exclude list so they don't get fuzzy matched to subjects.
content = content.replace("['الرقم', 'رقم', 'الملاحظة', 'التقدير', 'الغياب', 'المواظبة', 'اللقبوالاسم', 'الاسمواللقب']",
                          "['الرقم', 'رقم', 'الملاحظة', 'التقدير', 'الغياب', 'المواظبة', 'اللقبوالاسم', 'الاسمواللقب', 'المجموع', 'المعدل', 'معدل', 'المجموع العام', 'القرار']")

# In the second loop (fallback if len == 0), it doesn't do difflib, but let's make sure it excludes non-subjects
content = content.replace("elif mapped_subject and mapped_subject != '':\n                subject_indices_multi[(mapped_subject, col_term)] = idx",
                          "elif mapped_subject and mapped_subject != '' and len(mapped_subject) > 2 and mapped_subject not in ['الرقم', 'رقم', 'الملاحظة', 'التقدير', 'الغياب', 'المواظبة', 'اللقبوالاسم', 'الاسمواللقب', 'المجموع', 'المعدل', 'معدل', 'المجموع العام', 'القرار']:\n                subject_indices_multi[(mapped_subject, col_term)] = idx")


with open(filepath, "w") as f:
    f.write(content)

print("Updated grade_importer.py")
