from .models import SchoolMemory, SchoolSettings
import logging

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

    def generate_response(self, system_instruction, user_query, rag_enabled=True):
        """
        Simulates calling Gemini API with System Instructions + RAG Context.
        """
        context = ""
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
