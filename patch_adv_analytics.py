with open("students/templates/students/advanced_analytics.html", "r") as f:
    content = f.read()

s1 = """    function handleGlobalTeacherChange() {
        // When global teacher changes, trigger form submission to refresh server context
        document.getElementById('globalLevelSelector').value = "";
        document.getElementById('globalClassSelector').innerHTML = '<option value="">كل الأقسام</option>';
        document.getElementById('globalFiltersForm').submit();
    }

    function handleGlobalSubjectChange(selectElement) {
        const subj = selectElement.value;
        const teacherFilter = document.getElementById('globalTeacherSelector');

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
        } else {
            for (let i = 0; i < teacherFilter.options.length; i++) {
                teacherFilter.options[i].style.display = 'block';
                teacherFilter.options[i].disabled = false;
            }
        }
        document.getElementById('globalFiltersForm').submit();
    }

    document.addEventListener('DOMContentLoaded', () => {
        const globalSubjectFilter = document.getElementById('globalSubjectSelector');
        const teacherFilter = document.getElementById('globalTeacherSelector');

        // Run subject check on load without triggering form submission
        if (globalSubjectFilter && globalSubjectFilter.value) {
            const subj = globalSubjectFilter.value;
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

        // Initial setup for the level filter based on teacher
        const globalLevelFilter = document.getElementById('globalLevelSelector');

        if (teacherFilter && teacherFilter.value !== "") {
            const validLevels = Object.keys(classMap);
            for (let i = globalLevelFilter.options.length - 1; i >= 0; i--) {
                let opt = globalLevelFilter.options[i];
                if (opt.value !== "" && !validLevels.includes(opt.value)) {
                    globalLevelFilter.remove(i);
                }
            }
        }

        updateGlobalClassDropdown(false);
    });"""

r1 = """    function handleGlobalTeacherChange() {
        document.getElementById('globalFiltersForm').submit();
    }

    function handleGlobalSubjectChange(selectElement) {
        document.getElementById('globalFiltersForm').submit();
    }

    document.addEventListener('DOMContentLoaded', () => {
        updateGlobalClassDropdown(false);
    });"""

content = content.replace(s1, r1)

with open("students/templates/students/advanced_analytics.html", "w") as f:
    f.write(content)
