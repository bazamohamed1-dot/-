import os
import requests
from io import BytesIO
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class DocumentProcessor:
    @staticmethod
    def extract_text_from_file(file_obj):
        """
        Extracts text from uploaded file object (PDF, TXT, etc.)
        """
        text = ""
        filename = file_obj.name.lower()

        try:
            if filename.endswith('.pdf'):
                reader = PdfReader(file_obj)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            elif filename.endswith('.txt'):
                text = file_obj.read().decode('utf-8', errors='ignore')
            elif filename.endswith('.md'):
                text = file_obj.read().decode('utf-8', errors='ignore')
            # Add image processing (OCR) here if Tesseract is available
            else:
                text = f"[File: {filename} uploaded. No text extraction supported.]"

            return text.strip()
        except Exception as e:
            logger.error(f"Text Extraction Error: {e}")
            return f"[Error extracting text: {str(e)}]"

    @staticmethod
    def extract_text_from_url(url):
        """
        Fetches URL and extracts main text content.
        """
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                # Remove scripts and styles
                for script in soup(["script", "style"]):
                    script.extract()

                text = soup.get_text()
                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = '\n'.join(chunk for chunk in chunks if chunk)
                return text[:5000] # Limit size
            else:
                return f"[URL Fetch Failed: {response.status_code}]"
        except Exception as e:
            logger.error(f"URL Fetch Error: {e}")
            return f"[Error processing URL: {str(e)}]"
