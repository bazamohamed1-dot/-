import re

with open('students/ui_views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the block that filters class_map in analytics_dashboard to be more robust for Arabic levels
new_filter_block = """
        filtered_class_map = {}
        for lvl, clist in class_map.items():
            valid_cls = []
            for c in clist:
                from .analytics_utils import unformat_class_name
                import re

                # Extract digits to make robust comparison
                lvl_digit = "1"
                if "ثانية" in lvl or "2" in lvl: lvl_digit = "2"
                elif "ثالثة" in lvl or "3" in lvl: lvl_digit = "3"
                elif "رابعة" in lvl or "4" in lvl: lvl_digit = "4"

                cls_digit = "1"
                m_cls = re.search(r'\\\\d+', c)
                if m_cls:
                    cls_digit = m_cls.group()

                short_c = f"{lvl_digit}م{cls_digit}"

                raw_c = unformat_class_name(c)

                if c in teacher_classes or raw_c in teacher_classes or short_c in teacher_classes or (locals().get('full_class_names') and c in full_class_names):
                    valid_cls.append(c)

            if valid_cls:
                filtered_class_map[lvl] = valid_cls
"""

pattern = re.compile(r'        filtered_class_map = \{\}.*?filtered_class_map\[lvl\] = valid_cls', re.DOTALL)
content = pattern.sub(new_filter_block.strip() + "\n", content)

with open('students/ui_views.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated ui_views.py class_map filter logic")
