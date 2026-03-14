import os

filepath = "./students/static/sw.js"
with open(filepath, "r") as f:
    content = f.read()

# Add /dashboard/ and /settings/ to the ignored paths list
if "/dashboard/" not in content:
    content = content.replace("url.pathname.includes('/auth/') ||", "url.pathname.includes('/auth/') ||\n        url.pathname.includes('/dashboard/') ||\n        url.pathname.includes('/settings/') ||")

with open(filepath, "w") as f:
    f.write(content)

print("Updated static/sw.js")
