import re

def format_class_name(level, class_name):
    level = str(level).strip()
    class_name = str(class_name).strip()

    # Try to extract the numeric level
    level_match = re.search(r'\d+', level)
    class_match = re.search(r'\d+', class_name)

    if level_match and class_match:
        # Check if the class name already has the level embedded (like "1AM 1")
        if re.search(r'^\d+\s*[A-Za-zم\s]+\s*\d+$', class_name):
            # Already seems to have a level and a class number. Let's just use it as is or try to extract.
            # actually to be consistent, we can just say `LمC`
            c_num = class_match.group()
            # If the class_name is something like "1AM 2" then the first digit is 1, second is 2
            digits = re.findall(r'\d+', class_name)
            if len(digits) >= 2:
                # probably level and class
                return f"{digits[0]}م{digits[1]}"
            else:
                return f"{level_match.group()}م{digits[0]}"
        return f"{level_match.group()}م{class_match.group()}"
    return f"{level} {class_name}"

print(format_class_name('1 متوسط', '1'))
print(format_class_name('1', '1AM 2'))
print(format_class_name('2AM', '2'))
print(format_class_name('3', '3 م 4'))
