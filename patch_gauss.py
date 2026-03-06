import re

with open('students/templates/students/advanced_analytics.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add updateGaussClassDropdown and updateGaussChart
new_funcs = """
    function updateGaussClassDropdown() {
        const levelSelect = document.getElementById('gaussLevelSelector');
        const classSelect = document.getElementById('gaussClassSelector');
        const selectedLvl = levelSelect.value;

        classSelect.innerHTML = '<option value="">كل الأقسام</option>';

        if (selectedLvl && classMap[selectedLvl]) {
            let classesToShow = [...new Set(classMap[selectedLvl])].sort((a, b) => {
                 const numA = parseInt(a.replace(/\\D/g, '')) || 0;
                 const numB = parseInt(b.replace(/\\D/g, '')) || 0;
                 if (numA === numB) return a.localeCompare(b);
                 return numA - numB;
            });

            classesToShow.forEach(cls => {
                const opt = document.createElement('option');
                opt.value = cls;
                opt.textContent = cls;
                classSelect.appendChild(opt);
            });
        }

        updateGaussChart();
    }

    async function updateGaussChart() {
        const level = document.getElementById('gaussLevelSelector').value;
        const className = document.getElementById('gaussClassSelector').value;

        try {
            const response = await fetch(`/canteen/analytics/gauss_data/?level=${encodeURIComponent(level)}&class_name=${encodeURIComponent(className)}`);
            if (response.ok) {
                const data = await response.json();
                renderGaussChart(data);
            }
        } catch (error) {
            console.error("Error fetching gauss stats:", error);
        }
    }
"""

if 'function updateGaussClassDropdown' not in content:
    content = content.replace('function renderGaussChart', new_funcs + '\n    function renderGaussChart')

with open('students/templates/students/advanced_analytics.html', 'w', encoding='utf-8') as f:
    f.write(content)
