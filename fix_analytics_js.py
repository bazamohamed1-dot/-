with open('students/templates/students/analytics.html', 'r', encoding='utf-8') as f:
    content = f.read()

js_code = """
<script>
    // Teacher Comparison Logic
    let comparisonTeachers = [];
    let teacherAvgChartObj = null;
    let teacherSuccessChartObj = null;

    function updateTeacherCharts() {
        const container = document.getElementById('teacherComparisonChartsContainer');
        if (comparisonTeachers.length === 0) {
            container.style.display = 'none';
            return;
        }
        container.style.display = 'flex';

        const labels = comparisonTeachers.map(t => t.name);
        const avgData = comparisonTeachers.map(t => t.avg);
        const successData = comparisonTeachers.map(t => t.success);

        // Colors array
        const bgColors = [
            'rgba(59, 130, 246, 0.7)', 'rgba(16, 185, 129, 0.7)',
            'rgba(245, 158, 11, 0.7)', 'rgba(239, 68, 68, 0.7)',
            'rgba(139, 92, 246, 0.7)', 'rgba(236, 72, 153, 0.7)'
        ];
        const borderColors = bgColors.map(c => c.replace('0.7', '1'));

        const chartBgColors = labels.map((_, i) => bgColors[i % bgColors.length]);
        const chartBorderColors = labels.map((_, i) => borderColors[i % borderColors.length]);

        // Average Chart (Bar)
        const ctxAvg = document.getElementById('teacherAvgChart');
        if (ctxAvg) {
            if (teacherAvgChartObj) {
                teacherAvgChartObj.data.labels = labels;
                teacherAvgChartObj.data.datasets[0].data = avgData;
                teacherAvgChartObj.data.datasets[0].backgroundColor = chartBgColors;
                teacherAvgChartObj.data.datasets[0].borderColor = chartBorderColors;
                teacherAvgChartObj.update();
            } else {
                teacherAvgChartObj = new Chart(ctxAvg.getContext('2d'), {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'المتوسط',
                            data: avgData,
                            backgroundColor: chartBgColors,
                            borderColor: chartBorderColors,
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: { y: { beginAtZero: true, max: 20 } },
                        plugins: {
                            legend: { display: false }
                        }
                    }
                });
            }
        }

        // Success Rate Chart (Line)
        const ctxSuccess = document.getElementById('teacherSuccessChart');
        if (ctxSuccess) {
            if (teacherSuccessChartObj) {
                teacherSuccessChartObj.data.labels = labels;
                teacherSuccessChartObj.data.datasets[0].data = successData;
                teacherSuccessChartObj.update();
            } else {
                teacherSuccessChartObj = new Chart(ctxSuccess.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'نسبة النجاح (%)',
                            data: successData,
                            borderColor: 'rgba(16, 185, 129, 1)',
                            backgroundColor: 'rgba(16, 185, 129, 0.2)',
                            borderWidth: 3,
                            fill: true,
                            tension: 0.4,
                            pointBackgroundColor: 'rgba(16, 185, 129, 1)',
                            pointRadius: 5
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: { y: { beginAtZero: true, max: 100 } }
                    }
                });
            }
        }
    }

    window.addTeacherToComparison = function() {
        const select = document.getElementById('compareTeacherSelect');
        const opt = select.options[select.selectedIndex];
        if (!opt || !opt.value) return;

        const tName = opt.value;
        const tAvg = parseFloat(opt.getAttribute('data-avg'));
        const tSuccess = parseFloat(opt.getAttribute('data-success'));

        if (!comparisonTeachers.find(t => t.name === tName)) {
            comparisonTeachers.push({ name: tName, avg: tAvg, success: tSuccess });
            updateTeacherCharts();
        }

        // reset select
        select.value = "";
    };

    window.clearTeacherComparison = function() {
        comparisonTeachers = [];
        updateTeacherCharts();
    };
</script>
"""

# replace near the end
content = content.replace("{% endblock %}", js_code + "\n{% endblock %}")

with open('students/templates/students/analytics.html', 'w', encoding='utf-8') as f:
    f.write(content)
