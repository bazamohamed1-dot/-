import pandas as pd
import numpy as np
from scipy import stats
from sklearn.linear_model import LinearRegression
import logging
import json
from .models import Grade, Student, ExpertAnalysisRun, StudentExpertData, CohortExpertData

logger = logging.getLogger(__name__)

def run_expert_engine(current_academic_year, current_term, prev_academic_year):
    """
    Executes the Deep Expert Analysis Engine.
    1. Z-Score Scaler
    2. Linear Regression (Predictions & Residuals)
    3. Correlation Matrix (Heatmap)
    4. Sensitivity (Beta Coefficients)
    5. Cohort Effect
    """
    logger.info(f"Starting Expert Engine: {current_academic_year} {current_term} vs {prev_academic_year}")

    try:
        # Create a new run record
        run_record = ExpertAnalysisRun.objects.create(
            academic_year=current_academic_year,
            term=current_term,
            status='running'
        )

        # 1. Fetch data
        # Fetch current year grades
        curr_grades = Grade.objects.filter(academic_year=current_academic_year).select_related('student')
        if not curr_grades.exists():
            run_record.status = 'failed: no current data'
            run_record.save()
            return False

        # Fetch previous year grades (for baseline/prediction)
        prev_grades = Grade.objects.filter(academic_year=prev_academic_year).select_related('student')

        # Build DataFrames
        curr_data = list(curr_grades.values('student__id', 'student__student_id_number', 'student__academic_year', 'student__class_name', 'student__class_code', 'subject', 'term', 'score'))
        prev_data = list(prev_grades.values('student__id', 'student__student_id_number', 'student__academic_year', 'subject', 'term', 'score'))

        df_curr = pd.DataFrame(curr_data)
        df_prev = pd.DataFrame(prev_data)

        if df_curr.empty:
            run_record.status = 'failed: empty dataframe'
            run_record.save()
            return False

        # Clean data (remove zeros and negative scores if they represent absence)
        df_curr = df_curr[df_curr['score'] > 0]
        if not df_prev.empty:
            df_prev = df_prev[df_prev['score'] > 0]

        levels = df_curr['student__academic_year'].unique()

        # Group data by level for Cohort Analysis
        for level in levels:
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
            # Fill NaN with mean to avoid breaking correlation
            pivot_curr_filled = pivot_curr.fillna(pivot_curr.mean())
            corr_matrix = pivot_curr_filled.corr().round(3)

            # Replace NaNs in corr_matrix with 0 for JSON serialization
            corr_matrix = corr_matrix.fillna(0)
            corr_dict = corr_matrix.to_dict()

            # --- C. SENSITIVITY ANALYSIS (Beta Coefficients) ---
            # Multiple Regression to find the "Ruling Subject" (بيضة القبان)
            # Dependent variable: General Average (المعدل العام) or average of all subjects
            betas = {}
            ruling_subject = None

            if 'المعدل العام' in pivot_curr_filled.columns:
                y = pivot_curr_filled['المعدل العام']
                X = pivot_curr_filled.drop(columns=['المعدل العام'])

                if not X.empty and len(X) > 1:
                    try:
                        model = LinearRegression()
                        model.fit(X, y)
                        # Beta coefficients
                        for i, col in enumerate(X.columns):
                            betas[col] = float(model.coef_[i])

                        # Find ruling subject (highest positive impact)
                        if betas:
                            ruling_subject = max(betas, key=betas.get)
                    except Exception as e:
                        logger.error(f"Error calculating sensitivity for {level}: {e}")

            # --- D. COHORT EFFECT ---
            # Compare level Z-Scores between current year and previous year
            curr_avg_z = 0.0
            prev_avg_z = 0.0
            cohort_effect = "لا توجد بيانات سابقة كافية"

            if not df_level_prev.empty:
                df_level_prev['z_score'] = df_level_prev.groupby('subject')['score'].transform(lambda x: stats.zscore(x, ddof=1) if len(x) > 1 and x.std() > 0 else 0)
                # Note: The mean of Z-scores within the same group is 0.
                # To compare cohorts, we need a standard baseline.
                # A better approach: Compare raw average, or standardize current year using previous year's mean/std.

                # Standardizing current year against previous year's distribution
                subject_stats_prev = df_level_prev.groupby('subject')['score'].agg(['mean', 'std']).reset_index()

                # Merge prev stats into current to calculate relative Z-Score
                df_rel = pd.merge(df_level_curr, subject_stats_prev, on='subject', suffixes=('', '_prev'))

                # Calculate relative Z-score: (Current Score - Prev Mean) / Prev Std
                # If Prev Std is 0 or NaN, set Z-score to 0
                df_rel['rel_z_score'] = np.where(df_rel['std'] > 0, (df_rel['score'] - df_rel['mean']) / df_rel['std'], 0)

                curr_avg_z = float(df_rel['rel_z_score'].mean())
                if pd.isna(curr_avg_z): curr_avg_z = 0.0

                # Prev avg Z against itself is ~0
                prev_avg_z = 0.0

                if curr_avg_z < -0.2:
                    cohort_effect = "تراجع عام في المستوى (تأثير الفوج/المنهج)"
                elif curr_avg_z > 0.2:
                    cohort_effect = "تحسن عام في المستوى (تأثير الفوج/المنهج)"
                else:
                    cohort_effect = "مستوى الفوج مستقر مقارنة بالعام الماضي"

            # Save Cohort Data
            CohortExpertData.objects.create(
                run=run_record,
                academic_year_level=level,
                correlation_matrix=corr_dict,
                current_year_z_score_avg=curr_avg_z,
                last_year_z_score_avg=prev_avg_z,
                cohort_effect_analysis=cohort_effect,
                sensitivity_betas=betas,
                ruling_subject=ruling_subject
            )

            # --- E. PATTERN FINDER & FUTURE FORECAST (Student Level) ---
            # We need to calculate Linear Regression per student to find Trend and Residuals
            # Y = ax + b, where x is time (terms), y is score

            students_in_level = df_level_curr['student__id'].unique()

            for student_id in students_in_level:
                student_curr = df_level_curr[df_level_curr['student__id'] == student_id]
                student_prev = pd.DataFrame()
                if not df_prev.empty:
                    student_prev = df_prev[df_prev['student__id'] == student_id]

                # Combine history for trend
                history = []
                # Simple time mapping: Prev Year Terms = 1, 2, 3; Curr Year Terms = 4, 5, 6
                # This is a simplification. We'll just order them chronologically.
                time_x = []
                scores_y = []
                term_counter = 1

                # Process previous year terms if available
                if not student_prev.empty:
                    # Get general average per term
                    prev_avgs = student_prev.groupby('term')['score'].mean().reset_index()
                    for _, row in prev_avgs.iterrows():
                        history.append({"term": f"{prev_academic_year} - {row['term']}", "score": round(row['score'], 2)})
                        time_x.append(term_counter)
                        scores_y.append(row['score'])
                        term_counter += 1

                # Process current year terms
                curr_avgs = student_curr.groupby('term')['score'].mean().reset_index()
                current_avg_score = 0
                for _, row in curr_avgs.iterrows():
                    history.append({"term": f"{current_academic_year} - {row['term']}", "score": round(row['score'], 2)})
                    time_x.append(term_counter)
                    scores_y.append(row['score'])
                    if row['term'] == current_term:
                        current_avg_score = row['score']
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
                        logger.error(f"Regression error for student {student_id}: {e}")
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

                # Save Student Data
                StudentExpertData.objects.create(
                    run=run_record,
                    student_id=student_id,
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
