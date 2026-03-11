import pandas as pd
import re
import os
import logging
from docx import Document

logger = logging.getLogger(__name__)

# Pattern to detect any variation of class name:
# e.g., "1 م 1", "1M1", "1 AM 1", "4متوسط3"
# Broad pattern: Digit + (optional text) + Digit
CLASS_REGEX = r'\b(\d+)\s*[\u0600-\u06FFa-zA-Z]*\s*(\d+)\b'

def normalize_class_name(raw_name):
    """
    Returns the raw name cleaned up but NOT forced to '1AM1' format unless absolutely necessary.
    The user wants to keep the original Arabic format if present.
    Example: "1 م 1" -> "1 م 1"
    """
    if not isinstance(raw_name, str):
        return None

    clean = raw_name.strip()
    # If it's just spaces, return None
    if not clean: return None

    return clean

def normalize_subject(subject):
    """
    Maps various subject names to standard database values.
    """
    if not isinstance(subject, str):
        return None

    s = subject.strip()

    subjects_map = {
        'رياضيات': 'رياضيات', 'Math': 'رياضيات',
        'فيزياء': 'فيزياء', 'Physique': 'فيزياء',
        'علوم': 'علوم طبيعية', 'Science': 'علوم طبيعية',
        'عربية': 'لغة عربية', 'Arabe': 'لغة عربية',
        'فرنسية': 'لغة فرنسية', 'Français': 'لغة فرنسية',
        'انجليزية': 'لغة إنجليزية', 'Anglais': 'لغة إنجليزية',
        'تاريخ': 'تاريخ وجغرافيا', 'Histoire': 'تاريخ وجغرافيا',
        'جغرافيا': 'تاريخ وجغرافيا', 'Géographie': 'تاريخ وجغرافيا',
        'إسلامية': 'تربية إسلامية', 'Islamique': 'تربية إسلامية',
        'مدنية': 'تربية مدنية', 'Civique': 'تربية مدنية',
        'إعلام': 'إعلام آلي', 'Informatique': 'إعلام آلي',
        'تكنولوجيا': 'تكنولوجيا', 'Technologie': 'تكنولوجيا',
        'بدنية': 'تربية بدنية', 'Sport': 'تربية بدنية',
        'موسيقى': 'تربية موسيقية', 'Musique': 'تربية موسيقية',
        'تشكيلية': 'تربية تشكيلية', 'Dessin': 'تربية تشكيلية',
        'أمازيغية': 'لغة أمازيغية', 'Tamazight': 'لغة أمازيغية'
    }

    for key, val in subjects_map.items():
        if key in s:
            return val
    return None

def extract_from_excel(file_path):
    """
    Extracts assignment candidates from an Excel file (Schedule).
    Handles tabular schedules correctly without confusing horizontal columns.
    """
    candidates = []
    try:
        # Load workbook, without forward filling axis=1 which corrupts the row
        df = pd.read_excel(file_path, header=None)

        # Iterate through rows and columns carefully
        for idx, row in df.iterrows():
            row_cells = [str(x).strip() for x in row.values if str(x).lower() != 'nan' and str(x).strip() != '']

            if not row_cells:
                continue

            # We process cell by cell to group subjects and classes locally
            # Or we can do a smart line by line join if it's just a simple table.
            # But the main issue was ffill(axis=1) duplicating data across empty columns.
            row_text = "  ".join(row_cells)

            # Extract basic info
            extracted = _extract_candidate_from_text(row_text)
            if extracted:
                _merge_candidate(candidates, extracted)

    except Exception as e:
        logger.error(f"Excel Extraction Failed: {e}")

    return candidates

def extract_from_pdf(file_path):
    """
    Extracts assignment candidates from a PDF document using pdfplumber.
    It reads the text layout to find Teacher Names, Subjects, and Classes.
    This saves massive AI tokens by doing local text processing.
    """
    candidates = []
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                # Try extracting tables first
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        # row is a list of strings
                        row_text = " ".join([str(cell).strip() for cell in row if cell])
                        extracted = _extract_candidate_from_text(row_text)
                        if extracted:
                            _merge_candidate(candidates, extracted)

                # Also try normal text extraction line by line in case it's not a standard table
                text = page.extract_text()
                if text:
                    for line in text.split('\n'):
                        extracted = _extract_candidate_from_text(line)
                        if extracted:
                            _merge_candidate(candidates, extracted)

    except Exception as e:
        logger.error(f"PDF Extraction Failed: {e}")

    return candidates

