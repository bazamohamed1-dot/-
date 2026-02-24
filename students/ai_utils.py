from .models import SchoolMemory, SchoolSettings, Employee, TeacherAssignment
import logging
import os
import re
from PyPDF2 import PdfReader
from docx import Document
from bs4 import BeautifulSoup
import openpyxl

logger = logging.getLogger(__name__)

class AIService:
    """
    Service to handle AI interactions (Mocking Gemini for now).
    Implements RAG (Retrieval-Augmented Generation) and Context Injection.
    """

    def __init__(self):
        self.settings = SchoolSettings.objects.first()
        self.tone = self.settings.ai_tone if self.settings else "professional"
        self.focus = self.settings.ai_focus if self.settings else "academic"

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

        # Simple string concatenation of top 3 matches
        context_text = "\n".join([f"[{m.category}] {m.title}: {m.content}" for m in matches[:3]])
        return context_text

    def generate_response(self, system_instruction, user_query, rag_enabled=True, free_mode=False):
        """
        Simulates calling Gemini API with System Instructions + RAG Context.
        If free_mode is True, it acts as a general assistant without RAG constraints.
        """
        context = ""

        if free_mode:
            full_prompt = f"""
            System Role: You are a helpful, creative assistant.
            Mode: Free Brainstorming (Unrestricted).
            User Query: {user_query}
            """
            # Mock Free Response (Simulating dynamic response based on query keywords)
            if "نصيحة" in user_query or "suggest" in user_query:
                return f"إليك بعض الأفكار حول '{user_query}': 1. جرب مقاربة جديدة تعتمد على التفاعل. 2. ابحث عن نماذج ناجحة مشابهة. 3. لا تخف من التجريب!"
            elif "خطة" in user_query or "plan" in user_query:
                return f"لإعداد خطة حول '{user_query}'، أنصحك بالبدء بتحديد الأهداف بوضوح (SMART)، ثم توزيع الأدوار، وأخيراً تحديد جدول زمن مرن."
            else:
                return f"شكراً لسؤالك حول '{user_query}'. هذا موضوع مثير للاهتمام! في الوضع الحر، نركز على الإبداع. ماذا لو نظرنا للأمر من زاوية مختلفة؟"

        if rag_enabled:
            context = self.get_rag_context(user_query)

        # Construct the full prompt (Mental Model of what gets sent to API)
        full_prompt = f"""
        System Role: You are an educational assistant at a school.
        Tone: {self.tone}
        Focus: {self.focus}

        System Instructions (Manager Context):
        {system_instruction}

        School Memory (Context):
        {context if context else "No specific school records found."}

        User Query:
        {user_query}
        """

        logger.info(f"AI Prompt Generated:\n{full_prompt}")

        # --- MOCK RESPONSE LOGIC ---
        # Simulate AI behavior based on instructions

        if "observation" in user_query.lower() or "ملاحظة" in user_query:
            return self._mock_observation_response(user_query)

        if "explain task" in user_query.lower() or "اشرح" in user_query:
            return self._mock_task_explanation(system_instruction)

        return "بناءً على تعليمات المدير وسياق المدرسة، أنصحك بالتركيز على الجانب التربوي والالتزام بالقانون الداخلي."

    def _mock_observation_response(self, query):
        if "تشتت" in query or "distracted" in query:
            return "بناءً على حالة التلميذ، نقترح استخدام وسائل بصرية لزيادة التركيز، وتغيير مكان جلوسه ليكون أقرب للسبورة. (تم استنتاج ذلك من سجلات المدرسة حول حالات مشابهة)."
        if "غياب" in query or "absent" in query:
            return "يجب استدعاء الولي فوراً لتبرير الغياب طبقاً للمادة 12 من القانون الداخلي. نقترح صيغة استدعاء تركز على مصلحة التلميذ."
        return "شكراً على الملاحظة. نقترح صياغة التقرير بأسلوب يبرز نقاط القوة قبل الضعف لتشجيع الولي على التعاون."

    def _mock_task_explanation(self, manager_instructions):
        return f"مرحباً أيها الزميل. بناءً على توجيهات المدير: '{manager_instructions}'، إليك الخطوات العملية:\n1. قم بمراجعة القائمة.\n2. تأكد من البيانات.\n3. سجل الملاحظة بدقة.\nبالتوفيق في مهامك!"

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
            # Using our util or just openpyxl quickly here since we need text blob
            # For structure, it's better to iterate rows, but "Global Analysis" implies finding names in text.
            # Let's dump all cells to text.
            import pandas as pd
            try:
                df = pd.read_excel(file_path)
                text = df.to_string()
            except:
                # Fallback
                pass

        # Fallback text extraction if pandas failed or not xlsx
        if not text and ext in ['.html', '.htm']:
             with open(file_path, 'r', encoding='utf-8') as f:
                 soup = BeautifulSoup(f.read(), 'html.parser')
                 text = soup.get_text()

        # If text is still empty (maybe failed xls read), try to read as text
        if not text:
             try:
                 with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: text = f.read()
             except: pass

        # --- AI LOGIC (Regex/Heuristic) ---
        # 1. Find Teachers
        teachers = Employee.objects.filter(rank='teacher')

        stats = {'processed': 0, 'classes': 0}

        for teacher in teachers:
            # Check if teacher name exists in text (Fuzzy match recommended, here simple substring)
            # Try Last Name + First Name, or just Last Name if unique
            name_match = False
            if teacher.last_name in text or teacher.first_name in text:
                name_match = True

            if name_match:
                # Find Classes near the name? Or just find all classes in text and assign?
                # The user said "Analyze it... extract subjects... link to DB".
                # Realistically, without a structured format, we can't know WHICH class belongs to WHICH teacher
                # unless we parse rows.
                # Assuming the text is line-based: "Teacher Name ... Subject ... Class1, Class2"

                # Mock Logic: Find classes in the same "context window" as the teacher name
                # Implementation: Split text by lines. If line has teacher name, look for classes in that line.

                teacher_classes = []
                teacher_subject = teacher.subject # Default to existing

                # Regex for classes: 1M1, 4AM2, etc.
                class_pattern = r'\b(\d+[AM]+\d+|\d+M\d+)\b'

                lines = text.split('\n')
                for line in lines:
                    if teacher.last_name in line or teacher.first_name in line:
                        # Found teacher line
                        found_classes = re.findall(class_pattern, line)
                        teacher_classes.extend(found_classes)

                        # Try to find subject in this line
                        subjects = ['رياضيات', 'فيزياء', 'علوم', 'عربية', 'فرنسية', 'انجليزية', 'تاريخ', 'جغرافيا', 'إسلامية', 'مدنية', 'إعلام آلي', 'تكنولوجية', 'بدنية', 'تشكيلية', 'موسيقى']
                        for s in subjects:
                            if s in line:
                                teacher_subject = s
                                break

                if teacher_classes:
                    # Update Teacher
                    if teacher_subject and teacher_subject != '/':
                        teacher.subject = teacher_subject
                        teacher.save()

                    # Create Assignment
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
