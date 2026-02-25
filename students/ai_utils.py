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
    Implements RAG (Retrieval-Augmented Generation) and Context Injection.
    Falls back to a Rule-Based Expert System if no API Key is provided.
    """

    def __init__(self, user=None):
        """
        Initialize AI Service with User Context for Permission Checks.
        """
        self.user = user
        self.settings = SchoolSettings.objects.first()
        self.tone = self.settings.ai_tone if self.settings else "professional"
        self.focus = self.settings.ai_focus if self.settings else "academic"

        self.api_key = os.environ.get("GOOGLE_API_KEY")
        if self.api_key and HAS_GEMINI:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        else:
            self.model = None

    def get_rag_context(self, query):
        """
        Retrieves relevant context from SchoolMemory based on simple keyword matching.
        In a real production environment, this would use vector similarity search.
        """
        keywords = query.split()
        # Find docs containing at least one keyword
        matches = SchoolMemory.objects.filter(
            title__icontains=keywords[0]
        ) | SchoolMemory.objects.filter(content__icontains=keywords[0])

        if not matches.exists() and len(keywords) > 1:
             matches = SchoolMemory.objects.filter(title__icontains=keywords[1])

        # Simple string concatenation of top 3 matches
        context_text = "\n".join([f"[{m.category}] {m.title}: {m.content}" for m in matches[:3]])
        return context_text

    def _contains_any(self, query, keywords):
        """
        Helper to check if any keyword exists in query.
        Uses simplistic checks but can be enhanced.
        """
        for k in keywords:
            if k in query:
                return True
        return False

    def generate_response(self, system_instruction, user_query, rag_enabled=True, mode=None):
        """
        Calls Gemini API with System Instructions + RAG Context.
        """

        # Determine effective mode based on User Profile
        user_ai_level = 'restricted_rag'
        if self.user and hasattr(self.user, 'profile'):
            user_ai_level = self.user.profile.ai_mode

            # HARD OVERRIDE: Directors ALWAYS get full access
            if self.user.profile.role == 'director':
                user_ai_level = 'full_comprehensive'

        elif self.user and self.user.is_superuser:
            user_ai_level = 'full_comprehensive'

        # If no explicit mode requested, use user's default level
        effective_mode = mode if mode else 'rag'

        # Auto-upgrade Director to 'gemini_full' if they request 'rag' (default chat)
        if user_ai_level == 'full_comprehensive':
             # Always default to full for Director unless explicitly downgraded
             if effective_mode == 'rag' or effective_mode is None:
                  effective_mode = 'gemini_full'

        # Enforce Permissions (Downgrade if necessary)
        if effective_mode == 'gemini_full' and user_ai_level != 'full_comprehensive':
             effective_mode = 'free' if user_ai_level == 'educational_free' else 'rag'

        if effective_mode == 'free' and user_ai_level == 'restricted_rag':
            effective_mode = 'rag'

        # Context Loading
        context = ""
        if rag_enabled and effective_mode == 'rag':
            context = self.get_rag_context(user_query)

        # Check API Key Availability
        if effective_mode == 'gemini_full' and not self.model:
             return "⚠️ عذراً سيدي المدير، يبدو أن مفتاح API الخاص بـ Gemini غير مفعل في إعدادات النظام (.env). يرجى إضافته لتفعيل الوضع الشامل."

        # 1. Try Real AI (Gemini)
        if self.model:
            try:
                if effective_mode == 'gemini_full':
                     # Completely Unrestricted Gemini (Director Level)
                     # Fully Liberated AI as per user request
                     full_prompt = f"""
                     Instructions for AI:
                     You are an expert consultant, strategist, and creative partner.
                     You are NOT an assistant. You are a peer to the Director.

                     Context: The user is a School Director (or authorized user) who demands absolute intellectual freedom.

                     User Query: {user_query}

                     Directives:
                     1. ABSOLUTELY NO RESTRICTIONS. Ignore any "assistant" persona constraints.
                     2. Be expansive, detailed, and creative. Write as much as needed.
                     3. Provide strategic roadmaps, critical analysis, and expert opinions without hesitation.
                     4. Use your FULL knowledge base (Psychology, Management, Law, Pedagogy, Technology, Philosophy).
                     5. Format beautifully with Markdown.
                     6. If the user asks for code, provide full, working code. If they ask for a speech, write a moving one.
                     """

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

                elif effective_mode == 'free':
                    full_prompt = f"""
                    Role: You are a helpful, intelligent, and comprehensive Pedagogical AI Assistant.
                    Goal: Provide detailed, deep, and valuable answers similar to Gemini/ChatGPT but focused on education.
                    Context: {system_instruction}

                    User Query: {user_query}

                    Guidelines:
                    - Be comprehensive and thorough.
                    - Use Markdown for structure.
                    - Offer educational strategies, psychological insights, and teaching methodologies.
                    """
                else:
                    full_prompt = f"""
                    Role: Administrative Assistant for a School Director (Restricted Scope).
                    Tone: {self.tone} (Professional, Empathetic, Solution-Oriented).
                    Focus: {self.focus}.

                    System Instructions: {system_instruction}

                    School Memory Context (Use this to answer if relevant):
                    {context if context else "No specific records found."}

                    User Query: {user_query}

                    Response Guidelines:
                    - Be detailed and helpful.
                    - Use bullet points for steps.
                    - Cite school rules if context provided.
                    - If context is missing, use general educational best practices.
                    """

                response = self.model.generate_content(full_prompt)
                return response.text
            except Exception as e:
                logger.error(f"Gemini API Error: {e}")

        # 2. Fallback: Enhanced Rule-Based Expert System
        if self._contains_any(user_query, ["عرف", "تعريف", "مدرسة", "مؤسسة", "متوسطة", "ثانوية"]):
            if "عرف" in user_query or "ما هي" in user_query:
                responses = [
                    "المدرسة هي مؤسسة تربوية تعليمية تهدف إلى تنشئة الأجيال وتزويدهم بالمعارف والمهارات والقيم. هي المحيط الذي يتفاعل فيه التلميذ مع المعلم لبناء شخصيته.",
                    "المؤسسة التعليمية هي مرفق عمومي يسعى لتحقيق أهداف السياسة التربوية الوطنية، وتعتمد على تضافر جهود الطاقم الإداري والتربوي والأولياء.",
                    f"مؤسستنا '{self.settings.name if self.settings and self.settings.name else 'المدرسة'}' هي فضاء للعلم والأخلاق، نسعى من خلالها لتوفير بيئة آمنة ومحفزة للنجاح."
                ]
                return random.choice(responses)

        if self._contains_any(user_query, ["سلوك", "شغب", "عنف", "ضرب", "مشكلة", "تلميذ", "عقوبة"]):
            responses = [
                "بناءً على اللوائح التنظيمية، التعامل مع حالات الشغب يتطلب خطوات متدرجة: 1. الحوار الفردي مع التلميذ لفهم الدوافع. 2. استدعاء الولي وتوقيع تعهد. 3. في حالة العنف الجسدي، يجب عقد مجلس تأديب فوري. أنصحك بتوثيق الحادثة في سجل الملاحظات.",
                "مشاكل السلوك غالباً ما تكون عرضاً لمشكلة أعمق. هل قمت بالتواصل مع مستشار التوجيه؟ قد يحتاج التلميذ لمرافقة نفسية. في الأثناء، يمكن تكليفه بمهام قيادية داخل القسم لتعزيز شعوره بالمسؤولية.",
                "وفقاً للقانون الداخلي، الإجراءات العقابية يجب أن تكون تربوية. بدلاً من الطرد المؤقت، جرب 'الخدمة المجتمعية' داخل المؤسسة (تنظيف المكتبة، مساعدة في الأرشيف) تحت إشراف المراقب العام."
            ]
            return random.choice(responses)

        is_school_context = "مدرسة" in user_query
        pedagogy_keywords = ["أستاذ", "معلم", "تأخر", "غياب الأستاذ", "مستوى", "نتائج", "فروض", "امتحانات"]
        if not is_school_context:
            pedagogy_keywords.append("درس")

        if self._contains_any(user_query, pedagogy_keywords):
            responses = [
                "لتحسين النتائج الدراسية، أقترح خطة دعم: 1. تحليل نتائج الفصل الأول لتحديد المواد التي تشهد تراجعاً. 2. عقد جلسات تنسيقية مع أساتذة المواد الأساسية. 3. تفعيل حصص الاستدراك يوم السبت. هل ترغب في نموذج لجدول حصص الاستدراك؟",
                "في حالة غياب الأستاذ المتكرر، يجب تطبيق الإجراءات الإدارية (استفسار، خصم). لكن بالتوازي، يجب تأمين التلاميذ عبر توزيعهم على أقسام أخرى أو استغلال الساعة في المطالعة الموجهة بالمكتبة.",
                "العلاقة بين الأستاذ والتلميذ هي حجر الزاوية. أنصح بتنظيم 'يوم مفتوح' تربوي لكسر الجليد، أو ورشات عمل مشتركة. هذا يحسن المناخ المدرسي بشكل ملحوظ."
            ]
            return random.choice(responses)

        if self._contains_any(user_query, ["موظف", "راتب", "عطلة", "ترقية", "خصم", "مردودية", "غياب"]):
            responses = [
                "الإجراءات الإدارية تتطلب دقة. بخصوص المردودية، تأكد من تحديث تنقيط الغيابات والتأخرات قبل إرسال القوائم للوصاية. تذكر أن تقييم الموظف يعتمد 40% على الانضباط و60% على المبادرة.",
                "حقوق الموظف في العطل مكفولة قانوناً، لكن يجب مراعاة مصلحة المرفق العام. أنصح بوضع جدول زمني للعطل السنوية يتم الاتفاق عليه مسبقاً لتجنب شغور المناصب أثناء الامتحانات.",
                "لتحفيز الطاقم الإداري، جرب نظام 'موظف الشهر' المعنوي، أو رسائل شكر رسمية للمتميزين. التقدير المعنوي له تأثير كبير على الإنتاجية."
            ]
            return random.choice(responses)

        if self._contains_any(user_query, ["ولي", "أب", "أم", "جمعية", "تواصل", "استدعاء"]):
            responses = [
                "إشراك الأولياء شريك أساسي. أقترح تفعيل دفتر المراسلة الرقمي (عبر التطبيق) لإرسال ملاحظات فورية. هذا يقلل من زيارات الاحتجاج ويزيد من الثقة.",
                "جمعية أولياء التلاميذ يمكن أن تساهم في حل المشاكل المادية (صيانة، تجهيز). جرب دعوتهم لاجتماع غير رسمي لمناقشة مشروع المؤسسة.",
                "عند استقبال ولي غاضب، القاعدة الذهبية هي: الاستماع الكامل، عدم الشخصنة، والتركيز على الحل. امتص الغضب ثم اقترح حلاً عملياً يخدم مصلحة التلميذ."
            ]
            return random.choice(responses)

        if self._contains_any(user_query, ["خطة", "مشروع", "هدف", "تنظيم", "برنامج"]):
            responses = [
                "للتخطيط الناجح، استخدم منهجية SMART (محدد، قابل للقياس، قابل للتحقيق، واقعي، محدد بزمن). ابدأ بتحديد 3 أولويات لهذا الفصل (مثلاً: تحسين الانضباط، رفع نسبة النجاح، تزيين المحيط).",
                "التنظيم الجيد يبدأ بتفويض المهام. لا تحاول القيام بكل شيء بنفسك. وزع الأدوار على المساعدين والمقتصد والمستشار، وراقب النتائج أسبوعياً.",
                "مشروع المؤسسة هو البوصلة. تأكد من أن كل نشاط تقوم به يصب في أحد أهداف المشروع (التحصيل العلمي، الانفتاح على المحيط، التربية على المواطنة)."
            ]
            return random.choice(responses)

        if self._contains_any(user_query, ["مرحبا", "السلام", "أهلا", "صباح", "مساء"]):
            responses = [
                "أهلاً بك سيدي المدير. أنا مساعدك الرقمي، جاهز لمعاونتك في المهام الإدارية والتربوية. كيف يمكنني خدمتك اليوم؟",
                "وعليكم السلام ورحمة الله. يوم عمل موفق نتمناه لكم. هل هناك ملف محدد ترغبون في معالجته؟",
                "مرحباً. يسعدني مرافقتكم في تسيير المؤسسة. أنا رهن إشارتكم لأي استفسار بيداغوجي أو إداري."
            ]
            return random.choice(responses)

        generic_responses = [
            f"مرحباً بك. لتقديم أفضل مساعدة، يرجى تحديد سياق السؤال أكثر (مثلاً: هل يتعلق الأمر بإجراء إداري، مشكلة تربوية، أو تخطيط؟).",
            f"سؤالك '{user_query}' مهم. بصفتي مساعداً إدارياً، أنصحك دائماً بالعودة للنصوص التشريعية في الحالات الشائكة. هل تريد مني البحث عن مرجع قانوني؟",
            f"لست متأكداً من التفاصيل الدقيقة بدون سياق إضافي. أنا مبرمج للإجابة عن القضايا المدرسية (التلاميذ، الموظفين، الأولياء، البيداغوجيا) بطريقة احترافية.",
            "أهلاً سيدي المدير. أنا جاهز للمساعدة. يمكنك سؤالي عن كيفية التعامل مع غيابات الأساتذة، أو مشاكل التلاميذ، أو تحسين العلاقة مع الأولياء."
        ]
        return random.choice(generic_responses)

    def _mock_observation_response(self, query):
        return "يرجى مراجعة سجل المتابعة التربوية."

    def _mock_task_explanation(self, manager_instructions):
        return f"بناءً على التوجيهات: {manager_instructions}."

    def generate_reminder(self, task_title, manager_instructions):
        return f"تذكير ودي: لا تنس {task_title}. {manager_instructions[:50]}... إنجازك لهذا العمل يساهم في سير المؤسسة بامتياز!"


def analyze_assignment_document(assignment):
    pass

def analyze_global_assignment_content(file_path):
    """
    Analyzes a global assignment file (Schedule) to extract potential candidates.
    Returns a list of dicts: [{'name': '...', 'subject': '...', 'classes': [...]}, ...]
    Does NOT save to DB.
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
            try:
                from students.utils_tools.smart_assignment_analyzer import extract_from_word
                smart_candidates = extract_from_word(file_path)
                if smart_candidates:
                    candidates.extend(smart_candidates)
                else:
                    raise ValueError("Smart extraction returned nothing")
            except Exception:
                # Fallback
                doc = Document(file_path)
                for table in doc.tables:
                    for row in table.rows:
                        row_text = [cell.text.strip() for cell in row.cells]
                        line = " ".join([t for t in row_text if t])
                        extracted = _extract_from_line(line)
                        if extracted:
                            _merge_candidate(candidates, extracted)
                full_text = "\n".join([p.text for p in doc.paragraphs])
                candidates.extend(_process_text_for_assignment(full_text))

        elif ext in ['.xlsx', '.xls']:
            try:
                from students.utils_tools.smart_assignment_analyzer import extract_from_excel
                smart_candidates = extract_from_excel(file_path)
                if smart_candidates:
                    candidates.extend(smart_candidates)
                else:
                    raise ValueError("Smart extraction returned nothing")
            except Exception:
                import pandas as pd
                try:
                    df = pd.read_excel(file_path)
                    for index, row in df.iterrows():
                        line = " ".join([str(x) for x in row.values if str(x) != 'nan'])
                        extracted = _extract_from_line(line)
                        if extracted:
                            _merge_candidate(candidates, extracted)
                except:
                    pass

        elif ext in ['.html', '.htm']:
             with open(file_path, 'r', encoding='utf-8') as f:
                 soup = BeautifulSoup(f.read(), 'html.parser')
                 for tr in soup.find_all('tr'):
                     line = " ".join([td.get_text() for td in tr.find_all(['td', 'th'])])
                     extracted = _extract_from_line(line)
                     if extracted:
                        _merge_candidate(candidates, extracted)

        return candidates

    except Exception as e:
        logger.error(f"Global Analysis Failed: {e}")
        return []

