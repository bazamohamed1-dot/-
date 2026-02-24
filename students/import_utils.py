import openpyxl
import xlrd
from bs4 import BeautifulSoup
from docx import Document
from PyPDF2 import PdfReader
import re
from datetime import datetime, date

def extract_rows_from_file(file):
    """
    Extracts rows from any supported file type (Excel, Word, HTML, PDF).
    Returns a generator of lists.
    """
    file.seek(0)
    filename = file.name.lower()

    if filename.endswith('.xlsx'):
        try:
            wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
            ws = wb.active
            for row in ws.iter_rows(values_only=True):
                yield list(row)
        except:
            # Fallback for HTML disguised as XLSX
            file.seek(0)
            content = file.read()
            yield from _parse_html_table(content)

    elif filename.endswith('.xls'):
        try:
            content = file.read()
            wb = xlrd.open_workbook(file_contents=content)
            sheet = wb.sheet_by_index(0)
            for r in range(sheet.nrows):
                yield sheet.row_values(r)
        except:
             # Fallback for HTML disguised as XLS
            yield from _parse_html_table(content)

    elif filename.endswith('.docx'):
        doc = Document(file)
        for table in doc.tables:
            for row in table.rows:
                yield [cell.text.strip() for cell in row.cells]

    elif filename.endswith('.pdf'):
        # PDF is hard to get "rows", return parsing results as pseudo-rows
        # This is a best-effort for simple tables
        reader = PdfReader(file)
        for page in reader.pages:
            text = page.extract_text()
            for line in text.split('\n'):
                yield line.split() # Naive split

    elif filename.endswith('.html') or filename.endswith('.htm'):
        content = file.read()
        yield from _parse_html_table(content)

def _parse_html_table(content):
    soup = BeautifulSoup(content, 'html.parser')
    table = soup.find('table')
    if table:
        for tr in table.find_all('tr'):
            cells = tr.find_all(['td', 'th'])
            yield [cell.get_text(strip=True) for cell in cells]
