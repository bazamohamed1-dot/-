import re

file_path = './students/templates/students/analytics.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the ternary condition for trend chart data
old_code = """
        let tLabels = Object.keys(termData).length > 1 ? Object.keys(termData) : sortedClassLabels;
        let tValues = Object.keys(termData).length > 1 ? Object.values(termData) : sortedClassLabels.map(l => classData[l]);
        let tLabelName = Object.keys(termData).length > 1 ? 'تطور المتوسط حسب الفصل' : 'مقارنة الأقسام';
        let tType = Object.keys(termData).length > 1 ? 'line' : 'bar';
"""

new_code = """
        // Always show class comparison if multiple classes exist. Only show term trend if exactly 1 class is filtered.
        const showTermTrend = Object.keys(termData).length > 1 && sortedClassLabels.length <= 1;

        let tLabels = showTermTrend ? Object.keys(termData) : sortedClassLabels;
        let tValues = showTermTrend ? Object.values(termData) : sortedClassLabels.map(l => classData[l]);
        let tLabelName = showTermTrend ? 'تطور المتوسط حسب الفصل' : 'مقارنة الأقسام';
        let tType = showTermTrend ? 'line' : 'bar';
"""

content = content.replace(old_code, new_code)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed trend chart logic in analytics.html")
