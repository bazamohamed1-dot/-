import pandas as pd
import logging
from django.db.models import QuerySet

logger = logging.getLogger(__name__)

import re

def format_class_name(level, class_name):
    """تنسيق اسم القسم كفوج تربوي (مثل 4م1، 4م2) دائماً."""
    if pd.isna(level) or pd.isna(class_name):
        return f"{level} {class_name}"
    level = str(level).strip()
    class_name = str(class_name).strip()
    level_match = re.search(r"\d+", level)
    if not level_match:
        # مستوى بصيغة عربية (رابعة متوسط، أولى متوسط، ...)
        arabic_level_map = {'أولى': '1', 'ثانية': '2', 'ثالثة': '3', 'رابعة': '4'}
        for arb, digit in arabic_level_map.items():
            if arb in level:
                level_digit = digit
                break
        else:
            level_digit = None
        if not level_digit:
            return class_name
        digits = re.findall(r"\d+", class_name)
        if len(digits) >= 2:
            return f"{digits[0]}م{digits[-1]}"
        elif len(digits) == 1:
            return f"{level_digit}م{digits[0]}"
        return f"{level_digit}م{class_name}"
    digits = re.findall(r"\d+", class_name)
    if len(digits) >= 2:
        return f"{digits[0]}م{digits[-1]}"
    elif len(digits) == 1:
        return f"{level_match.group()}م{digits[0]}"
    return f"{level_match.group()}م{class_name}"

def unformat_class_name(formatted_class):
    """
    Tries to map a formatted class string (like '1م5' or 'أولى 5') back to its raw numeric part (like '5').
    This is a best-effort helper for backend queries when the DB stores raw numbers but the frontend passes back formatted strings.
    """
    if not formatted_class:
        return formatted_class
    digits = re.findall(r'\d+', str(formatted_class))
    if len(digits) >= 1:
        return digits[-1]
    return formatted_class


def _level_key(s):
    """استخراج مفتاح المستوى (1،2،3،4) من نص المستوى لاستخدامه في مطابقة إعفاء المستوى."""
    if not s or not str(s).strip():
        return None
    s = str(s).strip()
    # التحقق من الأسماء العربية أولاً حتى لا يُفسَّر رقم القسم (مثل ثانية 1) كمستوى
    if 'أولى' in s or 'الاولى' in s or 'الأولى' in s:
        return '1'
    if 'ثانية' in s or 'الثانية' in s:
        return '2'
    if 'ثالثة' in s or 'الثالثة' in s:
        return '3'
    if 'رابعة' in s or 'الرابعة' in s:
        return '4'
    # ثم الرقم وحده أو في بداية النص (مثل 1، 1 متوسط)
    if re.match(r'^1\s|^1$|متوسط\s*1', s) or s == '1':
        return '1'
    if re.match(r'^2\s|^2$|متوسط\s*2', s) or s == '2':
        return '2'
    if re.match(r'^3\s|^3$|متوسط\s*3', s) or s == '3':
        return '3'
    if re.match(r'^4\s|^4$|متوسط\s*4', s) or s == '4':
        return '4'
    return None


