import pandas as pd
import logging
from django.db.models import QuerySet

logger = logging.getLogger(__name__)

def analyze_grades_locally(grades_qs: QuerySet):
    """
    Takes a Django QuerySet of Grade objects and uses Pandas to perform local statistical analysis.
    Returns a dictionary with stats and a Markdown representation of the data for the Executive Dashboard.
    """
    if not grades_qs.exists():
        return None

    try:
        # 1. Convert QuerySet to Pandas DataFrame
        data = list(grades_qs.values('student__last_name', 'student__first_name', 'student__class_name', 'student__academic_year', 'subject', 'term', 'score'))
        if not data:
            return None
        df = pd.DataFrame(data)

        # Reconstruct full_name
        df['student_name'] = df['student__last_name'].fillna('') + ' ' + df['student__first_name'].fillna('')

        import json

        # Determine the "General Average" (المعدل العام) subject if it exists, otherwise use mean of all scores
        has_general_avg = 'المعدل العام' in df['subject'].values

        if has_general_avg:
            general_avg_df = df[df['subject'] == 'المعدل العام'].copy()
        else:
            # If no explicit general average subject, we calculate it per student per term
            general_avg_df = df.groupby(['student_name', 'student__class_name', 'student__academic_year', 'term'])['score'].mean().reset_index()

        # Separate absent vs active students based on general average
        # An absent student is defined as having a general average of exactly 0.0 or NaN
        active_students_df = general_avg_df[general_avg_df['score'] > 0]
        absent_students_df = general_avg_df[(general_avg_df['score'] == 0) | (general_avg_df['score'].isna())]

        # 2. General Stats (Calculated ONLY on active students)
        total_students = general_avg_df['student_name'].nunique()
        active_students_count = active_students_df['student_name'].nunique()

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
        if 'المعدل العام' in subject_avgs:
            del subject_avgs['المعدل العام']

        detailed_subject_stats = {}
        for subject, group in active_subjects_df.groupby('subject'):
            if subject == 'المعدل العام': continue

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
        student_ranking_df['is_absent'] = student_ranking_df['score'].apply(lambda x: pd.isna(x) or x == 0)

        ranking_list = student_ranking_df.to_dict('records')

        # Safely dump dictionaries to JSON strings to pass to template to avoid JS parsing issues with quotes
        # We explicitly cast keys and values to avoid Pandas/Numpy types that break json.dumps silently
        subject_avgs_json = json.dumps({str(k): float(v) for k, v in subject_avgs.items()})
        dist_counts_json = json.dumps({str(k): int(v) for k, v in dist_counts.items()})
        categories_json = json.dumps({str(k): int(v) for k, v in categories.items()})
        class_avgs_json = json.dumps({str(k): float(v) for k, v in class_avgs.items()})
        term_avgs_json = json.dumps({str(k): float(v) for k, v in term_avgs.items()})
        detailed_subject_stats_json = json.dumps(detailed_subject_stats)

        # Markdown representation for AI (only a sample or aggregated view to save tokens)
        pivot_df = df.pivot_table(index=['student_name', 'student__class_name'], columns='subject', values='score', aggfunc='mean').reset_index()
        markdown_table = pivot_df.head(20).to_markdown(index=False) + "\n... (Truncated for AI processing)" if len(pivot_df) > 20 else pivot_df.to_markdown(index=False)

        return {
            'total_students': total_students,
            'general_avg': general_avg,
            'success_rate': success_rate,
            'failures_count': failures_count,
            'success_count': success_count,
            'class_avgs': class_avgs_json,
            'term_avgs': term_avgs_json,
            'std_dev': std_dev,
            'distribution': dist_counts_json,
            'categories': categories_json,
            'subject_avgs': subject_avgs_json,
            'detailed_subject_stats': detailed_subject_stats,
            'detailed_subject_stats_json': detailed_subject_stats_json,
            'ranking_list': ranking_list,
            'markdown_data': markdown_table
        }

    except Exception as e:
        logger.error(f"Pandas analysis error: {e}")
        return None
