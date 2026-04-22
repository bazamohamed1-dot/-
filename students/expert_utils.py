import pandas as pd
import numpy as np
from scipy import stats
from sklearn.linear_model import LinearRegression
import logging
import json
from .models import Grade, Student, ExpertAnalysisRun, StudentExpertData, CohortExpertData, HistoricalGrade, SchoolSettings
from .import_utils import standardize_subject_name

logger = logging.getLogger(__name__)


def _weighted_avg_per_row(row_series, coef_dict):
    """متوسط مرجح لصف (سلسلة قيم المواد). coef_dict: {اسم_المادة: معامل}."""
    if not coef_dict or row_series.empty:
        return float(row_series.mean()) if not row_series.empty else 0.0
    total = 0.0
    wsum = 0.0
    for subj, val in row_series.items():
        if pd.isna(val):
            continue
        w = float(coef_dict.get(subj, 1.0))
        total += val * w
        wsum += w
    return total / wsum if wsum > 0 else float(row_series.mean()) if not row_series.empty else 0.0


def _term_weighted_avg(df_term, coef_dict):
    """معدل فصلي مرجح لجدول (student, subject, score) لفصل واحد. يرجع عدد واحد."""
    if df_term.empty:
        return 0.0
    if not coef_dict:
        return float(df_term['score'].mean())
    total = 0.0
    wsum = 0.0
    for _, row in df_term.iterrows():
        s = row.get('subject')
        sc = row.get('score', 0)
        if pd.isna(sc):
            continue
        w = float(coef_dict.get(s, 1.0))
        total += sc * w
        wsum += w
    return total / wsum if wsum > 0 else float(df_term['score'].mean())

