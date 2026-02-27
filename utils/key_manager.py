import os

def main():
    env_path = '.env'
    print("=== أداة إدارة مفاتيح الذكاء الاصطناعي ===")
    print("سيتم حفظ المفاتيح في ملف .env")

    current_keys = {}
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    k, v = line.strip().split('=', 1)
                    current_keys[k] = v

    # 1. Google Gemini
    print("\n--- Google Gemini ---")
    g_key = input(f"أدخل مفتاح Google API (الحالي: {current_keys.get('GOOGLE_API_KEY', 'غير موجود')}): ").strip()
    if g_key: current_keys['GOOGLE_API_KEY'] = g_key

    # 2. Groq
    print("\n--- Groq ---")
    groq_key = input(f"أدخل مفتاح Groq API (الحالي: {current_keys.get('GROQ_API_KEY', 'غير موجود')}): ").strip()
    if groq_key: current_keys['GROQ_API_KEY'] = groq_key

    # 3. Anthropic Claude
    print("\n--- Anthropic Claude ---")
    c_key = input(f"أدخل مفتاح Claude API (الحالي: {current_keys.get('ANTHROPIC_API_KEY', 'غير موجود')}): ").strip()
    if c_key: current_keys['ANTHROPIC_API_KEY'] = c_key

    # Save
    with open(env_path, 'w', encoding='utf-8') as f:
        for k, v in current_keys.items():
            f.write(f"{k}={v}\n")

    print("\n✅ تم حفظ المفاتيح بنجاح! يرجى إعادة تشغيل التطبيق لتفعيلها.")
    input("اضغط Enter للخروج...")

if __name__ == "__main__":
    main()
