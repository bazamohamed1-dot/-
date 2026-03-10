import re

with open('students/models.py', 'r') as f:
    content = f.read()

new_has_perm = """    def has_perm(self, perm):
        if self.role == 'director' or self.user.is_superuser:
            return True

        if isinstance(self.permissions, str):
            import json
            import ast
            try:
                perms_list = json.loads(self.permissions.replace("'", '"'))
                if isinstance(perms_list, list):
                    return perm in perms_list
            except Exception:
                pass

            try:
                perms_list = ast.literal_eval(self.permissions)
                if isinstance(perms_list, list):
                    return perm in perms_list
            except Exception:
                pass

            if "," in self.permissions:
                return perm in [p.strip() for p in self.permissions.split(',')]

            return perm in self.permissions

        if isinstance(self.permissions, (list, tuple, set)):
            return perm in self.permissions

        return False"""

# Replace the old has_perm block
old_has_perm_pattern = re.compile(r'    def has_perm\(self, perm\):.*?(?=\n    def __str__\(self\):)', re.DOTALL)
content = old_has_perm_pattern.sub(new_has_perm + "\n", content)

with open('students/models.py', 'w') as f:
    f.write(content)

print("Updated students/models.py")
