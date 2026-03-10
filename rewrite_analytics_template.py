with open('students/templates/students/analytics.html', 'r', encoding='utf-8') as f:
    content = f.read()

import re
# We need to completely rebuild that specific section because the previous script messed up the logic.
# Let's replace everything from <table class="table table-hover table-striped" style="direction: rtl;"> up to <!-- Ranking Table & Deep Analysis Request -->

correct_table_html = """            <table class="table table-hover table-striped" style="direction: rtl;">
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
{% endif %}

<!-- Ranking Table & Deep Analysis Request -->"""

pattern = re.compile(r'            <table class="table table-hover table-striped" style="direction: rtl;">.*?<!-- Ranking Table & Deep Analysis Request -->', re.DOTALL)
content = pattern.sub(correct_table_html, content)

with open('students/templates/students/analytics.html', 'w', encoding='utf-8') as f:
    f.write(content)