def analyze_grades_locally(grades_qs: QuerySet, subject_filter=None, include_zeros=True, grades_qs_for_ranking=None, exempt_subjects=None, exemption_rules=None):
    """
    Takes a Django QuerySet of Grade objects and uses Pandas to perform local statistical analysis.
    If grades_qs_for_ranking is provided (e.g. نفس الطلاب/الأفواج لكن كل المواد)، يُستخدم لحساب
    ترتيب التلاميذ والمعدل الفصلي الحقيقي (كل المواد) بدل معدل المواد المفلترة فقط.
    exempt_subjects: list of subject names to exclude from all calculations (المادة المعفاة من التحليل).
    """
    if not grades_qs.exists():
        return None

    exempt_set = set(str(s).strip() for s in (exempt_subjects or []) if s)

    try:
        # 1. Convert QuerySet to Pandas DataFrame
        data = list(grades_qs.values('student__id', 'student__last_name', 'student__first_name', 'student__class_name', 'student__class_code', 'student__academic_year', 'student__gender', 'student__is_repeater', 'student__date_of_birth', 'subject', 'term', 'score'))
        if not data:
            return None
        df = pd.DataFrame(data)

        # استبعاد المواد المعفاة من التحليل تماماً
        if exempt_set:
            df = df[~df['subject'].astype(str).str.strip().isin(exempt_set)]

        df_ranking = None
        if grades_qs_for_ranking and grades_qs_for_ranking.exists():
            data_rank = list(grades_qs_for_ranking.values('student__id', 'student__last_name', 'student__first_name', 'student__class_name', 'student__class_code', 'student__academic_year', 'subject', 'term', 'score'))
            if data_rank:
                df_ranking = pd.DataFrame(data_rank)
                if exempt_set:
                    df_ranking = df_ranking[~df_ranking['subject'].astype(str).str.strip().isin(exempt_set)]
                df_ranking['student_name'] = df_ranking['student__last_name'].fillna('') + ' ' + df_ranking['student__first_name'].fillna('')
                df_ranking['student__class_name'] = df_ranking.apply(lambda row: format_class_name(row['student__academic_year'], row['student__class_name']), axis=1)

        # Reconstruct full_name and format class — قبل فلتر الأصفار لاستخدام نفس البيانات للقائمة والترتيب
        df['student_name'] = df['student__last_name'].fillna('') + ' ' + df['student__first_name'].fillna('')
        df['student__class_name'] = df.apply(lambda row: format_class_name(row['student__academic_year'], row['student__class_name']), axis=1)

        def apply_exemption_rules_to_frame(d):
            """تطبيق قواعد الإعفاء (تلميذ/فوج/مستوى/مؤسسة) على إطار البيانات."""
            if not exemption_rules or not isinstance(exemption_rules, list) or d.empty:
                return d
            try:
                d = d.copy()
                d['__class_code_effective'] = d['student__class_code'].fillna('')
                needs = d['__class_code_effective'].astype(str).str.strip() == ''
                if needs.any():
                    d.loc[needs, '__class_code_effective'] = d.loc[needs].apply(
                        lambda row: format_class_name(row['student__academic_year'], row['student__class_name']),
                        axis=1
                    )
                d['__class_code_effective'] = d['__class_code_effective'].astype(str).str.strip()

                subj_norm = d['subject'].astype(str).str.strip()
                term_norm = d['term'].astype(str).str.strip()
                mask_exempt = pd.Series(False, index=d.index)

                for r in exemption_rules:
                    if not isinstance(r, dict):
                        continue
                    r_subj = str(r.get('subject') or '').strip()
                    if not r_subj:
                        continue
                    r_scope = str(r.get('scope_type') or '').strip()
                    r_term = str(r.get('term') or '').strip()

                    # مطابقة المادة: تطابق تام أو بعد إزالة "ال" من الطرفين
                    r_subj_norm = r_subj.replace('ال', '', 1) if r_subj.startswith('ال') else r_subj
                    subj_norm_alt = subj_norm.str.replace('^ال', '', regex=True).str.strip()
                    m = (subj_norm == r_subj) | (subj_norm == r_subj_norm) | (subj_norm_alt == r_subj) | (subj_norm_alt == r_subj_norm)
                    if r_term:
                        m = m & (term_norm == r_term)

                    if r_scope == 'student':
                        sid = r.get('student_id')
                        if sid:
                            m = m & (d['student__id'] == int(sid))
                        else:
                            continue
                    elif r_scope == 'class':
                        cc = str(r.get('class_code') or '').strip()
                        if not cc:
                            continue
                        m = m & (d['__class_code_effective'] == cc)
                    elif r_scope == 'level':
                        lvl = str(r.get('academic_year') or '').strip()
                        if not lvl:
                            continue
                        rule_level_key = _level_key(lvl)
                        if not rule_level_key:
                            continue
                        # مطابقة المستوى بمفتاح موحد (1،2،3،4) لأن القاعدة قد تكون "أولى متوسط" والبيانات "أولى" فقط
                        d['__level_key'] = d['student__academic_year'].apply(lambda x: _level_key(x))
                        m = m & (d['__level_key'] == rule_level_key)
                        d.drop(columns=['__level_key'], inplace=True, errors='ignore')
                    elif r_scope == 'school':
                        pass
                    else:
                        continue

                    mask_exempt = mask_exempt | m

                if mask_exempt.any():
                    d = d[~mask_exempt]
                return d
            except Exception:
                return d

        # تطبيق قواعد الإعفاء على البيانات الرئيسية وعلى بيانات الترتيب
        if exemption_rules and isinstance(exemption_rules, list):
            df = apply_exemption_rules_to_frame(df)
            if df_ranking is not None and not df_ranking.empty:
                df_ranking = apply_exemption_rules_to_frame(df_ranking)

        # نسخة كاملة (مع الأصفار) لبناء قائمة الترتيب وعرض الأصفار — مستقلة عن خيار احتساب الأصفار
        df_full = df.copy()

        # Remove zeros from dataframe for stats only if include_zeros is False
        if not include_zeros:
            df = df[df['score'] != 0.0]

        import json
        from datetime import date

        general_avg_subj = None

        # نفس المنطق لـ df_full لبناء قائمة الترتيب وعرض الأصفار (مستقلة عن include_zeros)
        if subject_filter:
            general_avg_df = df.groupby(['student_name', 'student__class_name', 'student__academic_year', 'term'])['score'].mean().reset_index()
            general_avg_df_full = df_full.groupby(['student_name', 'student__class_name', 'student__academic_year', 'term'])['score'].mean().reset_index()
        else:
            # Determine the "General Average" (المعدل العام) subject if it exists, otherwise use mean of all scores
            for subj in df['subject'].unique():
                if subj and isinstance(subj, str) and (subj.strip() == 'المعدل العام' or subj.strip().startswith('معدل الفصل')):
                    general_avg_subj = subj
                    break

            if general_avg_subj:
                general_avg_df = df[df['subject'] == general_avg_subj].copy()
                general_avg_df_full = df_full[df_full['subject'] == general_avg_subj].copy() if general_avg_subj in df_full['subject'].values else df_full.groupby(['student_name', 'student__class_name', 'student__academic_year', 'term'])['score'].mean().reset_index()
            else:
                general_avg_df = df.groupby(['student_name', 'student__class_name', 'student__academic_year', 'term'])['score'].mean().reset_index()
                general_avg_df_full = df_full.groupby(['student_name', 'student__class_name', 'student__academic_year', 'term'])['score'].mean().reset_index()

        # Separate absent vs active students based on general average
        # We consider a student active if their score is >= 0, UNLESS include_zeros is True,
        # Missing/Absent students have score == -1.0 or NaN
        active_students_df = general_avg_df[general_avg_df['score'] >= 0]
        if not include_zeros:
            active_students_df = general_avg_df[general_avg_df['score'] > 0]

        absent_students_df = general_avg_df[(general_avg_df['score'] < 0) | (general_avg_df['score'].isna())]

        # 2. General Stats (Calculated ONLY on active students)
        total_students = general_avg_df['student_name'].nunique()
        active_students_count = active_students_df['student_name'].nunique()

        # Demographics
        unique_students_df = df.drop_duplicates(subset=['student_name'])
        total_males = unique_students_df[unique_students_df['student__gender'] == 'ذكر'].shape[0]
        total_females = unique_students_df[unique_students_df['student__gender'] == 'أنثى'].shape[0]
        total_repeaters = unique_students_df[unique_students_df['student__is_repeater'] == True].shape[0]

        # Average Age
        today = date.today()
        def calc_age(dob):
            if pd.isna(dob): return None
            # Handle string or date objects
            try:
                if isinstance(dob, str): dob = pd.to_datetime(dob).date()
                return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            except:
                return None

        unique_students_df['age'] = unique_students_df['student__date_of_birth'].apply(calc_age)
        avg_age = unique_students_df['age'].mean()
        avg_age = round(avg_age, 1) if not pd.isna(avg_age) else 0

        general_avg = active_students_df['score'].mean()
        general_avg = round(general_avg, 2) if not pd.isna(general_avg) else 0

        # Success Rate (ONLY active students)
        failures_count = active_students_df[active_students_df['score'] < 10]['student_name'].nunique()
        success_count = active_students_count - failures_count
        success_rate = round((success_count / active_students_count) * 100, 2) if active_students_count > 0 else 0

        # Class Comparison (Average per class - active only)
        class_avgs = active_students_df.groupby('student__class_name')['score'].mean().round(2).to_dict()

        # Trend Analysis (Average per term - active only)
        term_avgs = active_students_df.groupby('term')['score'].mean().round(2).to_dict()

        # Distribution / Histogram (Ranges - active only)
        scores = active_students_df['score'].dropna()
        std_dev = round(scores.std(), 2) if len(scores) > 1 else 0

        bins = [0, 9.99, 11.99, 13.99, 15.99, 20]
        labels = ['<10', '10-11.99', '12-13.99', '14-15.99', '16-20']
        dist_counts = pd.cut(scores, bins=bins, labels=labels, right=True, include_lowest=True).value_counts().to_dict()

        # Categorization (Pie Chart - active only)
        cat_bins = [0, 9.99, 13.99, 15.99, 20]
        cat_labels = ['متعثر', 'متوسط', 'جيد', 'ممتاز']
        categories = pd.cut(scores, bins=cat_bins, labels=cat_labels, right=True, include_lowest=True).value_counts().to_dict()

        # Subject Averages Comparison & Detailed Stats for Print Layout
        # To calculate subject averages, we only consider scores > 0 to exclude absent records per subject
        active_subjects_df = df[df['score'] > 0].copy()

        subject_avgs = active_subjects_df.groupby('subject')['score'].mean().round(2).to_dict()
        if general_avg_subj and general_avg_subj in subject_avgs:
            del subject_avgs[general_avg_subj]

        detailed_subject_stats = {}
        for subject, group in active_subjects_df.groupby('subject'):
            if subject == general_avg_subj: continue

            total_tested = int(len(group))
            avg_score = float(round(group['score'].mean(), 2)) if total_tested > 0 else 0.0
            count_above_10 = int(len(group[group['score'] >= 10]))
            count_below_10 = int(len(group[group['score'] < 10]))
            success_pct = float(round((count_above_10 / total_tested) * 100, 2)) if total_tested > 0 else 0.0

            detailed_subject_stats[str(subject)] = {
                'total_tested': total_tested,
                'avg_score': avg_score,
                'count_above_10': count_above_10,
                'success_pct': success_pct,
                'count_below_10': count_below_10
            }

        # Sorted students list (Ranking Table) — دائماً من البيانات الكاملة (مع الأصفار) ليكون عرض الأصفار مستقلاً عن خيار احتساب الأصفار
        if df_ranking is not None and not df_ranking.empty:
            gen_avg_subj_r = None
            for subj in df_ranking['subject'].unique():
                if subj and isinstance(subj, str) and (subj.strip() == 'المعدل العام' or subj.strip().startswith('معدل الفصل')):
                    gen_avg_subj_r = subj
                    break
            if gen_avg_subj_r:
                rank_avg_df = df_ranking[df_ranking['subject'] == gen_avg_subj_r].groupby(['student_name', 'student__class_name', 'student__academic_year'])['score'].mean().reset_index()
            else:
                rank_avg_df = df_ranking.groupby(['student_name', 'student__class_name', 'student__academic_year', 'term'])['score'].mean().reset_index()
                rank_avg_df = rank_avg_df.groupby(['student_name', 'student__class_name', 'student__academic_year'])['score'].mean().reset_index()
            student_ranking_df = rank_avg_df
        else:
            student_ranking_df = general_avg_df_full.groupby(['student_name', 'student__class_name', 'student__academic_year'])['score'].mean().reset_index()
        student_ranking_df = student_ranking_df.sort_values(by='score', ascending=False)
        student_ranking_df['score'] = student_ranking_df['score'].round(2)

        # Mark absent students
        # Explicit absentees are saved as -1.0 or result in NaN if no records exist at all
        student_ranking_df['is_absent'] = student_ranking_df['score'].apply(lambda x: pd.isna(x) or float(x) < 0)

        # We must fillna so JSON conversion works (it fails on NaN)
        student_ranking_df['score'] = student_ranking_df['score'].where(pd.notna(student_ranking_df['score']), None)

        ranking_list = student_ranking_df.to_dict('records')
        ranking_list_json = json.dumps(ranking_list)

        # Safely dump dictionaries to JSON strings to pass to template to avoid JS parsing issues with quotes
        # We explicitly cast keys and values to avoid Pandas/Numpy types that break json.dumps silently
        subject_avgs_json = json.dumps({str(k): float(v) for k, v in subject_avgs.items()})
        dist_counts_json = json.dumps({str(k): int(v) for k, v in dist_counts.items()})

        # We also need a clean Python dict of categories for the template to render directly in HTML, not just the JSON string
        clean_categories = {str(k): int(v) for k, v in categories.items()}
        categories_json = json.dumps(clean_categories)

        class_avgs_json = json.dumps({str(k): float(v) for k, v in class_avgs.items()})
        term_avgs_json = json.dumps({str(k): float(v) for k, v in term_avgs.items()})

        # Ensure deep conversion to native types for detailed stats
        clean_detailed_stats = {}
        for k, v in detailed_subject_stats.items():
            clean_detailed_stats[str(k)] = {
                'total_tested': int(v['total_tested']),
                'avg_score': float(v['avg_score']),
                'count_above_10': int(v['count_above_10']),
                'success_pct': float(v['success_pct']),
                'count_below_10': int(v['count_below_10'])
            }
        detailed_subject_stats_json = json.dumps(clean_detailed_stats)

        # Markdown representation for AI (only a sample or aggregated view to save tokens)
        pivot_df = df.pivot_table(index=['student_name', 'student__class_name'], columns='subject', values='score', aggfunc='mean').reset_index()
        try:
            sample = pivot_df.head(20)
            markdown_table = sample.to_markdown(index=False) + "\n... (Truncated for AI processing)" if len(pivot_df) > 20 else pivot_df.to_markdown(index=False)
        except Exception:
            # Fallback if to_markdown fails (e.g. tabulate issues with NaN/numpy types)
            pivot_df = pivot_df.fillna('')
            try:
                markdown_table = pivot_df.head(20).to_string(index=False) if len(pivot_df) > 20 else pivot_df.to_string(index=False)
            except Exception:
                markdown_table = str(pivot_df.head(20).to_dict()) if len(pivot_df) > 20 else str(pivot_df.to_dict())

        # Teacher Performance Comparison
        teacher_stats = []
        try:
            from .models import TeacherAssignment
            import re

            # Build mapping
            class_subj_to_teacher = {}
            for assign in TeacherAssignment.objects.all():
                t_name = f"{assign.teacher.last_name} {assign.teacher.first_name}"
                subj = assign.subject
                for c in assign.classes:
                    class_subj_to_teacher[(c, subj)] = t_name

            def get_teacher(row):
                lvl = row['student__academic_year']
                cls = row['student__class_name']
                subj = row['subject']

                lvl_digit = "1"
                if "ثانية" in lvl or "2" in lvl: lvl_digit = "2"
                elif "ثالثة" in lvl or "3" in lvl: lvl_digit = "3"
                elif "رابعة" in lvl or "4" in lvl: lvl_digit = "4"

                cls_digit = "".join(re.findall(r'\d+', cls))
                if not cls_digit: cls_digit = "1"

                shortcut = f"{lvl_digit}م{cls_digit}"

                if (shortcut, subj) in class_subj_to_teacher:
                    return class_subj_to_teacher[(shortcut, subj)]

                for (c, s), t_name in class_subj_to_teacher.items():
                    if c == shortcut and (s in subj or subj in s):
                        return t_name
                return "غير مسند"

            teacher_df = df[df['score'] > 0].copy()
            teacher_df['teacher_name'] = teacher_df.apply(get_teacher, axis=1)
            teacher_df = teacher_df[teacher_df['teacher_name'] != "غير مسند"]

            for t_name, group in teacher_df.groupby('teacher_name'):
                total_t = len(group)
                avg_score_t = float(round(group['score'].mean(), 2)) if total_t > 0 else 0.0
                above_10_t = int(len(group[group['score'] >= 10]))
                success_pct_t = float(round((above_10_t / total_t) * 100, 2)) if total_t > 0 else 0.0
                teacher_stats.append({
                    'teacher_name': t_name,
                    'total_tested': total_t,
                    'avg_score': avg_score_t,
                    'success_pct': success_pct_t
                })
            # Sort by average score descending
            teacher_stats = sorted(teacher_stats, key=lambda x: x['avg_score'], reverse=True)
        except Exception as e:
            print("Error in teacher stats:", e)

        return {
            'total_students': total_students,
            'teacher_stats': teacher_stats,
            'total_males': total_males,
            'total_females': total_females,
            'total_repeaters': total_repeaters,
            'avg_age': avg_age,
            'general_avg': general_avg,
            'success_rate': success_rate,
            'failures_count': failures_count,
            'success_count': success_count,
            'class_avgs': class_avgs_json,
            'term_avgs': term_avgs_json,
            'std_dev': std_dev,
            'distribution': dist_counts_json,
            'categories_dict': clean_categories,
            'categories': categories_json,
            'subject_avgs': subject_avgs_json,
            'detailed_subject_stats': detailed_subject_stats,
            'detailed_subject_stats_json': detailed_subject_stats_json,
            'ranking_list': ranking_list,
            'ranking_list_json': ranking_list_json,
            'markdown_data': markdown_table
        }

    except Exception as e:
        logger.error(f"Pandas analysis error: {e}")
        return None
