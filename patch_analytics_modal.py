import re

with open("students/templates/students/analytics.html", "r") as f:
    content = f.read()

s1 = """        // Remove duplicates and map to format like "1م1" if needed
        let cleanGlobal = [...new Set(flatClasses)].map(c => {
             let m = c.match(/(\d+)\s*متوسط\s*(\d+)/);
             if (m) return `${m[1]}م${m[2]}`;
             return c;
        });"""

r1 = """        // Remove duplicates and map to format like "1م1"
        let cleanGlobal = [...new Set(flatClasses)].map(c => {
             let m = c.match(/(\d+)\s*متوسط\s*(\d+)/);
             if (m) return `${m[1]}م${m[2]}`;
             return c;
        });"""

s2 = """    function loadTeacherAnalyticsAssignment(teacherId) {
        if (!teacherId) {
            document.getElementById('teacherAssignmentEditor').style.display = 'none';
            return;
        }

        const select = document.getElementById('teacherSelect');
        const opt = select.options[select.selectedIndex];
        document.getElementById('selectedTeacherName').innerText = opt.getAttribute('data-name');

        let assignments = [];
        try {
            assignments = JSON.parse(opt.getAttribute('data-assignments') || '[]');
        } catch(e) {}

        const container = document.getElementById('analyticsAssignmentBlocksContainer');
        container.innerHTML = '';

        if (assignments.length === 0) {
            addAnalyticsAssignmentBlock();
        } else {
            assignments.forEach(a => addAnalyticsAssignmentBlock(a.subject, a.classes));
        }

        document.getElementById('teacherAssignmentEditor').style.display = 'block';
    }"""

r2 = """    function loadTeacherAnalyticsAssignment(teacherId) {
        if (!teacherId) {
            document.getElementById('teacherAssignmentEditor').style.display = 'none';
            return;
        }

        const select = document.getElementById('teacherSelect');
        const opt = select.options[select.selectedIndex];
        document.getElementById('selectedTeacherName').innerText = opt.getAttribute('data-name');

        let assignments = [];
        try {
            assignments = JSON.parse(opt.getAttribute('data-assignments') || '[]');
        } catch(e) {}

        let hrAssignments = [];
        try {
            hrAssignments = JSON.parse(opt.getAttribute('data-hr-assignments') || '[]');
        } catch(e) {}

        const container = document.getElementById('analyticsAssignmentBlocksContainer');
        container.innerHTML = '';

        if (assignments.length === 0) {
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
        } else {
            assignments.forEach(a => addAnalyticsAssignmentBlock(a.subject, a.classes));
        }

        document.getElementById('teacherAssignmentEditor').style.display = 'block';
    }"""

content = content.replace(s1, r1)
content = content.replace(s2, r2)

with open("students/templates/students/analytics.html", "w") as f:
    f.write(content)
