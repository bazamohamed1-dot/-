from .models import SchoolMemory, SchoolSettings
import logging
import os
import random
import time
from PyPDF2 import PdfReader
from docx import Document
from bs4 import BeautifulSoup

# Provider Libraries
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

try:
    import anthropic
    HAS_CLAUDE = True
except ImportError:
    HAS_CLAUDE = False

logger = logging.getLogger(__name__)

class AIService:
    """
    Advanced AI Service with Multi-Provider Fallback (Google -> Groq -> Claude).
    Implements Load Balancing for multiple keys of the same provider.
    """

    def __init__(self, user=None):
        self.user = user
        self.settings = SchoolSettings.objects.first()

        # Load API Keys with Rotation Support
        self.gemini_keys = self._load_keys("GOOGLE_API_KEY")
        self.groq_keys = self._load_keys("GROQ_API_KEY")
        self.claude_keys = self._load_keys("ANTHROPIC_API_KEY")

        # Models Configuration (Ranked by Preference)
        self.models_config = {
            'gemini': ['gemini-1.5-flash', 'gemini-pro', 'gemini-1.0-pro'],
            'groq': ['llama3-70b-8192', 'mixtral-8x7b-32768', 'gemma2-9b-it'],
            'claude': ['claude-3-haiku-20240307', 'claude-3-sonnet-20240229']
        }

    def _load_keys(self, prefix):
        """Loads keys like KEY, KEY_2, KEY_3..."""
        keys = []
        k1 = os.environ.get(prefix)
        if k1: keys.append(k1)

        i = 2
        while True:
            k = os.environ.get(f"{prefix}_{i}")
            if not k: break
            keys.append(k)
            i += 1
        return keys

    def get_rag_context(self, query):
        keywords = query.split()
        matches = SchoolMemory.objects.filter(
            title__icontains=keywords[0]
        ) | SchoolMemory.objects.filter(content__icontains=keywords[0])

        if not matches.exists() and len(keywords) > 1:
             matches = SchoolMemory.objects.filter(title__icontains=keywords[1])

        context_text = "\n".join([f"[{m.category}] {m.title}: {m.content}" for m in matches[:3]])
        return context_text

    def generate_response(self, system_instruction, user_query, rag_enabled=True, mode=None):
        # 1. Prepare Context
        context = ""
        if rag_enabled:
            context = self.get_rag_context(user_query)

        # Adjust Prompt based on Mode
        directives = """
        - Concise for greetings (1-2 sentences).
        - Detailed for tasks/plans.
        - Use Markdown.
        """

        if mode == 'bot_helper':
            directives = """
            - Role: In-App Helper Bot.
            - Goal: Explain how to use the app features briefly.
            - Tone: Helpful, direct, very concise (max 3 sentences).
            - NO long strategic advice. Just "How-To".
            """

        prompt = f"""
        System Role: Expert School Director Consultant / Helper.
        Context: {system_instruction}
        School Data: {context if context else "None"}
        User Query: {user_query}

        Directives:
        {directives}
        """

        # 2. Provider Cascade Strategy
        # Priority 1: Google Gemini (Fast & Free Tier usually available)
        if self.gemini_keys and HAS_GEMINI:
            resp = self._try_gemini_rotation(prompt)
            if resp: return resp

        # Priority 2: Groq (Super Fast)
        if self.groq_keys and HAS_GROQ:
            resp = self._try_groq_rotation(prompt)
            if resp: return resp

        # Priority 3: Claude (High Quality)
        if self.claude_keys and HAS_CLAUDE:
            resp = self._try_claude_rotation(prompt)
            if resp: return resp

        return "⚠️ عذراً، جميع خوادم الذكاء الاصطناعي مشغولة حالياً أو المفاتيح غير صالحة. يرجى المحاولة لاحقاً."

    def _try_gemini_rotation(self, prompt):
        """Round-Robin Load Balancing for Gemini Keys"""
        keys = list(self.gemini_keys)
        random.shuffle(keys)

        for key in keys:
            genai.configure(api_key=key)
            for model_name in self.models_config['gemini']:
                try:
                    model = genai.GenerativeModel(model_name)
                    config = genai.types.GenerationConfig(
                        candidate_count=1,
                        temperature=0.7
                    )
                    response = model.generate_content(prompt, generation_config=config)
                    if response and response.text:
                        return response.text
                except Exception as e:
                    logger.warning(f"Gemini Fail ({model_name}): {e}")
                    if "429" in str(e) or "404" in str(e):
                        continue # Try next model/key
                    break # Other errors might be prompt related
        return None

    def _try_groq_rotation(self, prompt):
        """Round-Robin Load Balancing for Groq Keys"""
        keys = list(self.groq_keys)
        random.shuffle(keys)

        for key in keys:
            try:
                client = Groq(api_key=key)
                for model in self.models_config['groq']:
                    try:
                        completion = client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model=model,
                        )
                        return completion.choices[0].message.content
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"Groq Fail: {e}")
        return None

    def _try_claude_rotation(self, prompt):
        """Round-Robin Load Balancing for Claude Keys"""
        keys = list(self.claude_keys)
        random.shuffle(keys)

        for key in keys:
            try:
                client = anthropic.Anthropic(api_key=key)
                for model in self.models_config['claude']:
                    try:
                        message = client.messages.create(
                            model=model,
                            max_tokens=1024,
                            messages=[{"role": "user", "content": prompt}]
                        )
                        return message.content[0].text
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"Claude Fail: {e}")
        return None

# Legacy/Stub Functions
def analyze_assignment_document(assignment): pass
def analyze_global_assignment(file_path): pass
def analyze_global_assignment_content(file_path):
    # Delegate to smart analyzer
    from students.utils_tools.smart_assignment_analyzer import extract_from_excel, extract_from_word
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.xlsx', '.xls']: return extract_from_excel(file_path)
    if ext == '.docx': return extract_from_word(file_path)
    return []