def extract_from_word(file_path):
    """
    Extracts assignment candidates from a Word document.
    Reads tables and paragraphs.
    """
    candidates = []
    try:
        doc = Document(file_path)

        # 1. Process Tables
        for table in doc.tables:
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    txt = cell.text.strip()
                    if txt:
                        row_text.append(txt)

                line = " ".join(row_text)
                extracted = _extract_candidate_from_text(line)
                if extracted:
                    _merge_candidate(candidates, extracted)

        # 2. Process Paragraphs (if not in table)
        for para in doc.paragraphs:
            extracted = _extract_candidate_from_text(para.text)
            if extracted:
                _merge_candidate(candidates, extracted)

    except Exception as e:
        logger.error(f"Word Extraction Failed: {e}")

    return candidates

def _extract_candidate_from_text(text):
    """
    Helper to parse a single line of text for Teacher Name, Subject, Classes.
    """
    text = text.strip()
    if len(text) < 5:
        return None

    # 1. Identify Subject
    subject = normalize_subject(text)

    # 2. Identify Classes
    # Pattern: 1M1, 4AM2, 4 م 3, 1 م 1
    # We look for digit + (optional chars) + digit

    # New Regex to catch "1 م 1" specifically along with "1M1"
    # Matches: "1" then spaces then "م" or "M" or "AM" then spaces then "1"
    raw_classes = re.findall(r'\b\d+\s*(?:M|AM|م|متوسط)\s*\d+\b', text, re.IGNORECASE)

    found_classes = []
    for rc in raw_classes:
        # Keep it essentially as is, just clean spaces
        # But user wants consistency? "1 م 2" vs "1م2"
        # Let's clean extra internal spaces
        clean_c = re.sub(r'\s+', ' ', rc).strip()
        found_classes.append(clean_c)

    # Sometimes AI output or files use formats like "أولى 1", we shouldn't rely solely on "م" locally.
    # Let's expand local extraction to catch words
    word_classes = re.findall(r'\b(?:أولى|ثانية|ثالثة|رابعة|الاولى|الثانية|الثالثة|الرابعة|اولى|ثانيه|ثالثه|رابعه)\s*(?:متوسط)?\s*\d+\b', text)
    for wc in word_classes:
        clean_wc = re.sub(r'\s+', ' ', wc).strip()
        found_classes.append(clean_wc)

    # If no subject and no classes, unlikely to be a schedule row
    if not subject and not found_classes:
        return None

    # 3. Identify Teacher Name
    # Remove subject and classes from text to find the name
    clean_text = text
    if subject:
        # Remove common subject keywords
        for key in ['رياضيات', 'علوم', 'فيزياء', 'عربية', 'فرنسية', 'انجليزية', 'تاريخ', 'جغرافيا', 'إسلامية', 'مدنية', 'تكنولوجيا', 'إعلام', 'بدنية', 'موسيقى', 'تشكيلية']:
             clean_text = clean_text.replace(key, '')

    for rc in raw_classes:
        clean_text = clean_text.replace(rc, '')

    # Remove common noise words
    noise = ['الأستاذ', 'الاستاذ', 'المادة', 'القسم', 'التوقيت', 'السيد', 'السيدة', 'الآنسة', ':', '-', '/']
    for n in noise:
        clean_text = clean_text.replace(n, ' ')

    # Remove digits (hours, room numbers)
    clean_text = re.sub(r'\d+', '', clean_text)

    name = clean_text.strip()

    # Validation
    if len(name) < 3:
        return None # Name too short

    if not found_classes:
        return None # No classes assigned?

    return {
        'name': name,
        'subject': subject if subject else '/',
        'classes': list(set(found_classes))
    }

def _merge_candidate(candidates, new_cand):
    """
    Merges entries only if Name AND Subject match.
    If Name matches but Subject is different, treats as separate assignment (e.g. Teacher X - Math vs Teacher X - Physics).
    """
    for c in candidates:
        # Strict matching on Name AND Subject to support multi-subject teachers
        if c['name'] == new_cand['name']:

            # If subjects are identical, merge classes
            if c['subject'] == new_cand['subject']:
                c['classes'].extend(new_cand['classes'])
                c['classes'] = list(set(c['classes']))
                return

            # If existing has no subject ('/'), take the new subject and merge
            # This handles cases where one row has subject, another doesn't for same teacher
            if c['subject'] == '/' and new_cand['subject'] != '/':
                c['subject'] = new_cand['subject']
                c['classes'].extend(new_cand['classes'])
                c['classes'] = list(set(c['classes']))
                return

            # If new has no subject, merge into existing
            if new_cand['subject'] == '/':
                c['classes'].extend(new_cand['classes'])
                c['classes'] = list(set(c['classes']))
                return

    # If no match found (different name OR different subject), append as new
    candidates.append(new_cand)
