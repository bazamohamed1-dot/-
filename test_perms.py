import json
import ast

def test_has_perm(perm, perms):
    if isinstance(perms, str):
        try:
            # Try parsing properly formatted JSON first
            perms_list = json.loads(perms.replace("'", '"'))
            if isinstance(perms_list, list):
                return perm in perms_list
        except Exception:
            pass

        try:
            # Try python ast literal eval for stringified python lists
            perms_list = ast.literal_eval(perms)
            if isinstance(perms_list, list):
                return perm in perms_list
        except Exception:
            pass

        # If it's a comma-separated string
        if "," in perms:
             return perm in [p.strip() for p in perms.split(',')]

        return perm in perms

    # If it is a list or other iterable
    if isinstance(perms, (list, tuple, set)):
        return perm in perms

    return False

print("Test 1 (Python string list):", test_has_perm('access_analytics', "['access_management', 'access_analytics']"))
print("Test 2 (JSON list):", test_has_perm('access_analytics', '["access_management", "access_analytics"]'))
print("Test 3 (Comma string):", test_has_perm('access_analytics', "access_management,access_analytics"))
print("Test 4 (Actual list):", test_has_perm('access_analytics', ['access_management', 'access_analytics']))
print("Test 5 (Missing string list):", test_has_perm('access_hr', "['access_management', 'access_analytics']"))
