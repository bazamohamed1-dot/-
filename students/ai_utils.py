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
    from google import genai
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
    Updated to use `google-genai` (Official v1 SDK).
    """

    def __init__(self, user=None):
        self.user = user
        self.settings = SchoolSettings.objects.first()

        # Load API Keys
        self.gemini_keys = self._load_keys("GOOGLE_API_KEY")
        self.groq_keys = self._load_keys("GROQ_API_KEY")
        self.claude_keys = self._load_keys("ANTHROPIC_API_KEY")

        # Models Config
        self.models_config = {
            # Try 2.0 first (Fastest), then 1.5-flash (Stable), then Pro
            'gemini': ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro'],
            # Updated to use currently active Groq models (removed decommissioned models)
            'groq': ['llama3-8b-8192', 'gemma2-9b-it'],
            'claude': ['claude-3-haiku-20240307']
        }

    def _load_keys(self, prefix):
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
        matches = SchoolMemory.objects.filter(title__icontains=keywords[0])
        context_text = "\n".join([f"[{m.category}] {m.title}: {m.content}" for m in matches[:3]])
        return context_text

    def generate_response(self, system_instruction, user_query, rag_enabled=True, mode=None):
        context = ""
        if rag_enabled:
            context = self.get_rag_context(user_query)

        # Mode-specific directives
        directives = "- Concise for greetings. Detailed for plans."

        # UI Knowledge map for the floating bot
        ui_knowledge_map = """
        أنت المساعد التقني العائم لتطبيق "تسيير متوسطة بوشنافة عمر". مهمتك هي إرشاد المستخدمين حول كيفية استخدام التطبيق ومكان العثور على الأزرار والميزات.
        إليك خريطة شاملة للتطبيق:

        1. **الرئيسية (Dashboard):** تعرض إحصائيات عامة، أعداد التلاميذ، الحضور في المطعم، وقائمة الأقسام المسندة للأستاذ.
        2. **تسيير التلاميذ:**
           - **البحث:** يوجد شريط بحث في الأعلى للبحث بالاسم أو رقم التعريف.
           - **إضافة تلميذ:** زر "جديد" (أخضر) أسفل نموذج الإدخال.
           - **حذف تلميذ:** حدد المربع بجانب التلميذ في الجدول، ثم اضغط زر "حذف" (أحمر) في شريط الإجراءات.
           - **تعديل تلميذ:** اضغط على صف التلميذ في الجدول، سيظهر زر "تعديل" (برتقالي)، اضغط عليه لتفعيل الحقول، ثم "حفظ" (أزرق).
           - **الصورة:** يمكن تحميل صورة من المعرض أو التقاطها بالكاميرا عبر الأزرار الموجودة تحت إطار الصورة في الجهة اليمنى.
           - **طباعة البطاقات:** حدد التلاميذ من الجدول ثم اضغط زر "طباعة البطاقات" (بنفسجي).
        3. **الموارد البشرية (HR):**
           - **استيراد القوائم / الإسناد:** أزرار في الأعلى لرفع ملفات Excel.
           - **إضافة موظف:** زر "إضافة موظف" لفتح نافذة الإدخال اليدوي.
           - **زر الإسناد (لأساتذة فقط):** أيقونة "سبورة" (برتقالية) في جدول الموظفين لربط الأستاذ بالأقسام.
        4. **المطعم المدرسي:** لتسجيل حضور التلاميذ (يتطلب أن يكون التلميذ 'نصف داخلي').
        5. **المكتبة:** لإعارة وإرجاع الكتب باستخدام رقم التعريف.
        6. **تحديثات (Pending Updates):** (للمدير فقط) تظهر في القائمة الجانبية للموافقة على التعديلات التي أجراها الأساتذة/الموظفون (مثل إضافة/حذف تلميذ).
        7. **المهام والملاحظات:** للتواصل وإسناد المهام بين الطاقم.

        **قواعد الإجابة:**
        - أجب باختصار ومباشرة.
        - إذا سأل المستخدم "كيف أحذف موظف؟" قل له: "اذهب إلى قسم 'الموارد البشرية' من القائمة الجانبية، ابحث عن الموظف في الجدول، واضغط على أيقونة سلة المهملات الحمراء بجانبه".
        - لا تقم بتنفيذ الإجراءات بنفسك (أنت لا تملك الصلاحية)، بل أرشد المستخدم لمكان الزر في الشاشة.
        """

        if mode == 'bot_helper':
            directives = "- Role: Application UI Guide Bot. Concise, helpful navigation answers only."
            system_instruction = ui_knowledge_map # Override generic instruction with app map

        prompt = f"""
        Role: School Director Consultant.
        Context: {system_instruction}
        Data: {context}
        Query: {user_query}
        Directives: {directives}
        """

        # 1. Google Gemini (v1 SDK)
        if self.gemini_keys and HAS_GEMINI:
            resp = self._try_gemini_v1(prompt)
            if resp: return resp

        # 2. Groq
        if self.groq_keys and HAS_GROQ:
            resp = self._try_groq(prompt)
            if resp: return resp

        # 3. Claude
        if self.claude_keys and HAS_CLAUDE:
            resp = self._try_claude(prompt)
            if resp: return resp

        # Detailed Failure Message
        return "⚠️ عذراً، لم أتمكن من الاتصال بأي خادم (Google, Groq, Claude). يرجى التأكد من صحة المفاتيح في ملف .env ومن اتصال الإنترنت."

    def _try_gemini_v1(self, prompt):
        """Uses new google-genai SDK"""
        if not self.gemini_keys:
            logger.warning("No Google Keys Found")
            return None

        keys = list(self.gemini_keys)
        random.shuffle(keys)

        for key in keys:
            try:
                # Initialize Client per key
                client = genai.Client(api_key=key)

                for model in self.models_config['gemini']:
                    try:
                        # New SDK Call
                        response = client.models.generate_content(
                            model=model,
                            contents=prompt
                        )
                        if response and response.text:
                            return response.text
                    except Exception as e:
                        error_msg = f"Gemini V1 Fail ({model}) key=...{key[-4:]}: {e}"
                        print(error_msg) # Force Print
                        logger.warning(error_msg)
                        continue
            except Exception as e:
                error_msg = f"Gemini Client Init Error for key=...{key[-4:]}: {e}"
                print(error_msg)
                logger.error(error_msg)
        return None

    def _try_groq(self, prompt):
        keys = list(self.groq_keys)
        random.shuffle(keys)
        for key in keys:
            try:
                client = Groq(api_key=key)
                for model in self.models_config['groq']:
                    try:
                        chat_completion = client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model=model,
                        )
                        return chat_completion.choices[0].message.content
                    except Exception as e:
                        logger.warning(f"Groq Fail ({model}): {e}")
                        continue
            except Exception as e:
                logger.error(f"Groq Client Error: {e}")
                continue
        return None

    def _try_claude(self, prompt):
        keys = list(self.claude_keys)
        random.shuffle(keys)
        for key in keys:
            try:
                client = anthropic.Anthropic(api_key=key)
                for model in self.models_config['claude']:
                    try:
                        msg = client.messages.create(
                            model=model, max_tokens=1024,
                            messages=[{"role": "user", "content": prompt}]
                        )
                        return msg.content[0].text
                    except Exception as e:
                        logger.warning(f"Claude Fail ({model}): {e}")
                        continue
            except Exception as e:
                logger.error(f"Claude Client Error: {e}")
                continue
        return None

# Stub
def analyze_assignment_document(a): pass
def analyze_global_assignment(f): pass
def analyze_global_assignment_content(f):
    from students.utils_tools.smart_assignment_analyzer import extract_from_excel, extract_from_word
    ext = os.path.splitext(f)[1].lower()
    if ext in ['.xlsx', '.xls']: return extract_from_excel(f)
    if ext == '.docx': return extract_from_word(f)
    return []
