from django.test import TestCase
from students.utils_tools.smart_assignment_analyzer import extract_from_excel
import pandas as pd
import os
import openpyxl

class SmartAnalyzerTest(TestCase):
    def test_excel_parsing(self):
        # Create a mock dataframe
        data = {
            0: [float('nan'), float('nan'), 'الرقم', 'الأستاذ', 'الرتبة', 'المادة', 'الحجم الساعي', 'الأقسام المسندة'],
            1: [float('nan'), float('nan'), 1, 'اعمارة عمر', 'أستاذ تعليم متوسط', 'اجتماعيات', 18, '1م4 2م4 3م4'],
            2: [float('nan'), float('nan'), 2, 'بوعيشة حيزية', 'أستاذ', 'اجتماعيات', 18, '4م1-4م2']
        }
        df = pd.DataFrame.from_dict(data, orient='index')

        # Save to temp excel
        filename = 'temp_test.xlsx'
        df.to_excel(filename, index=False, header=False)

        try:
            candidates = extract_from_excel(filename)

            # Check Count
            # The function now returns a list of dictionaries
            # We must adapt the test expectation based on the implementation of extract_from_excel
            # which iterates rows and calls _extract_candidate_from_text

            # Since the dummy logic in my `write_file` implementation is regex-based, let's see if it works.

            # Actually, my previous implementation of `smart_assignment_analyzer.py` had `extract_from_excel`
            # iterating rows. Let's trust the logic for now and debug if fails.

            print(f"Candidates found: {candidates}")

            # Check Count
            # Row 0 is header (might produce candidate if regex matches, unlikely)
            # Row 1 is teacher 1
            # Row 2 is teacher 2

            # The test expects 2 valid candidates
            self.assertTrue(len(candidates) >= 2)

            # Check First Teacher
            # Note: The extraction logic might be fuzzy. Let's find by name.
            c1 = next((c for c in candidates if 'اعمارة عمر' in c['name']), None)
            self.assertIsNotNone(c1)
            # Normalization might change 1م4 to 1AM4
            self.assertIn('1AM4', c1['classes'])

            # Check Second Teacher (Split by dash)
            c2 = next((c for c in candidates if 'بوعيشة حيزية' in c['name']), None)
            self.assertIsNotNone(c2)
            self.assertIn('4AM1', c2['classes'])
            self.assertIn('4AM2', c2['classes'])

        finally:
            if os.path.exists(filename):
                os.remove(filename)