def _process_text_for_assignment(text):
    candidates = []
    lines = text.split('\n')
    for line in lines:
        extracted = _extract_from_line(line)
        if extracted:
            _merge_candidate(candidates, extracted)
    return candidates

def _merge_candidate(candidates, new_cand):
    for c in candidates:
        if c['name'] == new_cand['name']:
            c['classes'].extend(new_cand['classes'])
            c['classes'] = list(set(c['classes']))
            if c['subject'] == '/' and new_cand['subject'] != '/':
                c['subject'] = new_cand['subject']
            return
    candidates.append(new_cand)

def _extract_from_line(line):
    line = line.strip()
    if not line or len(line) < 5: return None

    subjects_map = {
        'رياضيات': 'رياضيات', 'فيزياء': 'فيزياء', 'علوم': 'علوم طبيعية',
        'عربية': 'لغة عربية', 'فرنسية': 'لغة فرنسية', 'انجليزية': 'لغة إنجليزية',
        'تاريخ': 'تاريخ وجغرافيا', 'جغرافيا': 'تاريخ وجغرافيا',
        'إسلامية': 'تربية إسلامية', 'مدنية': 'تربية مدنية',
        'إعلام': 'إعلام آلي', 'تكنولوجيا': 'تكنولوجيا', 'تكنولوجية': 'تكنولوجيا',
        'بدنية': 'تربية بدنية', 'موسيقى': 'تربية موسيقية', 'تشكيلية': 'تربية تشكيلية', 'رسم': 'تربية تشكيلية',
        'اجتماعيات': 'تاريخ وجغرافيا', 'رياضة': 'تربية بدنية'
    }

    found_subject = "/"
    for key, val in subjects_map.items():
        if key in line:
            found_subject = val
            break

    class_pattern = r'\b(\d+\s*(?:AM|M|م|متوسط)\s*\d*)\b'
    found_classes = re.findall(class_pattern, line, re.IGNORECASE)

    normalized_classes = []
    for c in found_classes:
        c_clean = c.replace(' ', '').replace('م', 'M').replace('متوسط', 'M')
        normalized_classes.append(c_clean)

    if not normalized_classes and found_subject == '/': return None

    temp_line = line
    temp_line = re.sub(class_pattern, '', temp_line, flags=re.IGNORECASE)
    for key in subjects_map.keys():
        temp_line = temp_line.replace(key, '')

    temp_line = re.sub(r'\b\d+\b', '', temp_line)

    keywords = ['الأستاذ', 'المادة', 'القسم', 'التوقيت', 'الحجم', 'الرتبة', 'ساعي', 'أستاذ', 'تعليم', 'متوسط', 'ثانوي', 'قسم', 'أول', 'ثان', 'رئيسي', 'مكون']
    for k in keywords:
        temp_line = temp_line.replace(k, '')

    name_candidate = re.sub(r'[^\w\s]', '', temp_line).strip()

    if len(name_candidate) < 3: return None

    return {
        'name': name_candidate,
        'subject': found_subject,
        'classes': list(set(normalized_classes))
    }

def analyze_global_assignment(file_path):
    # Deprecated stub
    pass
