import pandas as pd
import logging
from django.db.models import QuerySet

logger = logging.getLogger(__name__)

import re

def format_class_name(level, class_name):
    if pd.isna(level) or pd.isna(class_name):
        return f"{level} {class_name}"
    level = str(level).strip()
    class_name = str(class_name).strip()
    level_match = re.search(r"\d+", level)
    if not level_match:
        return class_name
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

def analyze_grades_locally(grades_qs: QuerySet, subject_filter=None, include_zeros=True):
    """
    Takes a Django QuerySet of Grade objects and uses Pandas to perform local statistical analysis.
    Returns a dictionary with stats and a Markdown representation of the data for the Executive Dashboard.
    """
    if not grades_qs.exists():
        return None

    try:
        # 1. Convert QuerySet to Pandas DataFrame
        data = list(grades_qs.values('student__last_name', 'student__first_name', 'student__class_name', 'student__academic_year', 'student__gender', 'student__is_repeater', 'student__date_of_birth', 'subject', 'term', 'score'))
        if not data:
            return None
        df = pd.DataFrame(data)

        # Remove zeros from dataframe entirely if include_zeros is False
        if not include_zeros:
            df = df[df['score'] != 0.0]

        # Reconstruct full_name
        df['student_name'] = df['student__last_name'].fillna('') + ' ' + df['student__first_name'].fillna('')

        # Format class names properly (e.g. 1م1 instead of just 1)
        df['student__class_name'] = df.apply(lambda row: format_class_name(row['student__academic_year'], row['student__class_name']), axis=1)

        import json
        from datetime import date

        general_avg_subj = None

        # If a specific subject filter is passed (e.g., specific teacher subject), calculate metrics based on THAT subject
        if subject_filter:
            general_avg_df = df.groupby(['student_name', 'student__class_name', 'student__academic_year', 'term'])['score'].mean().reset_index()
        else:
            # Determine the "General Average" (المعدل العام) subject if it exists, otherwise use mean of all scores
            for subj in df['subject'].unique():
                if subj and isinstance(subj, str) and (subj.strip() == 'المعدل العام' or subj.strip().startswith('معدل الفصل')):
                    general_avg_subj = subj
                    break

            if general_avg_subj:
                general_avg_df = df[df['subject'] == general_avg_subj].copy()
            else:
                # If no explicit general average subject, we calculate it per student per term
                general_avg_df = df.groupby(['student_name', 'student__class_name', 'student__academic_year', 'term'])['score'].mean().reset_index()

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

        # Sorted students list (Ranking Table)
        # Average per student across all terms in the queryset
        student_ranking_df = general_avg_df.groupby(['student_name', 'student__class_name'])['score'].mean().reset_index()
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
        markdown_table = pivot_df.head(20).to_markdown(index=False) + "\n... (Truncated for AI processing)" if len(pivot_df) > 20 else pivot_df.to_markdown(index=False)

        return {
            'total_students': total_students,
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
