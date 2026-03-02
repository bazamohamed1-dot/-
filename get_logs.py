with open('django.log', 'r') as f:
    lines = f.readlines()

# Find the last Exception traceback
import sys
for i in range(len(lines)-1, -1, -1):
    if "Traceback" in lines[i]:
        print("".join(lines[i-2:]))
        sys.exit(0)
