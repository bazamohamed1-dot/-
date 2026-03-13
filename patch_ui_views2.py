with open("students/ui_views.py", "r") as f:
    content = f.read()

s1 = """        # Load user subject mappings if provided
        import json
        subject_mappings = None
        mappings_json = request.POST.get('subject_mappings')
        if mappings_json:
            try:
                subject_mappings = json.loads(mappings_json)
            except json.JSONDecodeError:
                pass"""

r1 = """        # Load user subject mappings if provided
        import json
        subject_mappings = None
        mappings_json = request.POST.get('subject_mappings')
        if mappings_json:
            try:
                subject_mappings = json.loads(mappings_json)
                # Save these mappings permanently to the database
                from .models_mapping import SubjectAlias
                for old_name, new_name in subject_mappings.items():
                    if new_name and new_name != "ignore":
                        # Create or update alias
                        SubjectAlias.objects.update_or_create(
                            alias=old_name.strip(),
                            defaults={'canonical_name': new_name.strip()}
                        )
            except json.JSONDecodeError:
                pass"""

content = content.replace(s1, r1)

with open("students/ui_views.py", "w") as f:
    f.write(content)
