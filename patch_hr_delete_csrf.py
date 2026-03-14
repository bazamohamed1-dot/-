import os

filepath = "./students/templates/students/hr.html"
with open(filepath, "r") as f:
    content = f.read()

# Since hr_delete is triggered without csrf we should pass CSRF token or make it safe if GET
# The original was an <a> tag, meaning it was a GET request. So fetch with GET is fine and doesn't strictly need CSRF,
# but it's good practice. We'll use GET as it was initially to avoid 403.
content = content.replace("method: 'POST', // Try POST first", "method: 'GET',")

with open(filepath, "w") as f:
    f.write(content)
