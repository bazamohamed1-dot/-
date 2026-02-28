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

try:
    import requests # Required for OpenRouter fallback
    HAS_OPENROUTER = True
except ImportError:
    HAS_OPENROUTER = False

logger = logging.getLogger(__name__)

class AIService:
    """
    Advanced AI Service with Multi-Provider Fallback (OpenRouter -> Google -> Groq -> Claude).
    Updated to use `google-genai` (Official v1 SDK).
    """

    def __init__(self, user=None):
        self.user = user
        self.settings = SchoolSettings.objects.first()

        # Load API Keys
        self.openrouter_keys = self._load_keys("OPENROUTER_API_KEY")
        self.gemini_keys = self._load_keys("GOOGLE_API_KEY")
        self.groq_keys = self._load_keys("GROQ_API_KEY")
        self.claude_keys = self._load_keys("ANTHROPIC_API_KEY")

        # Models Config
        self.models_config = {
            'openrouter': ['google/gemini-2.0-flash-lite-preview-02-05:free', 'meta-llama/llama-3-8b-instruct:free', 'cognitivecomputations/dolphin3.0-r1-mistral-24b:free'], # Generous free tier models on OpenRouter
            # Try 2.0 first (Fastest), then 1.5-flash (Stable), then Pro
            'gemini': ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro'],
            # Updated to use currently active Groq models (removed decommissioned models)
            'groq': ['llama3-8b-8192', 'gemma2-9b-it'],
            'claude': ['claude-3-haiku-20240307']
        }

    def _load_keys(self, prefix):
        keys = []
        k1 = os.environ.get(prefix)
        if k1 and k1.strip(): keys.append(k1.strip().strip("'").strip('"'))
        i = 2
        while True:
            k = os.environ.get(f"{prefix}_{i}")
            if not k or not k.strip(): break
            keys.append(k.strip().strip("'").strip('"'))
            i += 1
        return keys

    def get_rag_context(self, query):
        keywords = query.split()
        matches = SchoolMemory.objects.filter(title__icontains=keywords[0])
        context_text = "\n".join([f"[{m.category}] {m.title}: {m.content}" for m in matches[:3]])
        return context_text

    def generate_response(self, system_instruction, user_query, rag_enabled=True, mode=None):
        if mode == 'bot_helper':
            return self._handle_bot_helper_local(user_query)

        context = ""
        if rag_enabled:
            context = self.get_rag_context(user_query)

        # Mode-specific directives
        directives = "- Concise for greetings. Detailed for plans."

        prompt = f"""
        Role: School Director Consultant.
        Context: {system_instruction}
        Data: {context}
        Query: {user_query}
        Directives: {directives}
        """

        # 1. OpenRouter (High Free Tier)
        if self.openrouter_keys and HAS_OPENROUTER:
            resp = self._try_openrouter(prompt)
            if resp: return resp

        # 2. Google Gemini (v1 SDK)
        if self.gemini_keys and HAS_GEMINI:
            resp = self._try_gemini_v1(prompt)
            if resp: return resp

        # 3. Groq
        if self.groq_keys and HAS_GROQ:
            resp = self._try_groq(prompt)
            if resp: return resp

        # 4. Claude
        if self.claude_keys and HAS_CLAUDE:
            resp = self._try_claude(prompt)
            if resp: return resp

        # If we got here, all providers failed. Let's try to get the last error from OpenRouter for debugging
        last_or_error = getattr(self, '_last_openrouter_error', None)
        if last_or_error:
            return f"⚠️ عذراً، فشل الاتصال بالذكاء الاصطناعي.\nالسبب من خادم OpenRouter:\n{last_or_error}"

        # Detailed Failure Message
        return "⚠️ عذراً، لم أتمكن من الاتصال بأي خادم (OpenRouter, Google, Groq, Claude). يرجى التأكد من صحة المفاتيح في ملف .env ومن اتصال الإنترنت."

    def _handle_bot_helper_local(self, query):
        """
        Local, purely offline helper without using AI APIs.
        Provides detailed mapping and answers based on simple keyword matching.
        """
        import re
        q = query.lower()

        # Responses logic
        if re.search(r'(إضافة|جديد|تسجيل)\s*(تلميذ|طالب|متعلم)', q):
            return "لإضافة تلميذ جديد: اذهب إلى 'تسيير التلاميذ' من القائمة الجانبية، انزل إلى أسفل نموذج الإدخال واضغط على زر 'جديد' (الأخضر)، ثم املأ البيانات واضغط 'حفظ'."

        if re.search(r'(حذف|ازالة|مسح)\s*(تلميذ|طالب|متعلم)', q):
            return "لحذف تلميذ: في واجهة 'تسيير التلاميذ'، حدد المربع بجانب اسم التلميذ في الجدول، ثم اضغط على زر 'حذف' (الأحمر) في شريط الإجراءات بالأعلى."

        if re.search(r'(تعديل|تغيير)\s*(تلميذ|طالب|متعلم)', q):
            return "لتعديل بيانات تلميذ: في 'تسيير التلاميذ'، اضغط على صف التلميذ في الجدول، سيظهر لك زر 'تعديل' (برتقالي)، اضغط عليه، عدّل البيانات، ثم اضغط 'حفظ'."

        if re.search(r'(صورة|صور)\s*(تلميذ|طالب|متعلم)', q):
            return "لإضافة صورة لتلميذ: أثناء إضافته أو تعديله، ستجد أزراراً تحت إطار الصورة في الجهة اليسرى (أو اليمنى حسب الاتجاه)، يمكنك تحميل صورة من جهازك أو التقاطها عبر الكاميرا."

        if re.search(r'(طباعة|بطاقة|بطاقات)', q):
            return "لطباعة بطاقات التلاميذ: من واجهة 'تسيير التلاميذ'، حدد التلاميذ المعنيين من الجدول، ثم اضغط على زر 'طباعة البطاقات' (البنفسجي) في الأعلى."

        if re.search(r'(اضافة|تسجيل|جديد)\s*(موظف|استاذ|أستاذ|عامل|اداري)', q):
            return "لإضافة موظف: اذهب إلى 'الموارد البشرية' من القائمة الجانبية، ثم اضغط على زر 'إضافة موظف' واكتب بياناته يدوياً."

        if re.search(r'(اسناد|أقسام|تدريس)\s*(موظف|استاذ|أستاذ)', q):
            return "لإسناد أقسام لأستاذ: في واجهة 'الموارد البشرية'، ستجد زر 'تعديل الإسناد' الذي يظهر لك جدولاً بكل الأساتذة مع مربعات نصية، أو يمكنك النقر على أيقونة السبورة بجانب اسم الأستاذ."

        if re.search(r'(استيراد|اكسل|excel|قوائم)', q):
            return "لاستيراد قوائم (تلاميذ أو أساتذة أو إسناد): يوجد أزرار استيراد خاصة في أعلى صفحة 'تسيير التلاميذ' أو 'الموارد البشرية'. تأكد من أن ملفك بصيغة Excel (أو PDF/Word للإسناد الشامل)."

        if re.search(r'(مطعم|كانتين|نصف داخلي)', q):
            return "لتسجيل حضور التلاميذ في المطعم: توجه إلى واجهة 'المطعم المدرسي'. تذكر أن التلميذ يجب أن تكون صفته 'نصف داخلي' ليظهر هناك."

        if re.search(r'(مكتبة|اعارة|إعارة|كتاب)', q):
            return "لإعارة الكتب: اذهب إلى واجهة 'المكتبة'. ستحتاج لإدخال رقم تعريف التلميذ لتسجيل الإعارة أو الإرجاع."

        if re.search(r'(تحديث|تحديثات|موافقة)', q):
            return "صفحة 'التحديثات المعلقة' (Pending Updates): تظهر للمدير فقط في القائمة الجانبية، وهي للموافقة على التعديلات (مثل إضافة/حذف تلميذ) التي قام بها المستخدمون الآخرون."

        if re.search(r'(مهام|مهمة)', q):
            return "لإسناد المهام: استخدم واجهة 'المهام' من القائمة الجانبية لإرسال مهام للطاقم ومتابعة تنفيذها."

        if re.search(r'(سلام|مرحبا|أهلا|مساعدة)', q):
            return "أهلاً بك! أنا المساعد التقني المحلي (بدون إنترنت) لتطبيق 'تسيير متوسطة بوشنافة عمر'. يمكنني إرشادك لأماكن الأزرار وكيفية عمل الواجهات. اسألني مثلاً: 'كيف أحذف تلميذ؟' أو 'أين أجد الإسناد؟'."

        return "عذراً، لم أفهم سؤالك. يرجى سؤالي عن وظيفة محددة في التطبيق مثل: 'كيف أضيف تلميذ؟'، 'كيف أعدل الإسناد؟'، أو 'كيف أطبع البطاقات؟'."

    def _try_openrouter(self, prompt):
        keys = list(self.openrouter_keys)
        random.shuffle(keys)
        last_error = None
        for key in keys:
            for model in self.models_config['openrouter']:
                try:
                    response = requests.post(
                        url="https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {key}",
                            "HTTP-Referer": "http://localhost", # Required by OpenRouter, can be any valid URL format
                            "X-Title": "School Management Agent", # Required by OpenRouter
                        },
                        json={
                            "model": model,
                            "messages": [
                                {"role": "user", "content": prompt}
                            ]
                        },
                        timeout=15 # Avoid hanging forever
                    )

                    if response.status_code == 200:
                        data = response.json()
                        if "choices" in data and len(data["choices"]) > 0:
                            return data["choices"][0]["message"]["content"]
                    else:
                        last_error = f"HTTP {response.status_code}: {response.text}"
                        print(f"OpenRouter Error ({model}): {last_error}")
                        logger.warning(f"OpenRouter Error ({model}): {last_error}")
                except Exception as e:
                    last_error = str(e)
                    print(f"OpenRouter Request Exception ({model}): {e}")
                    logger.warning(f"OpenRouter Request Exception ({model}): {e}")
                    continue

        # If we exhausted all keys and models, return detailed error for debugging
        if last_error:
            logger.error(f"All OpenRouter attempts failed. Last error: {last_error}")
            self._last_openrouter_error = last_error

        return None

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
