# تقرير: ربط عمليات الذكاء الاصطناعي بمفتاح OpenRouter فقط (نموذج DeepSeek)

## ملخص العملية

تم توحيد كل عمليات الذكاء الاصطناعي لاستخدام **الاشتراك مع OpenRouter فقط** بمفتاح واحد (`OPENROUTER_API_KEY`) ونموذج **DeepSeek** (`deepseek/deepseek-chat`). تم حذف المفاتيح الأخرى (Google، Groq، Anthropic، ومفتاح DeepSeek المباشر).

---

## 1. المواقع التي تستخدم الذكاء الاصطناعي

| الملف / المكوّن | الاستخدام |
|-----------------|-----------|
| `students/ai_utils.py` | خدمة `AIService`: الردود النصية، المساعد، RAG، تحليل الإسناد (استخراج JSON من نصوص) |
| `students/ai_views.py` | واجهات تستدعي `AIService` (مثلاً مساعد الشاشة / البوت) |
| `students/grade_importer.py` | استدعاء LLM لتحليل النصوص المستخرجة من Excel/PDF |
| `students/reminder_views.py` | استدعاء `AIService` للمهام/التذكيرات |
| `students/ui_views.py` | لوحة التحكم: عرض رصيد الذكاء الاصطناعي (اختياري، DeepSeek لا يوفّر رصيداً عاماً فتُعرض N/A) |

كل هذه الاستدعاءات تمرّ عبر `AIService` في `students/ai_utils.py`، لذلك كان كافياً تعديل هذه الخدمة لاستخدام DeepSeek فقط.

---

## 2. التعديلات المنفذة

### 2.1 `students/ai_utils.py`

- **الاعتماد الوحيد:** OpenRouter بمفتاح `OPENROUTER_API_KEY` ونموذج `deepseek/deepseek-chat`.
- **إضافة/استعادة:** `_try_openrouter(prompt)` ترسل الطلبات إلى `https://openrouter.ai/api/v1/chat/completions` مع النموذج `deepseek/deepseek-chat`.
- **استعادة:** `get_openrouter_balance()` لجلب رصيد الاعتماد من OpenRouter وعرضه في لوحة التحكم.
- **تعديل:** `generate_response()` لاستخدام `_try_openrouter()` فقط؛ رسائل الخطأ تشير إلى OpenRouter.

### 2.2 `utils/key_manager.py`

- **الاعتماد الوحيد:** طلب مفتاح **OpenRouter فقط** (`OPENROUTER_API_KEY`) مع توضيح أن المفتاح من https://openrouter.ai.  
- عند الحفظ، الأداة تحذف من `.env` مفاتيح الخدمات الأخرى (مثل DEEPSEEK_API_KEY، GOOGLE_API_KEY، GROQ_API_KEY، ANTHROPIC_API_KEY) مع الإبقاء على بقية المفاتيح.

### 2.3 `.env.example`

- مفتاح واحد للذكاء الاصطناعي:  
  `OPENROUTER_API_KEY=your_openrouter_api_key`  
  مع تعليق يشير إلى الاشتراك مع OpenRouter (https://openrouter.ai) ونموذج DeepSeek.

### 2.4 `students/ui_views.py` (لوحة التحكم)

- **إضافة:** استيراد `AIService` واستدعاء `ai_service.get_openrouter_balance()` وتمرير النتيجة إلى القالب تحت اسم `openrouter_balance` لعرض رصيد الاعتماد في لوحة التحكم.

### 2.5 القوالب

- **`students/templates/students/dashboard.html`:** يستمر استخدام `openrouter_balance`؛ إن وُجد رصيد من OpenRouter يُعرض، وإلا يظهر N/A.

---

## 3. المفاتيح المحذوفة من الاستخدام

| المفتاح | الخدمة |
|--------|--------|
| `GOOGLE_API_KEY` | Google Gemini |
| `GROQ_API_KEY` | Groq |
| `ANTHROPIC_API_KEY` | Claude (Anthropic) |
| `DEEPSEEK_API_KEY` | DeepSeek API المباشر (الاستخدام عبر OpenRouter فقط الآن) |

لا يُستخدم أي من هذه المفاتيح في الكود بعد التعديل.

---

## 4. المفتاح المعتمد حالياً

| المفتاح | الخدمة | الحصول على المفتاح |
|--------|--------|---------------------|
| `OPENROUTER_API_KEY` | OpenRouter (نموذج: deepseek/deepseek-chat) | https://openrouter.ai |

يُحمّل المفتاح من متغير البيئة أو من ملف `.env` عبر `load_dotenv()` في الإعدادات. رصيد الاعتماد يُعرض في لوحة التحكم عند توفره من واجهة OpenRouter.

---

## 5. توصيات للمستخدم

1. **إضافة المفتاح:** الاشتراك مع OpenRouter. في جذر المشروع، في ملف `.env`، أضف:  
   `OPENROUTER_API_KEY=sk-or-...`  
   أو شغّل أداة إدارة المفاتيح:  
   `python utils/key_manager.py`  
   وادخل مفتاح OpenRouter عند الطلب.

2. **تنظيف `.env`:** إن وُجدت مفاتيح قديمة (Google، Groq، Anthropic، DEEPSEEK_API_KEY)، يمكنك حذفها يدوياً أو تشغيل `key_manager.py` مرة واحدة؛ الأداة تحذفها تلقائياً عند الحفظ.

3. **رصيد لوحة التحكم:** بطاقة "رصيد الذكاء الاصطناعي" تعرض رصيد اعتماد OpenRouter عند توفره؛ وإلا تظهر N/A.

---

## 6. الخلاصة

- **جميع عمليات الذكاء الاصطناعي** في التطبيق تعتمد على **الاشتراك مع OpenRouter** بمفتاح واحد (`OPENROUTER_API_KEY`) ونموذج **DeepSeek** (`deepseek/deepseek-chat`).
- **تم إلغاء استخدام** مفاتيح Google، Groq، Anthropic، ومفتاح DeepSeek المباشر من الكود ومن مثال `.env` وأداة إدارة المفاتيح.
- **رصيد الاعتماد** يُعرض في لوحة التحكم من واجهة OpenRouter عند توفره.

تاريخ التقرير: 2025-03-15
