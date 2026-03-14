with open('students/templates/students/analytics.html', 'r') as f:
    content = f.read()

# Modify addAnalyticsAssignmentBlock
search_block = """        let classesHtml = '';
        const allGlobalClasses = {{ class_map_json|safe }};
        let flatClasses = [];
        Object.values(allGlobalClasses).forEach(arr => flatClasses = flatClasses.concat(arr));

        // Remove duplicates and map to format like "1م1"
        let cleanGlobal = [...new Set(flatClasses)].map(c => {
             let m = c.match(/(\d+)\s*متوسط\s*(\d+)/);
             if (m) return `${m[1]}م${m[2]}`;
             return c;
        });

        const cleanClasses = classesArray.map(c => c.trim().replace(/\s+/g, ''));
        const combinedClasses = [...new Set([...cleanGlobal, ...cleanClasses])].sort();

        combinedClasses.forEach(c => {
            const isChecked = cleanClasses.includes(c) ? 'checked' : '';
            classesHtml += `
                <div class="form-check" style="display:inline-block; margin-left:15px; margin-bottom:5px;">
                    <input class="form-check-input dyn-class-cb" type="checkbox" value="${c}" ${isChecked}>
                    <label class="form-check-label">${c}</label>
                </div>
            `;
        });"""

replace_block = """        let classesHtml = '';

        // 1. Fetch available class codes from the backend context
        // {{ class_list|safe_json|safe }} or we can use the HR assigned classes if we prefer,
        // but the user wants them pre-filled with format "4م1"
        const teacherSelect = document.getElementById('teacherSelect');
        const opt = teacherSelect.options[teacherSelect.selectedIndex];

        // Retrieve HR assigned classes for this teacher
        let hrAssignedClasses = [];
        try {
            const hrAssignmentsRaw = JSON.parse(opt.getAttribute('data-hr-assignments') || '[]');
            hrAssignmentsRaw.forEach(assignment => {
                hrAssignedClasses = hrAssignedClasses.concat(assignment.classes);
            });
        } catch(e) {}

        // Map HR classes to short format (e.g. "أولى 1" or "أولى متوسط 1" -> "1م1")
        const formatClassCode = (c) => {
             let cStr = String(c).trim();
             let level = '';
             if (cStr.includes('أولى') || cStr.includes('1')) level = '1';
             if (cStr.includes('ثانية') || cStr.includes('2')) level = '2';
             if (cStr.includes('ثالثة') || cStr.includes('3')) level = '3';
             if (cStr.includes('رابعة') || cStr.includes('4')) level = '4';

             let numMatch = cStr.match(/(\d+)$/);
             let num = numMatch ? numMatch[1] : '1';

             if (level && num) return `${level}م${num}`;
             return cStr;
        };

        const shortHrClasses = hrAssignedClasses.map(formatClassCode);

        // Also combine with any currently checked/assigned classes in this specific block
        const shortAssignedClasses = classesArray.map(formatClassCode);

        // Merge and remove duplicates
        let combinedClasses = [...new Set([...shortHrClasses, ...shortAssignedClasses])];

        // Custom sort logic to group by level
        combinedClasses.sort((a, b) => {
            let m1 = a.match(/(\d+)م(\d+)/);
            let m2 = b.match(/(\d+)م(\d+)/);
            if (m1 && m2) {
                if (m1[1] !== m2[1]) return parseInt(m1[1]) - parseInt(m2[1]);
                return parseInt(m1[2]) - parseInt(m2[2]);
            }
            return a.localeCompare(b, 'ar');
        });

        // Generate checkboxes
        combinedClasses.forEach(c => {
            const isChecked = shortAssignedClasses.includes(c) ? 'checked' : '';
            classesHtml += `
                <div class="form-check" style="display:inline-block; margin-left:15px; margin-bottom:5px;">
                    <input class="form-check-input dyn-class-cb" type="checkbox" value="${c}" ${isChecked}>
                    <label class="form-check-label font-weight-bold" style="font-size: 1.1rem; color: #333;">${c}</label>
                </div>
            `;
        });"""

content = content.replace(search_block, replace_block)

# Remove the default empty mapping fallback that sets default HR classes
search_default_fallback = """        if (assignments.length === 0) {
            // Default to HR assigned classes, but empty subject as requested
            let defaultClasses = [];
            hrAssignments.forEach(ha => {
                defaultClasses = defaultClasses.concat(ha.classes);
            });
            defaultClasses = [...new Set(defaultClasses)];

            // Map HR full names to "1م1" format
            defaultClasses = defaultClasses.map(c => {
                 let m = c.match(/(\d+)\s*متوسط\s*(\d+)/);
                 if (m) return `${m[1]}م${m[2]}`;
                 return c;
            });
            addAnalyticsAssignmentBlock('', defaultClasses);
        } else {"""

replace_default_fallback = """        if (assignments.length === 0) {
            // If no custom analytics assignments exist yet, auto-populate from HR assignments
            if (hrAssignments && hrAssignments.length > 0) {
                hrAssignments.forEach(ha => {
                    // Extract subject and format classes
                    let subj = ha.subject || '';
                    if (subj === '/' || subj === 'بدون') subj = '';
                    addAnalyticsAssignmentBlock(subj, ha.classes);
                });
            } else {
                // Completely empty, add one blank row
                addAnalyticsAssignmentBlock('', []);
            }
        } else {"""

content = content.replace(search_default_fallback, replace_default_fallback)

with open('students/templates/students/analytics.html', 'w') as f:
    f.write(content)
