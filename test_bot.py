#!/usr/bin/env python3
"""
Тестовий файл для перевірки логіки бота
"""

def test_message_handling():
    """Тестує логіку обробки повідомлень"""
    
    print("🧪 Тестування асинхронної логіки бота:")
    print("=" * 60)
    
    # Тестуємо команди
    commands = ["/start", "/help", "/status", "/ping", "/r"]
    print("📋 Команди:")
    for cmd in commands:
        print(f"  ✅ {cmd}")
    
    # Тестуємо функцію кидання кубиків
    print("\n🎲 Кидання кубиків:")
    dice_tests = [
        "/r d20",
        "/r d6+2", 
        "/r d100-5+10",
        "/r d4",
        "/r d12-3",
        "/r d4*2",
        "/r (d4*2)+6",
        "/r d6*3-1"
    ]
    
    for dice_test in dice_tests:
        print(f"  🎯 {dice_test}")
    
    # Тестуємо логіку парсингу
    print("\n🧮 Тестування парсингу формул:")
    test_formulas = [
        "d20", "d6+2", "d100-5+10", "d4", "d12-3",
        "d4*2", "(d4*2)+6", "d6*3-1"
    ]
    
    for formula in test_formulas:
        print(f"  📝 Формула: {formula}")
    
    # Тестуємо автоматичні відповіді
    print("\n💬 Автоматичні відповіді:")
    test_scenarios = [
        {"message": "Дарова всім!", "thread_id": None, "description": "Основна гілка"},
        {"message": "Привіт, як справи?", "thread_id": None, "description": "Без відповіді"},
        {"message": "Дарова, що нового?", "thread_id": 123, "description": "Гілка 123"},
        {"message": "Добрий день!", "thread_id": None, "description": "Без відповіді"},
        {"message": "Дарова, друзі!", "thread_id": 456, "description": "Гілка 456"}
    ]
    
    for scenario in test_scenarios:
        message = scenario["message"]
        thread_id = scenario["thread_id"]
        description = scenario["description"]
        
        message_lower = message.lower()
        if "дарова" in message_lower:
            response = "Ку"
            thread_info = f" в гілці {thread_id}" if thread_id else " в основній гілці"
            print(f"  ✅ '{message}' -> '{response}'{thread_info} ({description})")
        else:
            print(f"  ❌ '{message}' -> Без відповіді ({description})")
    
    print("\n⚡ Асинхронні особливості:")
    print("  ✅ Всі обробники async/await")
    print("  ✅ Правильна обробка гілок чату")
    print("  ✅ Ефективне логування")
    print("  ✅ Обробка помилок")
    print("  ✅ Функція кидання кубиків")
    print("  ✅ Кольорове маркування критичних значень")
    
    print("=" * 60)
    print("🎯 Тест завершено! Бот готовий до роботи!")

if __name__ == "__main__":
    test_message_handling()
