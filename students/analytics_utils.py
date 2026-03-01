
import pandas as pd
import logging
from django.db.models import QuerySet

logger = logging.getLogger(__name__)

def analyze_grades_locally(grades_qs: QuerySet):
    """
    Takes a Django QuerySet of Grade objects and uses Pandas to perform local statistical analysis.
    Returns a dictionary with stats and a Markdown representation of the data.
    """
    if not grades_qs.exists():
        return None

    try:
        # 1. Convert QuerySet to Pandas DataFrame
        data = list(grades_qs.values('student__full_name', 'student__class_name', 'subject', 'term', 'score'))
        df = pd.DataFrame(data)

        # 2. Basic Stats
        total_students = df['student__full_name'].nunique()

        # Average per subject
        subject_avgs = df.groupby('subject')['score'].mean().round(2).to_dict()

        # General Average (if "المعدل العام" exists in subjects, or overall average)
        general_avg = df[df['subject'] == 'المعدل العام']['score'].mean()
        if pd.isna(general_avg):
            general_avg = df['score'].mean()
        general_avg = round(general_avg, 2)

        # 3. Failures & Top Students (Based on General Average or overall scores)
        # Pivot the table to have one row per student, columns as subjects
        pivot_df = df.pivot_table(index=['student__full_name', 'student__class_name'], columns='subject', values='score', aggfunc='mean').reset_index()

        # Determine sorting column
        sort_col = 'المعدل العام' if 'المعدل العام' in pivot_df.columns else pivot_df.columns[-1]

        # Top 3
        top_students_df = pivot_df.sort_values(by=sort_col, ascending=False).head(3)
        top_students = [f"{row['student__full_name']} ({row[sort_col]})" for _, row in top_students_df.iterrows()]

        # Failures (Score < 10)
        failures_count = pivot_df[pivot_df[sort_col] < 10].shape[0]
        success_count = total_students - failures_count

        # 4. Convert to Markdown for Deep Analysis API
        # Only take a subset of columns to save tokens if it's too large, but for now we send the whole pivot table
        markdown_table = pivot_df.to_markdown(index=False)

        return {
            'total_students': total_students,
            'general_avg': general_avg,
            'subject_avgs': subject_avgs,
            'top_students': top_students,
            'failures_count': failures_count,
            'success_count': success_count,
            'markdown_data': markdown_table
        }

    except Exception as e:
        logger.error(f"Pandas analysis error: {e}")
        return None
