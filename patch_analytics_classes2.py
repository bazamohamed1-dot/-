import re
with open('students/templates/students/analytics.html', 'r') as f:
    content = f.read()

# I will use a regex replace because the previous python script failed to find the exact string
# due to python string raw escaping issues or string mismatches.

search_str = r"let classesHtml = '';(.*?)classesHtml \+= `(.*?)`;\s*\}\);"

replace_str = r"""let classesHtml = '';

        const teacherSelect = document.getElementById('teacherSelect');
        const opt = teacherSelect.options[teacherSelect.selectedIndex];

        let hrAssignedClasses = [];
        let defaultSubj = subject;
        try {
            const hrAssignmentsRaw = JSON.parse(opt.getAttribute('data-hr-assignments') || '[]');
            hrAssignmentsRaw.forEach(assignment => {
                hrAssignedClasses = hrAssignedClasses.concat(assignment.classes);
                if (!defaultSubj && assignment.subject && assignment.subject !== '/') {
                     defaultSubj = assignment.subject;
                }
            });
        } catch(e) {}

        const formatClassCode = (c) => {
             let cStr = String(c).trim();

             // Already formatted?
             if (cStr.match(/^\d+م\d+$/)) return cStr;

             let level = '';
             if (cStr.includes('أولى') || cStr.includes('1')) level = '1';
             else if (cStr.includes('ثانية') || cStr.includes('2')) level = '2';
             else if (cStr.includes('ثالثة') || cStr.includes('3')) level = '3';
             else if (cStr.includes('رابعة') || cStr.includes('4')) level = '4';

             let numMatch = cStr.match(/(\d+)$/);
             let num = numMatch ? numMatch[1] : '1';

             if (level && num) return `${level}م${num}`;
             return cStr;
        };

        const shortHrClasses = hrAssignedClasses.map(formatClassCode);
        const shortAssignedClasses = classesArray.map(formatClassCode);

        let combinedClasses = [...new Set([...shortHrClasses, ...shortAssignedClasses])];

        combinedClasses.sort((a, b) => {
            let m1 = a.match(/(\d+)م(\d+)/);
            let m2 = b.match(/(\d+)م(\d+)/);
            if (m1 && m2) {
                if (parseInt(m1[1]) !== parseInt(m2[1])) return parseInt(m1[1]) - parseInt(m2[1]);
                return parseInt(m1[2]) - parseInt(m2[2]);
            }
            return a.localeCompare(b, 'ar');
        });

        combinedClasses.forEach(c => {
            const isChecked = shortAssignedClasses.includes(c) ? 'checked' : '';
            classesHtml += `
                <div class="form-check form-check-inline" style="margin-left:15px; margin-bottom:10px;">
                    <input class="form-check-input dyn-class-cb" type="checkbox" value="${c}" ${isChecked} id="chk_${c}">
                    <label class="form-check-label font-weight-bold" for="chk_${c}" style="font-size: 1.1rem; color: #2c3e50;">${c}</label>
                </div>
            `;
        });"""

content = re.sub(search_str, replace_str, content, flags=re.DOTALL)


# Now fix the empty default to load from HR properly
fallback_search = r"if \(assignments\.length === 0\) \{.*?\} else \{"
fallback_replace = r"""if (assignments.length === 0) {
            if (hrAssignments && hrAssignments.length > 0) {
                hrAssignments.forEach(ha => {
                    let subj = ha.subject || '';
                    if (subj === '/' || subj === 'بدون') subj = '';
                    addAnalyticsAssignmentBlock(subj, ha.classes);
                });
            } else {
                addAnalyticsAssignmentBlock('', []);
            }
        } else {"""

content = re.sub(fallback_search, fallback_replace, content, flags=re.DOTALL)

with open('students/templates/students/analytics.html', 'w') as f:
    f.write(content)
