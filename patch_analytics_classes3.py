with open('students/templates/students/analytics.html', 'r') as f:
    lines = f.readlines()

out = []
in_classes_html = False
in_fallback = False

for line in lines:
    if "let classesHtml = '';" in line:
        in_classes_html = True
        out.append(line)
        out.append("""
        const teacherSelect = document.getElementById('teacherSelect');
        const opt = teacherSelect.options[teacherSelect.selectedIndex];

        let hrAssignedClasses = [];
        try {
            const hrAssignmentsRaw = JSON.parse(opt.getAttribute('data-hr-assignments') || '[]');
            hrAssignmentsRaw.forEach(assignment => {
                hrAssignedClasses = hrAssignedClasses.concat(assignment.classes);
            });
        } catch(e) {}

        const formatClassCode = (c) => {
             let cStr = String(c).trim();
             if (cStr.match(/^\\d+م\\d+$/)) return cStr;
             let level = '';
             if (cStr.includes('أولى') || cStr.includes('1')) level = '1';
             else if (cStr.includes('ثانية') || cStr.includes('2')) level = '2';
             else if (cStr.includes('ثالثة') || cStr.includes('3')) level = '3';
             else if (cStr.includes('رابعة') || cStr.includes('4')) level = '4';

             let numMatch = cStr.match(/(\\d+)$/);
             let num = numMatch ? numMatch[1] : '1';
             if (level && num) return `${level}م${num}`;
             return cStr;
        };

        const shortHrClasses = hrAssignedClasses.map(formatClassCode);
        const shortAssignedClasses = classesArray.map(formatClassCode);

        let combinedClasses = [...new Set([...shortHrClasses, ...shortAssignedClasses])];

        combinedClasses.sort((a, b) => {
            let m1 = a.match(/(\\d+)م(\\d+)/);
            let m2 = b.match(/(\\d+)م(\\d+)/);
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
        });
""")
        continue

    if in_classes_html:
        if "let subjectOptions =" in line:
            in_classes_html = False
            out.append(line)
        continue

    if "if (assignments.length === 0) {" in line:
        in_fallback = True
        out.append(line)
        out.append("""
            if (hrAssignments && hrAssignments.length > 0) {
                hrAssignments.forEach(ha => {
                    let subj = ha.subject || '';
                    if (subj === '/' || subj === 'بدون') subj = '';
                    addAnalyticsAssignmentBlock(subj, ha.classes);
                });
            } else {
                addAnalyticsAssignmentBlock('', []);
            }
""")
        continue

    if in_fallback:
        if "} else {" in line:
            in_fallback = False
            out.append(line)
        continue

    out.append(line)

with open('students/templates/students/analytics.html', 'w') as f:
    f.writelines(out)
