import re

with open('students/templates/students/analytics.html', 'r', encoding='utf-8') as f:
    content = f.read()

replacement_html = """<!-- Teacher Comparison Table -->
{% if local_stats.teacher_stats %}
<div class="row mb-4" style="display: flex; flex-wrap: wrap; gap: 20px; padding: 0 15px;">
    <div class="card col-md-12" style="flex: 1; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); padding: 20px; background: #fff;">
        <h4 style="color: #334155; margin-bottom: 20px;"><i class="fas fa-chalkboard-teacher text-info"></i> مقارنة أداء الأساتذة</h4>

        <!-- Multi-Teacher Selector for Comparison -->
        <div style="margin-bottom: 20px; background: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0;">
            <label for="compareTeacherSelect" style="font-weight: bold; margin-bottom: 10px; display: block;">إضافة أستاذ للمقارنة:</label>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                <select id="compareTeacherSelect" class="form-select" style="max-width: 300px;">
                    <option value="">اختر أستاذ...</option>
                    {% for ts in local_stats.teacher_stats %}
                        <option value="{{ ts.teacher_name }}" data-avg="{{ ts.avg_score }}" data-success="{{ ts.success_pct }}">{{ ts.teacher_name }}</option>
                    {% endfor %}
                </select>
                <button type="button" class="btn btn-primary" onclick="addTeacherToComparison()">
                    <i class="fas fa-plus"></i> إضافة للمقارنة
                </button>
                <button type="button" class="btn btn-outline-danger" onclick="clearTeacherComparison()">
                    <i class="fas fa-trash"></i> مسح المقارنة
                </button>
            </div>

            <!-- Comparison Charts -->
            <div id="teacherComparisonChartsContainer" style="display: none; margin-top: 30px; gap: 20px; flex-wrap: wrap;">
                <div style="flex: 1; min-width: 300px;">
                    <h5 style="text-align: center; color: #475569;">متوسط العلامات (أعمدة)</h5>
                    <canvas id="teacherAvgChart" style="max-height: 250px;"></canvas>
                </div>
                <div style="flex: 1; min-width: 300px;">
                    <h5 style="text-align: center; color: #475569;">نسبة النجاح (خطي)</h5>
                    <canvas id="teacherSuccessChart" style="max-height: 250px;"></canvas>
                </div>
            </div>
        </div>

        <div class="table-responsive">
            <table class="table table-hover table-striped" style="direction: rtl;">
                <thead class="table-dark">
                    <tr>
                        <th>الأستاذ</th>
                        <th>عدد الاختبارات</th>
                        <th>متوسط العلامات</th>
                        <th>نسبة النجاح (%)</th>
                    </tr>
                </thead>
                <tbody>
                    {% for ts in local_stats.teacher_stats %}
                    <tr>
                        <td>{{ ts.teacher_name }}</td>
                        <td>{{ ts.total_tested }}</td>
                        <td>
                            <span class="badge {% if ts.avg_score >= 10 %}bg-success{% else %}bg-danger{% endif %} fs-6">
                                {{ ts.avg_score }}
                            </span>
                        </td>
                        <td>
                            <div class="progress" style="height: 20px; border-radius: 10px; background-color: #e2e8f0;">
                                <div class="progress-bar {% if ts.success_pct >= 50 %}bg-success{% else %}bg-danger{% endif %}" role="progressbar" style="width: {{ ts.success_pct }}%;" aria-valuenow="{{ ts.success_pct }}" aria-valuemin="0" aria-valuemax="100">
                                    <span style="font-weight:bold; color:white; padding:0 5px;">{{ ts.success_pct }}%</span>
                                </div>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
{% endif %}"""

pattern = re.compile(r'<!-- Teacher Comparison Table -->.*?{% endif %}', re.DOTALL)
content = pattern.sub(replacement_html, content)

with open('students/templates/students/analytics.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated analytics.html with comparison UI")
