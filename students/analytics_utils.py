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

        # 2. General Stats
        total_students = df['student_name'].nunique()

        # Determine the "General Average" (المعدل العام) subject if it exists, otherwise use mean of all scores
        has_general_avg = 'المعدل العام' in df['subject'].values

        if has_general_avg:
            general_avg_df = df[df['subject'] == 'المعدل العام']
        else:
            # If no explicit general average subject, we calculate it per student per term
            general_avg_df = df.groupby(['student_name', 'student__class_name', 'student__academic_year', 'term'])['score'].mean().reset_index()

        general_avg = general_avg_df['score'].mean()
        general_avg = round(general_avg, 2) if not pd.isna(general_avg) else 0

        # Success Rate
        failures_count = general_avg_df[general_avg_df['score'] < 10]['student_name'].nunique()
        success_count = total_students - failures_count
        success_rate = round((success_count / total_students) * 100, 2) if total_students > 0 else 0

        # Class Comparison (Average per class)
        class_avgs = general_avg_df.groupby('student__class_name')['score'].mean().round(2).to_dict()

        # Trend Analysis (Average per term)
        term_avgs = general_avg_df.groupby('term')['score'].mean().round(2).to_dict()

        # Distribution / Histogram (Ranges)
        scores = general_avg_df['score'].dropna()
        std_dev = round(scores.std(), 2) if len(scores) > 1 else 0

        bins = [0, 9.99, 11.99, 13.99, 15.99, 20]
        labels = ['<10', '10-11.99', '12-13.99', '14-15.99', '16-20']
        dist_counts = pd.cut(scores, bins=bins, labels=labels, right=True, include_lowest=True).value_counts().to_dict()

        # Categorization (Pie Chart)
        # ممتاز (Excellent >= 16), جيد (Good 14-15.99), متوسط (Average 10-13.99), متعثر (Struggling < 10)
        cat_bins = [0, 9.99, 13.99, 15.99, 20]
        cat_labels = ['متعثر', 'متوسط', 'جيد', 'ممتاز']
        categories = pd.cut(scores, bins=cat_bins, labels=cat_labels, right=True, include_lowest=True).value_counts().to_dict()

        # Subject Averages Comparison
        subject_avgs = df.groupby('subject')['score'].mean().round(2).to_dict()
        if 'المعدل العام' in subject_avgs:
            del subject_avgs['المعدل العام']

        # Sorted students list (Ranking Table)
        # Average per student across all terms in the queryset
        student_ranking_df = general_avg_df.groupby(['student_name', 'student__class_name'])['score'].mean().reset_index()
        student_ranking_df = student_ranking_df.sort_values(by='score', ascending=False)
        student_ranking_df['score'] = student_ranking_df['score'].round(2)

        ranking_list = student_ranking_df.to_dict('records')

        # Markdown representation for AI (only a sample or aggregated view to save tokens)
        pivot_df = df.pivot_table(index=['student_name', 'student__class_name'], columns='subject', values='score', aggfunc='mean').reset_index()
        markdown_table = pivot_df.head(20).to_markdown(index=False) + "\n... (Truncated for AI processing)" if len(pivot_df) > 20 else pivot_df.to_markdown(index=False)

        return {
            'total_students': total_students,
            'general_avg': general_avg,
            'success_rate': success_rate,
            'failures_count': failures_count,
            'success_count': success_count,
            'class_avgs': class_avgs,
            'term_avgs': term_avgs,
            'std_dev': std_dev,
            'distribution': dist_counts,
            'categories': categories,
            'subject_avgs': subject_avgs,
            'ranking_list': ranking_list,
            'markdown_data': markdown_table
        }

    except Exception as e:
        logger.error(f"Pandas analysis error: {e}")
        return None
