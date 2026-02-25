from django.test import TestCase
from students.utils_tools.smart_assignment_analyzer import extract_from_excel
import pandas as pd
import os

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

            print(f"Candidates found: {candidates}")

            self.assertTrue(len(candidates) >= 2)

            # Check First Teacher
            c1 = next((c for c in candidates if 'اعمارة عمر' in c['name']), None)
            self.assertIsNotNone(c1)
            # New behavior: expects raw Arabic string (cleaned of extra spaces)
            # '1م4' is what the analyzer returns now
            self.assertIn('1م4', c1['classes'])

            # Check Second Teacher
            c2 = next((c for c in candidates if 'بوعيشة حيزية' in c['name']), None)
            self.assertIsNotNone(c2)
            self.assertIn('4م1', c2['classes'])
            self.assertIn('4م2', c2['classes'])

        finally:
            if os.path.exists(filename):
                os.remove(filename)