def run_expert_engine(current_academic_year, current_term, prev_academic_year, prev_years_extra=None):
    """
    Deep Expert Analysis Engine.

    مراجع الحسابات:
    - السنة الحالية: من Grade (لوحة تحليل النتائج). نستخدم آخر فصل دراسي متاح.
    - السنوات الماضية: من HistoricalGrade (استيراد نتائج سابقة في تحليل الخبراء).
    """
    historical_years = [prev_academic_year] + (prev_years_extra or [])
    logger.info(f"Starting Expert Engine: {current_academic_year} {current_term} vs {historical_years}")

    try:
        # 1. Fetch current year grades (من لوحة التحليل فقط)
        curr_grades_all = Grade.objects.filter(academic_year=current_academic_year).select_related('student')
        if not curr_grades_all.exists():
            run_record = ExpertAnalysisRun.objects.create(
                academic_year=current_academic_year, term=current_term, status='failed: no current data'
            )
            return False

        # استعمال آخر فصل دراسي متاح للسنة الحالية (مرجع ثابت — لا يعتمد على اختيار المستخدم)
        term_order = {'الفصل الأول': 1, 'الفصل الثاني': 2, 'الفصل الثالث': 3}
        available_terms = list(curr_grades_all.values_list('term', flat=True).distinct())
        latest = max((t for t in available_terms if t), key=lambda t: term_order.get(t, 0)) if available_terms else None
        effective_term = latest or (current_term or 'الفصل الأول')

        run_record = ExpertAnalysisRun.objects.create(
            academic_year=current_academic_year,
            term=effective_term,
            status='running'
        )

        # 2. Fetch previous years grades (من استيراد تحليل الخبراء فقط)
        prev_grades = HistoricalGrade.objects.filter(historical_year__in=historical_years).select_related('student')

        # Build DataFrames: السنة الحالية بكل الفصول (للمسار والتنبؤ) ثم نفلتر لفصل واحد للتحليل الجماعي
        curr_data_all = list(curr_grades_all.values('student__id', 'student__last_name', 'student__first_name', 'student__date_of_birth', 'student__academic_year', 'student__class_name', 'student__class_code', 'subject', 'term', 'score'))
        prev_data = list(prev_grades.values('student__id', 'student__last_name', 'student__first_name', 'student__date_of_birth', 'student__academic_year', 'subject', 'term', 'score', 'historical_year'))

        df_curr_all = pd.DataFrame(curr_data_all)
        df_prev = pd.DataFrame(prev_data)

        if df_curr_all.empty:
            run_record.status = 'failed: empty dataframe'
            run_record.save()
            return False

        # Clean data (remove zeros and negative scores if they represent absence)
        df_curr = df_curr[df_curr['score'] > 0]
        if not df_prev.empty:
            df_prev = df_prev[df_prev['score'] > 0]

        # توحيد أسماء المواد لتفادي تشتت نفس المادة (فراغ/همزات/تاء...)
        df_curr = df_curr.copy()
        df_curr['subject'] = df_curr['subject'].apply(standardize_subject_name)
        if not df_prev.empty:
            df_prev = df_prev.copy()
            df_prev['subject'] = df_prev['subject'].apply(standardize_subject_name)

        # احتفظ بنسخة تتضمن سطور "المعدل ..." للاستفادة منها كمعدل جاهز من ملف Excel
        df_curr_with_avg = df_curr.copy()

        # استبعاد سطور "معدل ..." القادمة من ملف النتائج (ليست مواد حقيقية)
        # هذه السطور لو دخلت الحساب تُفسد المعدل المرجح والحساسية وWhat-If.
        df_curr = df_curr[df_curr['subject'].fillna('').astype(str).str.strip().ne('')]
        subj_s = df_curr['subject'].fillna('').astype(str).str.strip()
        df_curr = df_curr[~subj_s.str.startswith('معدل') & ~subj_s.str.startswith('المعدل')]
        if not df_prev.empty:
            df_prev = df_prev[df_prev['subject'].fillna('').astype(str).str.strip().ne('')]
            subj_p = df_prev['subject'].fillna('').astype(str).str.strip()
            df_prev = df_prev[~subj_p.str.startswith('معدل') & ~subj_p.str.startswith('المعدل')]

        levels = df_curr['student__academic_year'].unique()

        def _normalize_level_key(v):
            s = str(v or '').strip()
            s = ' '.join(s.split())
            if not s:
                return s
            # توحيد صيغ المستوى الشائعة (1/2/3/4 متوسط ↔ أولى/ثانية/ثالثة/رابعة متوسط)
            if 'متوسط' not in s and (s.isdigit() and s in {'1', '2', '3', '4'}):
                s = f"{s} متوسط"
            # إذا كان يبدأ برقم
            for d, w in (('1', 'أولى'), ('2', 'ثانية'), ('3', 'ثالثة'), ('4', 'رابعة')):
                if s.startswith(d):
                    # مثل: "4 متوسط" أو "4متوسط"
                    s2 = s.replace('متوسط', '').strip()
                    s = f"{w} متوسط" if (not s2 or s2 == d) else f"{w} متوسط"
                    break
            # إذا كان كلمة عربية بدون "متوسط"
            for w in ('أولى', 'ثانية', 'ثالثة', 'رابعة'):
                if s.startswith(w) and 'متوسط' not in s:
                    s = f"{w} متوسط"
                    break
            return s

        settings = SchoolSettings.objects.order_by('-id').first()
        all_coefs = getattr(settings, 'subject_coefficients_by_level', None) or {}
        # أحياناً تُخزن كـ JSON نصي
        if isinstance(all_coefs, str):
            try:
                all_coefs = json.loads(all_coefs) or {}
            except Exception:
                all_coefs = {}
        # بنِ قاموس معاملات بمفاتيح مستويات موحدة لتفادي عدم التطابق
        all_coefs_norm = {}
        if isinstance(all_coefs, dict):
            for k, v in all_coefs.items():
                nk = _normalize_level_key(k)
                if nk:
                    all_coefs_norm[nk] = v

        # مفتاح المطابقة للسنوات السابقة (اسم + تاريخ ميلاد)
        def match_key(row):
            ln = str(row.get('student__last_name', '') or row.get('last_name', '')).strip()
            fn = str(row.get('student__first_name', '') or row.get('first_name', '')).strip()
            dob = row.get('student__date_of_birth') or row.get('date_of_birth')
            if dob is None or (isinstance(dob, float) and pd.isna(dob)):
                dob_str = ''
            else:
                try:
                    dob_str = dob.strftime('%Y-%m-%d') if hasattr(dob, 'strftime') else str(dob)[:10]
                except Exception:
                    dob_str = str(dob)[:10] if dob else ''
            return (ln, fn, dob_str)

        if not df_prev.empty:
            df_prev = df_prev.copy()
            df_prev['_match_key'] = df_prev.apply(match_key, axis=1)
        # إضافة مفتاح المطابقة أيضاً لنسخة df_curr_with_avg (التي تحتوي على سطور "المعدل ...")
        try:
            if 'df_curr_with_avg' in locals():
                df_curr_with_avg = df_curr_with_avg.copy()
                df_curr_with_avg['_match_key'] = df_curr_with_avg.apply(match_key, axis=1)
        except Exception:
            pass

        # Group data by level for Cohort Analysis
        for level in levels:
            level_key = _normalize_level_key(level)
            # جرب مفاتيح متعددة: كما هي + مطبّعة
            coefs_raw = {}
            if isinstance(all_coefs, dict):
                coefs_raw = all_coefs.get(str(level).strip(), {}) or all_coefs.get(level, {}) or {}
            if not coefs_raw and level_key and isinstance(all_coefs_norm, dict):
                coefs_raw = all_coefs_norm.get(level_key, {}) or {}
            # مهم: توحيد مفاتيح المعاملات بنفس توحيد أسماء المواد في البيانات
            # حتى لا نفقد الأوزان بسبب اختلاف بسيط في الاسم (مسافات/ت/ة...).
            coefs = {}
            if isinstance(coefs_raw, dict):
                for k, v in coefs_raw.items():
                    kk = standardize_subject_name(k) or (str(k).strip() if k is not None else '')
                    if not kk:
                        continue
                    try:
                        coefs[kk] = float(v)
                    except Exception:
                        # fallback: معامل افتراضي
                        coefs[kk] = 1.0
            df_level_curr = df_curr[df_curr['student__academic_year'] == level].copy()
            if df_level_curr.empty:
                continue

            df_level_prev = pd.DataFrame()
            if not df_prev.empty:
                df_level_prev = df_prev[df_prev['student__academic_year'] == level].copy()

            # --- A. Z-SCORE CALCULATION (Current Year) ---
            # Z-Score helps unify the scale across different subjects and teachers.
            # We calculate Z-Score per subject within the level.
            df_level_curr['z_score'] = df_level_curr.groupby('subject')['score'].transform(lambda x: stats.zscore(x, ddof=1) if len(x) > 1 and x.std() > 0 else 0)

            # --- B. CORRELATION MATRIX (Inter-Subject Heatmap) ---
            pivot_curr = df_level_curr.pivot_table(index='student__id', columns='subject', values='score', aggfunc='mean')
            # نحتفظ بنسب التغطية قبل التعويض
            coverage = (1.0 - pivot_curr.isna().mean()).to_dict() if not pivot_curr.empty else {}
            # استبعاد المواد ضعيفة التغطية أو ذات تباين معدوم (لتفادي "مادة حاكمة" غير منطقية)
            keep_cols = []
            for col in pivot_curr.columns:
                cov = float(coverage.get(col, 0.0) or 0.0)
                if cov < 0.60:
                    continue
                s = pivot_curr[col].dropna()
                if len(s) < 8:
                    continue
                if float(s.std()) <= 1e-9:
                    continue
                keep_cols.append(col)
            pivot_curr = pivot_curr[keep_cols] if keep_cols else pivot_curr

            pivot_curr_filled = pivot_curr.fillna(pivot_curr.mean())
            # إضافة عمود المعدل العام المرجح إن وُجدت معاملات المواد
            if coefs and not pivot_curr_filled.empty:
                pivot_curr_filled['المعدل العام'] = pivot_curr_filled.apply(lambda row: _weighted_avg_per_row(row, coefs), axis=1)
            corr_matrix = pivot_curr_filled.corr().round(3)

            # Replace NaNs in corr_matrix with 0 for JSON serialization
            corr_matrix = corr_matrix.fillna(0)
            corr_dict = corr_matrix.to_dict()

            # --- C. SENSITIVITY ANALYSIS (Beta Coefficients) ---
            # Multiple Regression to find the "Ruling Subject" (بيضة القبان)
            # Dependent variable: General Average (المعدل العام) or mean of all subjects per student
            betas = {}
            ruling_subject = None

            if 'المعدل العام' in pivot_curr_filled.columns:
                y = pivot_curr_filled['المعدل العام']
                X = pivot_curr_filled.drop(columns=['المعدل العام'])
                if not X.empty and len(X.columns) > 1 and len(X) > 10:
                    try:
                        # معيارية X و y لجعل المقارنة بين المواد عادلة (تخفيض أثر اختلاف السلالم)
                        Xs = (X - X.mean()) / X.std(ddof=0).replace(0, np.nan)
                        ys = (y - y.mean()) / (y.std(ddof=0) if y.std(ddof=0) != 0 else 1.0)
                        Xs = Xs.fillna(0.0)
                        model = LinearRegression()
                        model.fit(Xs, ys)
                        for i, col in enumerate(Xs.columns):
                            betas[col] = float(model.coef_[i])
                        # المادة الحاكمة = أكبر تأثير مطلق (وليس أكبر موجب فقط)
                        if betas:
                            # ترجيح منطقي: لا نقبل مواد بمعامل ضعيف جداً إن كانت معاملات المواد متاحة
                            candidates = list(betas.keys())
                            if coefs and isinstance(coefs, dict):
                                candidates = [s for s in candidates if float(coefs.get(s, 1.0)) >= 2.0]
                                if not candidates:
                                    candidates = [s for s in betas.keys() if float(coefs.get(s, 1.0)) >= 1.0]
                            ruling_subject = max(candidates, key=lambda k: abs(betas.get(k, 0.0))) if candidates else max(betas, key=lambda k: abs(betas[k]))
                    except Exception as e:
                        logger.error(f"Error calculating sensitivity for {level}: {e}")
            else:
                # عند غياب عمود المعدل العام: احسب حساسية كل مادة للمعدل (انحدار بسيط: المعدل على المادة)
                y_avg = pivot_curr_filled.mean(axis=1)
                for col in pivot_curr_filled.columns:
                    try:
                        x_col = pivot_curr_filled[[col]]
                        if x_col.notna().all().all() and len(x_col) > 1:
                            model = LinearRegression()
                            model.fit(x_col, y_avg)
                            betas[col] = float(model.coef_[0])
                    except Exception:
                        pass
                if betas:
                    candidates = list(betas.keys())
                    if coefs and isinstance(coefs, dict):
                        candidates = [s for s in candidates if float(coefs.get(s, 1.0)) >= 2.0]
                        if not candidates:
                            candidates = [s for s in betas.keys() if float(coefs.get(s, 1.0)) >= 1.0]
                    ruling_subject = max(candidates, key=lambda k: abs(betas.get(k, 0.0))) if candidates else max(betas, key=betas.get)

            # --- D. COHORT EFFECT ---
            curr_avg_z = 0.0
            prev_avg_z = 0.0
            last_year_raw_avg = None
            cohort_effect = "لا توجد بيانات سابقة كافية"

            if not df_level_prev.empty:
                df_level_prev['z_score'] = df_level_prev.groupby('subject')['score'].transform(lambda x: stats.zscore(x, ddof=1) if len(x) > 1 and x.std() > 0 else 0)
                subject_stats_prev = df_level_prev.groupby('subject')['score'].agg(['mean', 'std']).reset_index()
                df_rel = pd.merge(df_level_curr, subject_stats_prev, on='subject', suffixes=('', '_prev'))
                df_rel['rel_z_score'] = np.where(df_rel['std'] > 0, (df_rel['score'] - df_rel['mean']) / df_rel['std'], 0)
                curr_avg_z = float(df_rel['rel_z_score'].mean())
                if pd.isna(curr_avg_z): curr_avg_z = 0.0
                prev_avg_z = 0.0  # معيار المقارنة = 0

                try:
                    if coefs:
                        per_student_avg = df_level_prev.groupby('student__id').apply(
                            lambda g: _term_weighted_avg(g, coefs), include_groups=False
                        )
                    else:
                        per_student_avg = df_level_prev.groupby('student__id')['score'].mean()
                    last_year_raw_avg = float(per_student_avg.mean())
                    if pd.isna(last_year_raw_avg): last_year_raw_avg = None
                except Exception:
                    last_year_raw_avg = float(df_level_prev['score'].mean()) if not df_level_prev.empty else None

                if curr_avg_z < -0.2:
                    cohort_effect = "تراجع عام في المستوى (تأثير الفوج/المنهج)"
                elif curr_avg_z > 0.2:
                    cohort_effect = "تحسن عام في المستوى (تأثير الفوج/المنهج)"
                else:
                    cohort_effect = "مستوى الفوج مستقر مقارنة بالعام الماضي"

            CohortExpertData.objects.create(
                run=run_record,
                academic_year_level=level,
                correlation_matrix=corr_dict,
                current_year_z_score_avg=curr_avg_z,
                last_year_z_score_avg=prev_avg_z,
                last_year_raw_avg=last_year_raw_avg,
                cohort_effect_analysis=cohort_effect,
                sensitivity_betas=betas,
                ruling_subject=ruling_subject
            )

            # --- E. PATTERN FINDER & FUTURE FORECAST (Student Level) ---
            df_level_curr['_match_key'] = df_level_curr.apply(match_key, axis=1)
            if not df_level_prev.empty:
                df_level_prev['_match_key'] = df_level_prev.apply(match_key, axis=1)
            # للمسار الفردي: مطابقة بكل السنوات والمستويات (نفس الشخص قد يكون أولى 2023 ثم ثانية 2024)
            if not df_prev.empty:
                df_prev = df_prev.copy()
                df_prev['_match_key'] = df_prev.apply(match_key, axis=1)

            students_in_level = df_level_curr['_match_key'].unique()

            for mkey in students_in_level:
                if mkey[0] == '' and mkey[1] == '': continue
                student_curr = df_level_curr[df_level_curr['_match_key'] == mkey]
                student_prev = pd.DataFrame()
                if not df_level_prev.empty and '_match_key' in df_level_prev.columns:
                    student_prev = df_level_prev[df_level_prev['_match_key'] == mkey]
                # سجل التلميذ الكامل عبر كل السنوات (للمسار والتنبؤ)
                student_prev_full = pd.DataFrame()
                if not df_prev.empty and '_match_key' in df_prev.columns:
                    student_prev_full = df_prev[df_prev['_match_key'] == mkey].copy()

                # Combine history for trend (ترتيب زمني: الأقدم أولاً)
                history = []
                time_x = []
                scores_y = []
                term_counter = 1
                term_order = {'الفصل الأول': 1, 'الفصل الثاني': 2, 'الفصل الثالث': 3}

                # Process all previous years terms (معدل فصلي مرجح بالمعاملات)
                if not student_prev_full.empty:
                    prev_entries = []
                    if 'historical_year' in student_prev_full.columns:
                        for (yr, term_name), grp in student_prev_full.groupby(['historical_year', 'term']):
                            avg_val = _term_weighted_avg(grp, coefs)
                            prev_entries.append((str(yr), term_name, avg_val))
                        prev_entries.sort(key=lambda e: (e[0], term_order.get(e[1], 99)))
                    else:
                        for term_name, grp in student_prev_full.groupby('term'):
                            avg_val = _term_weighted_avg(grp, coefs)
                            prev_entries.append((prev_academic_year, term_name, avg_val))
                    for yr, term_name, avg_val in prev_entries:
                        history.append({"term": f"{yr} - {term_name}", "score": round(avg_val, 2)})
                        time_x.append(term_counter)
                        scores_y.append(avg_val)
                        term_counter += 1

                # Process current year terms (معدل فصلي مرجح)
                current_avg_score = 0
                for term_name, grp in student_curr.groupby('term'):
                    # إذا كان ملف Excel يحتوي على "المعدل ..." لهذا التلميذ/الفصل: استعمله مباشرة (أدق وموحّد مع الجدول)
                    excel_avg_val = None
                    try:
                        g_all = df_curr_with_avg[
                            (df_curr_with_avg['_match_key'] == mkey) &
                            (df_curr_with_avg['term'] == term_name)
                        ].copy()
                        if not g_all.empty:
                            subj_all = g_all['subject'].fillna('').astype(str).str.strip()
                            g_avg = g_all[subj_all.str.startswith('معدل') | subj_all.str.startswith('المعدل')]
                            if not g_avg.empty:
                                excel_avg_val = float(g_avg['score'].dropna().iloc[0])
                    except Exception:
                        excel_avg_val = None

                    avg_val = excel_avg_val if excel_avg_val is not None else _term_weighted_avg(grp, coefs)
                    history.append({"term": f"{current_academic_year} - {term_name}", "score": round(avg_val, 2)})
                    time_x.append(term_counter)
                    scores_y.append(avg_val)
                    if term_name == effective_term:
                        current_avg_score = avg_val
                    term_counter += 1

                # Calculate Trend and Residual
                predicted_avg = None
                residual = None
                status_pattern = "مستقر"
                traffic_light = "yellow"

                if len(time_x) >= 2:
                    X_reg = np.array(time_x).reshape(-1, 1)
                    y_reg = np.array(scores_y)

                    try:
                        model = LinearRegression()
                        model.fit(X_reg, y_reg)

                        # Predict next term (term_counter)
                        predicted_avg = float(model.predict([[term_counter]])[0])

                        # Calculate residual for current term: Actual - Predicted(for current term)
                        # We trained on all data, so we check the residual of the last point
                        pred_last = model.predict([[time_x[-1]]])[0]
                        residual = float(scores_y[-1] - pred_last)

                        if residual > 1.5:
                            status_pattern = "قافز فجأة (أداء يفوق التوقع)"
                        elif residual < -1.5:
                            status_pattern = "متراجع فجأة (أداء أقل من التوقع)"

                        if predicted_avg < 10:
                            traffic_light = "red"
                        elif predicted_avg >= 12:
                            traffic_light = "green"

                    except Exception as e:
                        logger.error(f"Regression error for student {mkey}: {e}")
                else:
                    # Not enough data for regression
                    predicted_avg = current_avg_score
                    if predicted_avg < 10: traffic_light = "red"
                    elif predicted_avg >= 12: traffic_light = "green"

                # Average Z-Score for the student in current term
                student_z_score = float(student_curr['z_score'].mean()) if 'z_score' in student_curr.columns else 0.0
                if pd.isna(student_z_score): student_z_score = 0.0

                # Prefer class_code for display/grouping if available
                class_code_val = student_curr['student__class_code'].iloc[0] if 'student__class_code' in student_curr.columns and not pd.isna(student_curr['student__class_code'].iloc[0]) else None
                class_name = class_code_val or (student_curr['student__class_name'].iloc[0] if not student_curr.empty else "غير معروف")

                # student_id for StudentExpertData: use Student.id from curr
                curr_student_id = student_curr['student__id'].iloc[0] if not student_curr.empty else None

                # Save Student Data
                StudentExpertData.objects.create(
                    run=run_record,
                    student_id=curr_student_id,
                    class_name=class_name,
                    academic_year_level=level,
                    residual=residual,
                    status_pattern=status_pattern,
                    current_avg=current_avg_score,
                    predicted_avg=predicted_avg,
                    traffic_light=traffic_light,
                    trend_history=history,
                    net_value_added=residual, # Using residual as Net Value Added
                    z_score=student_z_score
                )

        run_record.status = 'completed'
        run_record.save()
        logger.info(f"Expert Engine completed successfully for {current_academic_year} {current_term}")
        return True

    except Exception as e:
        logger.error(f"Expert Engine Error: {e}")
        import traceback
        traceback.print_exc()
        if 'run_record' in locals():
            run_record.status = f"failed: {str(e)}"
            run_record.save()
        return False
