import os

def main():
    env_path = '.env'
    print("=== أداة إدارة مفتاح الذكاء الاصطناعي (OpenRouter) ===")
    print("الاشتراك مع OpenRouter — نموذج DeepSeek. سيتم حفظ المفتاح في ملف .env")

    current_keys = {}
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    k, v = line.strip().split('=', 1)
                    current_keys[k] = v

    print("\n--- OpenRouter API ---")
    print("احصل على المفتاح من: https://openrouter.ai/")
    or_key = input(f"أدخل مفتاح OpenRouter API (الحالي: {current_keys.get('OPENROUTER_API_KEY', 'غير موجود')}): ").strip()
    if or_key:
        current_keys['OPENROUTER_API_KEY'] = or_key

    # إزالة مفاتيح خدمات أخرى إن وُجدت (لتنظيف .env)
    for old in ('DEEPSEEK_API_KEY', 'GOOGLE_API_KEY', 'GROQ_API_KEY', 'ANTHROPIC_API_KEY'):
        current_keys.pop(old, None)
        i = 2
        while current_keys.pop(f'{old}_{i}', None) is not None:
            i += 1

    with open(env_path, 'w', encoding='utf-8') as f:
        for k, v in current_keys.items():
            f.write(f"{k}={v}\n")

    print("\n✅ تم حفظ المفتاح بنجاح! يرجى إعادة تشغيل التطبيق لتفعيله.")
    input("اضغط Enter للخروج...")

if __name__ == "__main__":
    main()
