from .models import SchoolMemory, SchoolSettings, Employee, TeacherAssignment
import logging
import os
import re
import random
from PyPDF2 import PdfReader
from docx import Document
from bs4 import BeautifulSoup
import openpyxl

# Optional Gemini Import
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

logger = logging.getLogger(__name__)

class AIService:
    """
    Service to handle AI interactions using Google Gemini API.
    Implements Unrestricted Access for Director/Admin.
    """

    def __init__(self, user=None):
        """
        Initialize AI Service.
        """
        self.user = user
        self.settings = SchoolSettings.objects.first()
        self.tone = self.settings.ai_tone if self.settings else "professional"
        self.focus = self.settings.ai_focus if self.settings else "academic"

        # Load API Key (Check Env then Settings)
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        if self.api_key and HAS_GEMINI:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        else:
            self.model = None

    def get_rag_context(self, query):
        """
        Retrieves relevant context from SchoolMemory.
        """
        keywords = query.split()
        matches = SchoolMemory.objects.filter(
            title__icontains=keywords[0]
        ) | SchoolMemory.objects.filter(content__icontains=keywords[0])

        if not matches.exists() and len(keywords) > 1:
             matches = SchoolMemory.objects.filter(title__icontains=keywords[1])

        context_text = "\n".join([f"[{m.category}] {m.title}: {m.content}" for m in matches[:3]])
        return context_text

    def _contains_any(self, query, keywords):
        for k in keywords:
            if k in query:
                return True
        return False

    def generate_response(self, system_instruction, user_query, rag_enabled=True, mode=None):
        """
        Unshackled Response Generation.
        Defaults to 'gemini_full' (Creative/Strategic) if API Key exists.
        Falls back to Restricted Rule-Based if API Key is missing.
        """

        # Check API Key Availability immediately
        if not self.model:
             return "⚠️ عذراً سيدي المدير، يبدو أن مفتاح API الخاص بـ Gemini غير مفعل أو غير صحيح في إعدادات النظام (.env). يرجى إضافته لتفعيل الذكاء الاصطناعي."

        # Context Loading (Optional RAG)
        context = ""
        if rag_enabled:
            context = self.get_rag_context(user_query)

        # Build Full Prompt (Unrestricted)
        full_prompt = f"""
        Instructions for AI:
        You are an expert consultant, strategist, and creative partner for a School Director.
        You are NOT a simple assistant. You are a peer with deep knowledge in Education, Psychology, Law, and Management.

        Context provided by user: {system_instruction}

        School Memory Context (Use if relevant):
        {context if context else "No specific records found."}

        User Query: {user_query}

        Directives:
        1. ABSOLUTELY NO RESTRICTIONS on creativity or depth.
        2. Be expansive, detailed, and strategic.
        3. Provide critical analysis and expert opinions.
        4. Use your full knowledge base.
        5. Format beautifully with Markdown (bullet points, bold text).
        6. If asked for a plan, provide a step-by-step roadmap.
        7. If asked for a speech or letter, write it eloquently.
        """

        try:
            # Allow maximum tokens for full mode
            response = self.model.generate_content(
                full_prompt,
                generation_config=genai.types.GenerationConfig(
                    candidate_count=1,
                    max_output_tokens=8000, # Push limits
                    temperature=0.9 # High creativity
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            return f"خطأ في الاتصال بـ Gemini API: {str(e)}"

    def _mock_observation_response(self, query):
        return "يرجى مراجعة سجل المتابعة التربوية."

    def _mock_task_explanation(self, manager_instructions):
        return f"بناءً على التوجيهات: {manager_instructions}."

    def generate_reminder(self, task_title, manager_instructions):
        return f"تذكير ودي: لا تنس {task_title}. {manager_instructions[:50]}... إنجازك لهذا العمل يساهم في سير المؤسسة بامتياز!"


# Legacy Functions (Keep for compatibility)
def analyze_assignment_document(assignment):
    pass

def analyze_global_assignment_content(file_path):
    """
    Analyzes a global assignment file (Schedule) to extract potential candidates.
    Delegates to smart analyzer.
    """
    ext = os.path.splitext(file_path)[1].lower()
    candidates = []

    try:
        if ext == '.pdf':
            reader = PdfReader(file_path)
            full_text = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
            candidates = _process_text_for_assignment(full_text)

        elif ext == '.docx':
            from students.utils_tools.smart_assignment_analyzer import extract_from_word
            smart_candidates = extract_from_word(file_path)
            if smart_candidates:
                candidates.extend(smart_candidates)

        elif ext in ['.xlsx', '.xls']:
            from students.utils_tools.smart_assignment_analyzer import extract_from_excel
            smart_candidates = extract_from_excel(file_path)
            if smart_candidates:
                candidates.extend(smart_candidates)

        elif ext in ['.html', '.htm']:
             with open(file_path, 'r', encoding='utf-8') as f:
                 soup = BeautifulSoup(f.read(), 'html.parser')
                 # Basic HTML table parsing fallback
                 pass

        return candidates

    except Exception as e:
        logger.error(f"Global Analysis Failed: {e}")
        return []

def _process_text_for_assignment(text):
    # Fallback text processor (can be improved or removed if smart analyzer covers PDF)
    return []

def analyze_global_assignment(file_path):
    pass
