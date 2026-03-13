with open("students/templates/students/analytics.html", "r") as f:
    content = f.read()

# We need to remove the frontend JavaScript filtering logic for dropdowns
# because the backend is already doing the filtering and sending the correct context variables.
# The user wants "mutual dynamic cross-filtering", meaning the backend already filters the lists based on the selected combination.

import re

# Remove the old JS logic that tries to hide/show options
s1 = """            function handleTeacherFilterChange(selectElement) {
                if (selectElement.value !== "") {
                    document.getElementById('levelFilter').value = "";
                    document.getElementById('classFilter').innerHTML = '<option value="" style="color: black;">جميع الأقسام</option>';
                    // Don't clear subject filter immediately, wait for backend to process
                }
                document.getElementById('analyticsFilterForm').submit();
            }

            function handleSubjectFilterChange(selectElement) {
                // If a subject is selected, disable/hide teachers that don't teach this subject
                const subj = selectElement.value;
                const teacherFilter = document.getElementById('teacherFilter');

                if (subj) {
                    let firstValidTeacherFound = false;
                    let currentSelectedIsValid = false;

                    for (let i = 0; i < teacherFilter.options.length; i++) {
                        let opt = teacherFilter.options[i];
                        if (opt.value === "") continue; // Skip 'All' option

                        const tSubj = opt.getAttribute('data-subject');
                        if (tSubj && tSubj !== '/' && tSubj !== subj) {
                            opt.style.display = 'none';
                            opt.disabled = true;
                        } else {
                            opt.style.display = 'block';
                            opt.disabled = false;
                            if (!firstValidTeacherFound) firstValidTeacherFound = true;
                            if (opt.selected) currentSelectedIsValid = true;
                        }
                    }

                    // If the currently selected teacher does not teach the new subject, clear the teacher filter
                    if (!currentSelectedIsValid && teacherFilter.value !== "") {
                        teacherFilter.value = "";
                    }
                } else {
                    // Reset all teachers
                    for (let i = 0; i < teacherFilter.options.length; i++) {
                        teacherFilter.options[i].style.display = 'block';
                        teacherFilter.options[i].disabled = false;
                    }
                }

                document.getElementById('analyticsFilterForm').submit();
            }

            // Run subject check on load without triggering form submission
            document.addEventListener('DOMContentLoaded', () => {
                const subjectFilter = document.getElementById('subjectFilter');
                const teacherFilter = document.getElementById('teacherFilter');
                const subj = subjectFilter.value;
                if (subj) {
                    let currentSelectedIsValid = false;
                    for (let i = 0; i < teacherFilter.options.length; i++) {
                        let opt = teacherFilter.options[i];
                        if (opt.value === "") continue;

                        const tSubj = opt.getAttribute('data-subject');
                        if (tSubj && tSubj !== '/' && tSubj !== subj) {
                            opt.style.display = 'none';
                            opt.disabled = true;
                        } else {
                            opt.style.display = 'block';
                            opt.disabled = false;
                            if (opt.selected) currentSelectedIsValid = true;
                        }
                    }
                    if (!currentSelectedIsValid && teacherFilter.value !== "") {
                        teacherFilter.value = "";
                    }
                }
            });"""

r1 = """            function handleTeacherFilterChange(selectElement) {
                document.getElementById('analyticsFilterForm').submit();
            }

            function handleSubjectFilterChange(selectElement) {
                document.getElementById('analyticsFilterForm').submit();
            }"""

content = content.replace(s1, r1)

with open("students/templates/students/analytics.html", "w") as f:
    f.write(content)
