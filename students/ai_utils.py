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

    def __init__(self):
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

    def generate_response(self, system_instruction, user_query, rag_enabled=True, free_mode=False):
        """
        Calls Gemini API with System Instructions + RAG Context.
        If API Key is missing, uses a sophisticated Rule-Based System.
        """
        context = ""
        if rag_enabled:
            context = self.get_rag_context(user_query)

        # 1. Try Real AI (Gemini)
        if self.model:
            try:
                full_prompt = f"""
                Role: Educational Assistant for a School Director.
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
                # Fallback to Mock if API fails

        # 2. Fallback: Enhanced Rule-Based Expert System
        # Categories: Discipline, Pedagogy, Admin, Parents, General

        # --- Definition / School Info ---
        if self._contains_any(user_query, ["عرف", "تعريف", "مدرسة", "مؤسسة", "متوسطة", "ثانوية"]):
            # Avoid triggering if it's just a casual mention, but "Define the school" is specific.
            if "عرف" in user_query or "ما هي" in user_query:
                responses = [
                    "المدرسة هي مؤسسة تربوية تعليمية تهدف إلى تنشئة الأجيال وتزويدهم بالمعارف والمهارات والقيم. هي المحيط الذي يتفاعل فيه التلميذ مع المعلم لبناء شخصيته.",
                    "المؤسسة التعليمية هي مرفق عمومي يسعى لتحقيق أهداف السياسة التربوية الوطنية، وتعتمد على تضافر جهود الطاقم الإداري والتربوي والأولياء.",
                    f"مؤسستنا '{self.settings.name if self.settings and self.settings.name else 'المدرسة'}' هي فضاء للعلم والأخلاق، نسعى من خلالها لتوفير بيئة آمنة ومحفزة للنجاح."
                ]
                return random.choice(responses)

        # --- Discipline / Behavior ---
        if self._contains_any(user_query, ["سلوك", "شغب", "عنف", "ضرب", "مشكلة", "تلميذ", "عقوبة"]):
            responses = [
                "بناءً على اللوائح التنظيمية، التعامل مع حالات الشغب يتطلب خطوات متدرجة: 1. الحوار الفردي مع التلميذ لفهم الدوافع. 2. استدعاء الولي وتوقيع تعهد. 3. في حالة العنف الجسدي، يجب عقد مجلس تأديب فوري. أنصحك بتوثيق الحادثة في سجل الملاحظات.",
                "مشاكل السلوك غالباً ما تكون عرضاً لمشكلة أعمق. هل قمت بالتواصل مع مستشار التوجيه؟ قد يحتاج التلميذ لمرافقة نفسية. في الأثناء، يمكن تكليفه بمهام قيادية داخل القسم لتعزيز شعوره بالمسؤولية.",
                "وفقاً للقانون الداخلي، الإجراءات العقابية يجب أن تكون تربوية. بدلاً من الطرد المؤقت، جرب 'الخدمة المجتمعية' داخل المؤسسة (تنظيف المكتبة، مساعدة في الأرشيف) تحت إشراف المراقب العام."
            ]
            return random.choice(responses)

        # --- Pedagogy / Teachers ---
        # Note: Exclude 'درس' if 'مدرسة' is present to avoid confusion
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

        # --- Administration / HR ---
        if self._contains_any(user_query, ["موظف", "راتب", "عطلة", "ترقية", "خصم", "مردودية", "غياب"]):
            responses = [
                "الإجراءات الإدارية تتطلب دقة. بخصوص المردودية، تأكد من تحديث تنقيط الغيابات والتأخرات قبل إرسال القوائم للوصاية. تذكر أن تقييم الموظف يعتمد 40% على الانضباط و60% على المبادرة.",
                "حقوق الموظف في العطل مكفولة قانوناً، لكن يجب مراعاة مصلحة المرفق العام. أنصح بوضع جدول زمني للعطل السنوية يتم الاتفاق عليه مسبقاً لتجنب شغور المناصب أثناء الامتحانات.",
                "لتحفيز الطاقم الإداري، جرب نظام 'موظف الشهر' المعنوي، أو رسائل شكر رسمية للمتميزين. التقدير المعنوي له تأثير كبير على الإنتاجية."
            ]
            return random.choice(responses)

        # --- Parents ---
        if self._contains_any(user_query, ["ولي", "أب", "أم", "جمعية", "تواصل", "استدعاء"]):
            responses = [
                "إشراك الأولياء شريك أساسي. أقترح تفعيل دفتر المراسلة الرقمي (عبر التطبيق) لإرسال ملاحظات فورية. هذا يقلل من زيارات الاحتجاج ويزيد من الثقة.",
                "جمعية أولياء التلاميذ يمكن أن تساهم في حل المشاكل المادية (صيانة، تجهيز). جرب دعوتهم لاجتماع غير رسمي لمناقشة مشروع المؤسسة.",
                "عند استقبال ولي غاضب، القاعدة الذهبية هي: الاستماع الكامل، عدم الشخصنة، والتركيز على الحل. امتص الغضب ثم اقترح حلاً عملياً يخدم مصلحة التلميذ."
            ]
            return random.choice(responses)

        # --- General / Planning ---
        if self._contains_any(user_query, ["خطة", "مشروع", "هدف", "تنظيم", "برنامج"]):
            responses = [
                "للتخطيط الناجح، استخدم منهجية SMART (محدد، قابل للقياس، قابل للتحقيق، واقعي، محدد بزمن). ابدأ بتحديد 3 أولويات لهذا الفصل (مثلاً: تحسين الانضباط، رفع نسبة النجاح، تزيين المحيط).",
                "التنظيم الجيد يبدأ بتفويض المهام. لا تحاول القيام بكل شيء بنفسك. وزع الأدوار على المساعدين والمقتصد والمستشار، وراقب النتائج أسبوعياً.",
                "مشروع المؤسسة هو البوصلة. تأكد من أن كل نشاط تقوم به يصب في أحد أهداف المشروع (التحصيل العلمي، الانفتاح على المحيط، التربية على المواطنة)."
            ]
            return random.choice(responses)

        # --- Greeting / Small Talk (But Professional) ---
        if self._contains_any(user_query, ["مرحبا", "السلام", "أهلا", "صباح", "مساء"]):
            responses = [
                "أهلاً بك سيدي المدير. أنا مساعدك الرقمي، جاهز لمعاونتك في المهام الإدارية والتربوية. كيف يمكنني خدمتك اليوم؟",
                "وعليكم السلام ورحمة الله. يوم عمل موفق نتمناه لكم. هل هناك ملف محدد ترغبون في معالجته؟",
                "مرحباً. يسعدني مرافقتكم في تسيير المؤسسة. أنا رهن إشارتكم لأي استفسار بيداغوجي أو إداري."
            ]
            return random.choice(responses)

        # --- Fallback (Generic but varied) ---
        generic_responses = [
            f"مرحباً بك. لتقديم أفضل مساعدة، يرجى تحديد سياق السؤال أكثر (مثلاً: هل يتعلق الأمر بإجراء إداري، مشكلة تربوية، أو تخطيط؟).",
            f"سؤالك '{user_query}' مهم. بصفتي مساعداً إدارياً، أنصحك دائماً بالعودة للنصوص التشريعية في الحالات الشائكة. هل تريد مني البحث عن مرجع قانوني؟",
            f"لست متأكداً من التفاصيل الدقيقة بدون سياق إضافي. أنا مبرمج للإجابة عن القضايا المدرسية (التلاميذ، الموظفين، الأولياء، البيداغوجيا) بطريقة احترافية.",
            "أهلاً سيدي المدير. أنا جاهز للمساعدة. يمكنك سؤالي عن كيفية التعامل مع غيابات الأساتذة، أو مشاكل التلاميذ، أو تحسين العلاقة مع الأولياء."
        ]
        return random.choice(generic_responses)

    def _mock_observation_response(self, query):
        # Deprecated by new logic above, kept for safety
        return "يرجى مراجعة سجل المتابعة التربوية."

    def _mock_task_explanation(self, manager_instructions):
        return f"بناءً على التوجيهات: {manager_instructions}."

    def generate_reminder(self, task_title, manager_instructions):
        """
        Generates a creative reminder message.
        """
        return f"تذكير ودي: لا تنس {task_title}. {manager_instructions[:50]}... إنجازك لهذا العمل يساهم في سير المؤسسة بامتياز!"


def analyze_assignment_document(assignment):
    """
    Deprecated. Used for single teacher assignment.
    """
    pass

def analyze_global_assignment(file_path):
    """
    Analyzes a global assignment file (Schedule) to link Teachers to Subjects and Classes.
    Supports Excel, Word, PDF, HTML.
    Returns summary stats.
    """
    text = ""
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == '.pdf':
            reader = PdfReader(file_path)
            for page in reader.pages: text += page.extract_text() + "\n"
        elif ext == '.docx':
            doc = Document(file_path)
            for p in doc.paragraphs: text += p.text + "\n"
            for t in doc.tables:
                for r in t.rows:
                    text += " ".join([c.text for c in r.cells]) + "\n"
        elif ext in ['.xlsx', '.xls']:
            import pandas as pd
            try:
                df = pd.read_excel(file_path)
                text = df.to_string()
            except:
                pass

        if not text and ext in ['.html', '.htm']:
             with open(file_path, 'r', encoding='utf-8') as f:
                 soup = BeautifulSoup(f.read(), 'html.parser')
                 text = soup.get_text()

        if not text:
             try:
                 with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: text = f.read()
             except: pass

        # --- AI LOGIC (Regex/Heuristic) ---
        teachers = Employee.objects.filter(rank='teacher')
        stats = {'processed': 0, 'classes': 0}

        for teacher in teachers:
            if teacher.last_name in text or teacher.first_name in text:
                teacher_classes = []
                teacher_subject = teacher.subject

                class_pattern = r'\b(\d+[AM]+\d+|\d+M\d+)\b'

                lines = text.split('\n')
                for line in lines:
                    if teacher.last_name in line or teacher.first_name in line:
                        found_classes = re.findall(class_pattern, line)
                        teacher_classes.extend(found_classes)

                        subjects = ['رياضيات', 'فيزياء', 'علوم', 'عربية', 'فرنسية', 'انجليزية', 'تاريخ', 'جغرافيا', 'إسلامية', 'مدنية', 'إعلام آلي', 'تكنولوجية', 'بدنية', 'تشكيلية', 'موسيقى']
                        for s in subjects:
                            if s in line:
                                teacher_subject = s
                                break

                if teacher_classes:
                    if teacher_subject and teacher_subject != '/':
                        teacher.subject = teacher_subject
                        teacher.save()

                    TeacherAssignment.objects.create(
                        teacher=teacher,
                        subject=teacher_subject or "عام",
                        classes=list(set(teacher_classes))
                    )
                    stats['processed'] += 1
                    stats['classes'] += len(set(teacher_classes))

        return stats

    except Exception as e:
        logger.error(f"Global Analysis Failed: {e}")
        raise e
