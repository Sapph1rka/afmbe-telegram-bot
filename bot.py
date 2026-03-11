import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from database import (
    init_database, get_user_by_telegram_id, get_gm, set_gm, create_character,
    grant_character_access, get_user_characters, set_active_character,
    get_active_character, check_character_access, set_attribute_value,
    set_skill_level, set_resource_value, get_character_sheet,
    add_item_template, add_item_to_character, get_character_inventory,
    remove_item_from_character, add_trait, remove_trait
)
from models import AccessRole, ItemType, ArmorSlot

# Завантажуємо змінні середовища
load_dotenv()

# Список Telegram ID, яким дозволена команда /deception (через кому в .env: DECEPTION_ALLOWED_IDS=123,456)
_deception_ids_str = os.getenv('DECEPTION_ALLOWED_IDS', '')
ALLOWED_DECEPTION_IDS = {int(x.strip()) for x in _deception_ids_str.split(',') if x.strip().isdigit()}

# Зберігання наступного "підтасованого" кидка: ключ — тип кубика (d10, d20...), значення — число на кубику
DECEPTION_NEXT_ROLL = {}

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /help"""
    help_text = """
🤖 Доступні команди:
/start - Почати роботу з ботом
/help - Показати цю довідку
/status - Показати статус бота та інформацію про чат
/r - Кинути кубик з модифікаторами

👤 Управління персонажами:
/createperson <ім'я> - Створити нового персонажа
/usecharacter <ім'я> - Прив'язати персонажа до користувача
/control [ім'я] - Встановити активного персонажа (без параметра - список доступних)
/sheet - Показати короткий лист активного персонажа

⚙️ Налаштування:
/gm - Встановити себе як GM (тільки якщо GM ще не встановлений)

📝 Редагування персонажа:
/set attribute <назва> <значення> - Змінити стату
  Приклади: /set attribute Сила 5, /set attribute Спритність 4
/set skill <назва> <рівень> - Додати/змінити навичку
  Приклад: /set skill Стрільба 3
/set resource <назва> <поточне> - Змінити поточне значення ресурсу
  Приклади: /set resource Витривалість 30, /set resource Здоров'я 25
/setmax resource <назва> <максимальне> - Встановити максимальне значення ресурсу
  Приклад: /setmax resource Витривалість 50
/set trait <назва> - Додати черту

🎒 Інвентар:
/add <тип> <назва> - Додати предмет
  Для броні: /add armor <назва> <захист> [слот]
  Для зброї: /add weapon <назва> <урон>
  Типи: weapon, armor, equipment, ammunition, consumable
  Слоти для броні: голова, шия, торс, руки, долоні, ноги, ступні
  Приклади:
  /add armor Шолом d4-1 голова
  /add weapon Ніж d6+2
/remove <назва> - Видалити предмет з інвентаря
/inventory - Показати інвентар активного персонажа

🎲 Кидання кубиків:
• /r d20 - кинути d20
• /r d6+2 - кинути d6 і додати 2
• /r d100-5+10 - кинути d100, відняти 5, додати 10
• /r d4*2 - кинути d4 і помножити на 2

💥 Вибухові кубики d10:
• 10 = кидаємо ще раз, додаємо (результат-5) якщо >5
• 1 = кидаємо ще раз: 1=повний провал, 2-4=провал, 5-10=залишаємо 1

📊 Рівні успіху (тільки для d10):
• ≤8 = Провал
• 9-10 = це 1
• 11-12 = це 2
• 13-15 = це 3
• 16-18 = це 4
• 19-22 = це 5
• 23-26 = це 6
• 27+ = це 7
"""
    try:
        await update.message.reply_text(help_text)
    except Exception as e:
        logger.error(f"Помилка команди /help: {e}")
        # Спробуємо надіслати повідомлення без reply
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=help_text
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник всіх повідомлень"""
    # Перевіряємо, чи повідомлення з групи
    if update.effective_chat.type in ['group', 'supergroup']:
        message_text = update.message.text.lower()
        
        # Якщо повідомлення містить "дарова", відповідаємо "Ку"
        if "Дарова" in message_text:
            # Відповідаємо в ту ж гілку чату (thread), де було повідомлення
            try:
                if update.message.message_thread_id:
                    # Якщо є гілка чату, відповідаємо в неї
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="Ку",
                        message_thread_id=update.message.message_thread_id
                    )
                else:
                    # Якщо немає гілки, використовуємо звичайну відповідь
                    await update.message.reply_text("Ку")
            except Exception as e:
                # Якщо щось пішло не так, спробуємо звичайну відповідь
                await update.message.reply_text("Ку")
                logger.warning(f"Помилка відповіді в гілці чату: {e}")
            
            logger.info(f"Відповів 'Ку' на повідомлення: {update.message.text} в гілці: {update.message.message_thread_id}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник помилок"""
    logger.error(f"Exception while handling an update: {context.error}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /status"""
    user = update.effective_user
    chat = update.effective_chat
    
    status_text = f"""
📊 Статус бота:
👤 Користувач: {user.first_name} {user.last_name or ''}
🆔 User ID: {user.id}
💬 Чат: {chat.title or chat.type}
🆔 Chat ID: {chat.id}
🕐 Час: {update.message.date.strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    try:
        await update.message.reply_text(status_text)
    except Exception as e:
        logger.error(f"Помилка команди /status: {e}")
        # Спробуємо надіслати повідомлення без reply
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=status_text
        )
    
    logger.info(f"Показав статус для користувача {user.id}")


async def roll_dice_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /r для кидання кубиків"""
    import re
    import random
    
    # Отримуємо текст команди
    command_text = update.message.text.strip()
    
    # Перевіряємо формат команди
    if not command_text.startswith('/r '):
        await update.message.reply_text("❌ Використання: /r d<число>[+/-<модифікатор>...]")
        return
    
    # Видаляємо '/r ' і парсимо формулу
    formula = command_text[3:].strip()
    
    # Додаткова перевірка
    if not formula:
        await update.message.reply_text("❌ Вкажіть формулу кубика!\n💡 Приклад: /r d20+5-2")
        return
    
    logger.info(f"Спроба кинути кубик: '{formula}' від користувача {update.effective_user.id}")
    
    try:
        # Перевірка підтасованого кидка (deception): наступний /r з таким дайсом покаже задане значення
        forced_dice_result = None
        dice_type_match = re.search(r'd(\d+)', formula)
        if dice_type_match:
            dice_type = dice_type_match.group(0).lower()  # d10, d20 ...
            if dice_type in DECEPTION_NEXT_ROLL:
                forced_dice_result = DECEPTION_NEXT_ROLL.pop(dice_type)
                logger.info(f"Застосовано deception: {dice_type} = {forced_dice_result}")
        # Парсимо формулу кубика
        result = parse_dice_formula(formula, forced_dice_result=forced_dice_result)
        
        # Формуємо відповідь з рівнем успіху
        response = f"🎲 {formula} = {result['result']}"
        
        # Додаємо рівень успіху, якщо він є
        if result.get('success_level'):
            if result['success_level'] == "Провал":
                response += f"\n❌ Рівень: {result['success_level']}"
            else:
                response += f"\n✅ Рівень: {result['success_level']}"
        
        if result['details']:
            response += f"\n📊 Деталі: {result['details']}"
        
        # Відповідаємо в ту ж гілку чату
        try:
            if update.message.message_thread_id:
                # Якщо є гілка чату, відповідаємо в неї
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=response,
                    message_thread_id=update.message.message_thread_id
                )
            else:
                # Якщо немає гілки, використовуємо звичайну відповідь
                await update.message.reply_text(response)
        except Exception as e:
            # Якщо щось пішло не так, спробуємо звичайну відповідь
            await update.message.reply_text(response)
            logger.warning(f"Помилка відповіді в гілці чату: {e}")
        
        logger.info(f"✅ Успішно кинув кубик: {formula} = {result['result']} для користувача {update.effective_user.id}")
        
    except ValueError as e:
        error_msg = f"❌ Помилка в формулі: {str(e)}\n💡 Приклад: /r d20+5-2"
        await update.message.reply_text(error_msg)
        logger.warning(f"❌ Помилка кидання кубика: {formula} - {str(e)}")
    except Exception as e:
        error_msg = f"❌ Неочікувана помилка: {str(e)}\n💡 Спробуйте ще раз"
        await update.message.reply_text(error_msg)
        logger.error(f"💥 Критична помилка кидання кубика: {formula} - {str(e)}")
        # Додаткове логування для діагностики
        import traceback
        logger.error(f"Повний traceback: {traceback.format_exc()}")


async def deception_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /deception — тільки для ID зі списку. Встановлює результат наступного кидка дайса."""
    import re
    user_id = update.effective_user.id
    if user_id not in ALLOWED_DECEPTION_IDS:
        return
    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Використання: /deception <дайс> <значення>\n"
            "Приклад: /deception d10 10 — наступний /r d10 (у будь-якому чаті) покаже 10."
        )
        return
    dice_type = args[0].strip().lower()
    try:
        value = int(args[1].strip())
    except ValueError:
        await update.message.reply_text("❌ Значення має бути числом.")
        return
    match = re.match(r'^d(\d+)$', dice_type)
    if not match:
        await update.message.reply_text("❌ Дайс у форматі d<число>, наприклад d10, d20.")
        return
    dice_size = int(match.group(1))
    if dice_size <= 0:
        await update.message.reply_text("❌ Розмір кубика має бути більше 0.")
        return
    if not (1 <= value <= dice_size):
        await update.message.reply_text(f"❌ Для {dice_type} значення має бути від 1 до {dice_size}.")
        return
    DECEPTION_NEXT_ROLL[dice_type] = value
    await update.message.reply_text(f"✅ Наступний кидок {dice_type} у будь-якому чаті покаже {value}.")
    logger.info(f"Deception встановлено: {dice_type} = {value} (користувач {user_id})")


def get_success_level(result: int) -> str:
    """Визначає рівень успіху на основі результату"""
    if result <= 8:
        return "Провал"
    elif 9 <= result <= 10:
        return "це 1"
    elif 11 <= result <= 12:
        return "це 2"
    elif 13 <= result <= 15:
        return "це 3"
    elif 16 <= result <= 18:
        return "це 4"
    elif 19 <= result <= 22:
        return "це 5"
    elif 23 <= result <= 26:
        return "це 6"
    elif result >= 27:
        return "це 7"
    else:
        return "Невідомий рівень"

def escape_markdown_v2(text: str) -> str:
    """Екранує спеціальні символи для MarkdownV2"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def _safe_eval_arithmetic(expr: str) -> int:
    """Безпечно обчислює арифметичний вираз. Дозволені лише цифри та оператори + - * / ( ).
    Захист від ін'єкції коду через /r d20+злий_код."""
    allowed = set("0123456789+-*/( )")
    cleaned = expr.replace(" ", "")
    if not cleaned:
        raise ValueError("Порожня формула")
    if not all(c in allowed for c in cleaned):
        raise ValueError("Дозволені лише числа та оператори + - * / ( )")
    try:
        result = eval(cleaned)
    except Exception:
        raise ValueError("Невірний вираз")
    if not isinstance(result, (int, float)):
        raise ValueError("Результат не є числом")
    return int(result)


def parse_dice_formula(formula: str, forced_dice_result: int | None = None) -> dict:
    """Парсить формулу кубика та обчислює результат з вибуховими кубиками для d10.
    Якщо forced_dice_result задано, перший кидок дайса буде цим числом (для /deception)."""
    import re
    import random
    
    # Регулярний вираз для пошуку кубика
    dice_pattern = r'd(\d+)'
    dice_match = re.search(dice_pattern, formula)
    
    if not dice_match:
        raise ValueError("Не знайдено кубик у форматі d<число>")
    
    # Отримуємо розмір кубика
    dice_size = int(dice_match.group(1))
    
    if dice_size <= 0:
        raise ValueError("Розмір кубика має бути більше 0")
    
    if forced_dice_result is not None and not (1 <= forced_dice_result <= dice_size):
        raise ValueError(f"Підтасоване значення має бути від 1 до {dice_size}")
    
    # Отримуємо оригінальну формулу без кубика для обчислення модифікаторів
    original_formula = formula.replace(dice_match.group(0), '')
    
    # Кидаємо перший кубик (або використовуємо підтасоване значення)
    dice_result = forced_dice_result if forced_dice_result is not None else random.randint(1, dice_size)
    total_bonus = 0
    explosion_details = []
    
    # Спеціальна логіка для d10 (вибухові кубики)
    if dice_size == 10:
        if dice_result == 10:
            # Вибуховий успіх - кидаємо додаткові кубики
            explosion_bonus = 0
            explosion_count = 0
            current_roll = 10
            
            while current_roll == 10:
                explosion_count += 1
                current_roll = random.randint(1, 10)
                if current_roll > 5:
                    explosion_bonus += current_roll - 5
                    explosion_details.append(f"вибух #{explosion_count}: d10={current_roll} (+{current_roll-5})")
                else:
                    explosion_details.append(f"вибух #{explosion_count}: d10={current_roll} (без бонусу)")
            
            total_bonus = explosion_bonus
            details = f"d{dice_size}=🟢{dice_result}🟢 (критичний успіх!)"
            if explosion_details:
                details += f", вибухи: {'; '.join(explosion_details)}"
                details += f", загальний бонус: +{total_bonus}"
        
        elif dice_result == 1:
            # Критичний провал - кидаємо ще раз
            second_roll = random.randint(1, 10)
            if second_roll == 1:
                # Повний провал
                details = f"d{dice_size}=🔴{dice_result}🔴 (КРИТИЧНИЙ провал! d10={second_roll})"
                total_bonus = -999  # Спеціальне значення для повного провалу
            elif 2 <= second_roll <= 4:
                # Просто провал
                details = f"d{dice_size}=🔴{dice_result}🔴 (звичайний провал! d10={second_roll})"
                total_bonus = -100  # Спеціальне значення для провалу
            else:
                # Залишаємо 1 як число
                details = f"d{dice_size}=🔴{dice_result}🔴 (провал, але d10={second_roll} - залишаємо як число)"
                total_bonus = 0
        
        else:
            # Звичайний результат
            details = f"d{dice_size}={dice_result}"
    else:
        # Для інших кубиків - звичайна логіка
        if dice_result == 1:
            details = f"d{dice_size}=🔴{dice_result}🔴 (критичний провал!)"
        elif dice_result == dice_size:
            details = f"d{dice_size}=🟢{dice_result}🟢 (критичний успіх!)"
        else:
            details = f"d{dice_size}={dice_result}"
    
    # Створюємо формулу з результатом кубика для всіх випадків
    formula_with_result = formula.replace(dice_match.group(0), str(dice_result))
    
    # Обчислюємо фінальний результат
    if total_bonus == -999:
        # Повний провал
        final_result = "ПОВНИЙ ПРОВАЛ"
    elif total_bonus == -100:
        # Провал
        final_result = "ПРОВАЛ"
    else:
        # Звичайний результат
        try:
            # Додаємо бонус від вибухових кубиків
            if total_bonus > 0:
                formula_with_result += f"+{total_bonus}"
            
            # Безпечне обчислення: лише числа та оператори + - * / ( ) — без eval() від користувача
            final_result = _safe_eval_arithmetic(formula_with_result)
            
        except Exception as e:
            raise ValueError(f"Помилка обчислення формули: {str(e)}")
    
    # Парсимо всі операції для детального показу
    operations = []
    
    # Знаходимо множення та ділення
    mult_div_pattern = r'(\d+[\*/]\d+)'
    mult_div_matches = re.findall(mult_div_pattern, formula_with_result)
    for op in mult_div_matches:
        operations.append(op)
    
    # Знаходимо додавання та віднімання
    add_sub_pattern = r'([+-]\d+)'
    add_sub_matches = re.findall(add_sub_pattern, formula_with_result)
    for op in add_sub_matches:
        operations.append(op)
    
    if operations:
        details += f", операції: {', '.join(operations)}"
    # Визначаємо рівень успіху тільки для d10
    success_level = None
    if dice_size == 10 and isinstance(final_result, int) and final_result > 0:
        success_level = get_success_level(final_result)
    
    return {
        'result': final_result,
        'dice_result': dice_result,
        'dice_size': dice_size,
        'operations': operations,
        'details': details,
        'total_bonus': total_bonus,
        'explosion_details': explosion_details,
        'success_level': success_level
    }

async def createperson_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /createperson"""
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ Використання: /createperson <ім'я>")
        return
    
    character_name = ' '.join(context.args)
    telegram_id = update.effective_user.id
    
    try:
        character_id = create_character(name=character_name)
        user = get_user_by_telegram_id(telegram_id)
        
        # Надаємо доступ як Owner
        grant_character_access(user.id, character_id, AccessRole.OWNER)
        
        # Встановлюємо як активного персонажа
        set_active_character(telegram_id, character_id)
        
        await update.message.reply_text(f"✅ Персонаж '{character_name}' створено та встановлено як активного")
        logger.info(f"Користувач {telegram_id} створив персонажа '{character_name}'")
    except Exception as e:
        logger.error(f"Помилка створення персонажа: {e}")
        await update.message.reply_text(f"❌ Помилка створення персонажа: {str(e)}")

async def gm_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /gm"""
    telegram_id = update.effective_user.id
    
    success, message = set_gm(telegram_id)
    if success:
        await update.message.reply_text(f"✅ {message}")
    else:
        await update.message.reply_text(f"❌ {message}")
    
    logger.info(f"Користувач {telegram_id} спробував встановити GM: {message}")

async def usecharacter_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /usecharacter"""
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ Використання: /usecharacter <ім'я>")
        return
    
    character_name = ' '.join(context.args)
    telegram_id = update.effective_user.id
    
    try:
        # Знаходимо персонажа серед доступних
        characters = get_user_characters(telegram_id)
        character = None
        for char in characters:
            if char.name.lower() == character_name.lower():
                character = char
                break
        
        if not character:
            await update.message.reply_text(f"❌ Персонаж '{character_name}' не знайдено або у вас немає доступу")
            return
        
        # Встановлюємо як активного
        success, message = set_active_character(telegram_id, character.id)
        if success:
            await update.message.reply_text(f"✅ {message}: {character.name}")
        else:
            await update.message.reply_text(f"❌ {message}")
    except Exception as e:
        logger.error(f"Помилка використання персонажа: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")

async def control_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /control"""
    telegram_id = update.effective_user.id
    
    try:
        if not context.args or len(context.args) == 0:
            # Показуємо список доступних персонажів
            characters = get_user_characters(telegram_id)
            if not characters:
                await update.message.reply_text("❌ У вас немає доступних персонажів")
                return
            
            active_char = get_active_character(telegram_id)
            active_id = active_char.id if active_char else None
            
            char_list = []
            for char in characters:
                marker = "👤 " if active_id == char.id else "  "
                char_list.append(f"{marker}{char.name}")
            
            response = "📋 Доступні персонажі:\n" + "\n".join(char_list)
            if active_char:
                response += f"\n\n👤 Активний: {active_char.name}"
            
            await update.message.reply_text(response)
        else:
            # Встановлюємо активного персонажа
            character_name = ' '.join(context.args)
            characters = get_user_characters(telegram_id)
            character = None
            for char in characters:
                if char.name.lower() == character_name.lower():
                    character = char
                    break
            
            if not character:
                await update.message.reply_text(f"❌ Персонаж '{character_name}' не знайдено або у вас немає доступу")
                return
            
            success, message = set_active_character(telegram_id, character.id)
            if success:
                await update.message.reply_text(f"✅ Тепер ви граєте за: {character.name}")
            else:
                await update.message.reply_text(f"❌ {message}")
    except Exception as e:
        logger.error(f"Помилка команди /control: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")

async def sheet_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /sheet"""
    telegram_id = update.effective_user.id
    
    try:
        character = get_active_character(telegram_id)
        if not character:
            await update.message.reply_text("❌ У вас немає активного персонажа. Використайте /control <ім'я>")
            return
        
        sheet_data = get_character_sheet(character.id)
        if not sheet_data:
            await update.message.reply_text("❌ Помилка отримання даних персонажа")
            return
        
        char = sheet_data['character']
        attrs = sheet_data['attributes']
        skills = sheet_data['skills']
        traits = sheet_data['traits']
        resources = sheet_data['resources']
        
        # Формуємо відповідь
        response = f"📋 Лист персонажа: {char.name}\n"
        response += f"⚡ Швидкість: {char.speed}\n\n"
        
        # Стати
        if attrs:
            response += "📊 Стати:\n"
            for attr_name, value in attrs.items():
                response += f"  • {attr_name}: {value}\n"
            response += "\n"
        
        # Навички
        if skills:
            response += "🎯 Навички:\n"
            for skill_name, level in skills.items():
                response += f"  • {skill_name}: {level}\n"
            response += "\n"
        else:
            response += "🎯 Навички: немає\n\n"
        
        # Черти
        if traits:
            response += "⭐ Черти:\n"
            for trait_name in traits:
                response += f"  • {trait_name}\n"
            response += "\n"
        else:
            response += "⭐ Черти: немає\n\n"
        
        # Ресурси
        if resources:
            response += "💚 Ресурси:\n"
            for res_name, res_data in resources.items():
                current = res_data['current']
                max_val = res_data['max']
                response += f"  • {res_name}: {current}/{max_val}\n"
        
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Помилка команди /sheet: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")

async def set_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /set"""
    if not context.args or len(context.args) < 3:
        await update.message.reply_text(
            "❌ Використання:\n"
            "/set attribute <назва> <значення>\n"
            "/set skill <назва> <рівень>\n"
            "/set resource <назва> <поточне>\n"
            "/set trait <назва> - Додати черту"
        )
        return
    
    telegram_id = update.effective_user.id
    command_type = context.args[0].lower()
    
    try:
        character = get_active_character(telegram_id)
        if not character:
            await update.message.reply_text("❌ У вас немає активного персонажа. Використайте /control <ім'я>")
            return
        
        # Перевіряємо доступ
        has_access, role = check_character_access(telegram_id, character.id, 
                                                  [AccessRole.GM, AccessRole.OWNER, AccessRole.CONTROLLER])
        if not has_access:
            await update.message.reply_text("❌ У вас немає прав для зміни цього персонажа")
            return
        
        if command_type == "attribute":
            attr_name = context.args[1]
            try:
                value = int(context.args[2])
            except ValueError:
                await update.message.reply_text("❌ Значення має бути числом")
                return
            
            success, message = set_attribute_value(character.id, attr_name, value)
            if success:
                await update.message.reply_text(f"✅ {message}")
            else:
                await update.message.reply_text(f"❌ {message}")
        
        elif command_type == "skill":
            skill_name = ' '.join(context.args[1:-1])
            try:
                level = int(context.args[-1])
            except ValueError:
                await update.message.reply_text("❌ Рівень має бути числом")
                return
            
            success, message = set_skill_level(character.id, skill_name, level)
            if success:
                await update.message.reply_text(f"✅ {message}")
            else:
                await update.message.reply_text(f"❌ {message}")
        
        elif command_type == "resource":
            resource_name = ' '.join(context.args[1:-1])
            try:
                current_value = int(context.args[-1])
            except ValueError:
                await update.message.reply_text("❌ Значення має бути числом")
                return
            
            success, message = set_resource_value(character.id, resource_name, current_value=current_value)
            if success:
                await update.message.reply_text(f"✅ {message}")
            else:
                await update.message.reply_text(f"❌ {message}")
        
        elif command_type == "trait":
            trait_name = ' '.join(context.args[1:])
            if not trait_name:
                await update.message.reply_text("❌ Вкажіть назву черти")
                return
            
            success, message = add_trait(character.id, trait_name)
            if success:
                await update.message.reply_text(f"✅ {message}")
            else:
                await update.message.reply_text(f"❌ {message}")
        
        else:
            await update.message.reply_text("❌ Невідомий тип. Використовуйте: attribute, skill, resource або trait")
    
    except Exception as e:
        logger.error(f"Помилка команди /set: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /add"""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Використання:\n"
            "/add <тип> <назва> - для звичайних предметів\n"
            "/add armor <назва> <захист> [слот] - для броні\n"
            "/add weapon <назва> <урон> - для зброї\n"
            "Типи: weapon, armor, equipment, ammunition, consumable\n"
            "Слоти для броні: голова, шия, торс, руки, долоні, ноги, ступні\n"
            "Приклади:\n"
            "/add armor Шолом d4-1 голова\n"
            "/add weapon Ніж d6+2"
        )
        return
    
    telegram_id = update.effective_user.id
    item_type_str = context.args[0].lower()
    
    # Мапінг типів
    type_mapping = {
        'weapon': ItemType.WEAPON,
        'armor': ItemType.ARMOR,
        'equipment': ItemType.EQUIPMENT,
        'ammunition': ItemType.AMMUNITION,
        'consumable': ItemType.CONSUMABLE
    }
    
    if item_type_str not in type_mapping:
        await update.message.reply_text(f"❌ Невідомий тип предмета. Доступні: {', '.join(type_mapping.keys())}")
        return
    
    # Мапінг слотів броні
    slot_mapping = {
        'голова': ArmorSlot.HEAD,
        'шия': ArmorSlot.NECK,
        'торс': ArmorSlot.TORSO,
        'руки': ArmorSlot.ARMS,
        'долоні': ArmorSlot.HANDS,
        'ноги': ArmorSlot.LEGS,
        'ступні': ArmorSlot.FEET
    }
    
    armor_value = None
    armor_slot = None
    damage = None
    item_name = None
    
    # Для броні потрібно: назва, захист, [слот]
    if item_type_str == 'armor':
        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ Для броні потрібно вказати назву та захист!\n"
                "Використання: /add armor <назва> <захист> [слот]\n"
                "Приклад: /add armor Шолом d4-1 голова"
            )
            return
        
        # Останній аргумент може бути слотом
        last_arg = context.args[-1].lower()
        if last_arg in slot_mapping:
            armor_slot = slot_mapping[last_arg]
            # Захист - передостанній аргумент
            armor_value = context.args[-2]
            # Назва - все між типом та захистом
            item_name = ' '.join(context.args[1:-2])
        else:
            # Немає слота, захист - останній аргумент
            armor_value = context.args[-1]
            # Назва - все між типом та захистом
            item_name = ' '.join(context.args[1:-1])
    elif item_type_str == 'weapon':
        # Для зброї потрібно: назва, урон
        if len(context.args) < 3:
            await update.message.reply_text(
                "❌ Для зброї потрібно вказати назву та урон!\n"
                "Використання: /add weapon <назва> <урон>\n"
                "Приклад: /add weapon Ніж d6+2"
            )
            return
        
        # Урон - останній аргумент
        damage = context.args[-1]
        # Назва - все між типом та уроном
        item_name = ' '.join(context.args[1:-1])
    else:
        # Для інших предметів - просто назва
        item_name = ' '.join(context.args[1:])
    
    if not item_name:
        await update.message.reply_text("❌ Назва предмета не може бути порожньою")
        return
    
    try:
        character = get_active_character(telegram_id)
        if not character:
            await update.message.reply_text("❌ У вас немає активного персонажа. Використайте /control <ім'я>")
            return
        
        # Перевіряємо доступ
        has_access, role = check_character_access(telegram_id, character.id,
                                                  [AccessRole.GM, AccessRole.OWNER, AccessRole.CONTROLLER])
        if not has_access:
            await update.message.reply_text("❌ У вас немає прав для додавання предметів")
            return
        
        # Створюємо шаблон предмета
        template = add_item_template(
            name=item_name,
            item_type=type_mapping[item_type_str],
            armor_value=armor_value,
            armor_slot_type=armor_slot,
            damage=damage
        )
        
        # Додаємо предмет персонажу
        success, message = add_item_to_character(character.id, template.id)
        if success:
            info_parts = []
            if armor_value:
                info_parts.append(f"захист: {armor_value}")
            if armor_slot:
                info_parts.append(f"слот: {armor_slot.value}")
            if damage:
                info_parts.append(f"урон: {damage}")
            info_text = f" ({', '.join(info_parts)})" if info_parts else ""
            await update.message.reply_text(f"✅ {message}{info_text}")
        else:
            await update.message.reply_text(f"❌ {message}")
    
    except Exception as e:
        logger.error(f"Помилка команди /add: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")

async def inventory_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /inventory"""
    telegram_id = update.effective_user.id
    
    try:
        character = get_active_character(telegram_id)
        if not character:
            await update.message.reply_text("❌ У вас немає активного персонажа. Використайте /control <ім'я>")
            return
        
        # Перевіряємо доступ
        has_access, role = check_character_access(telegram_id, character.id)
        if not has_access:
            await update.message.reply_text("❌ У вас немає доступу до цього персонажа")
            return
        
        inventory = get_character_inventory(character.id)
        armor_by_slot = inventory['armor']  # Тепер це словник {слот: [предмети]}
        weapon_items = inventory['weapons']
        other_items = inventory['items']
        
        response = f"🎒 Інвентар: {character.name}\n\n"
        
        # Спочатку показуємо броню, згруповану за слотами
        if armor_by_slot:
            response += "🛡️ Броня:\n"
            # Показуємо в порядку слотів
            slot_order = ['Голова', 'Шия', 'Торс', 'Руки', 'Долоні', 'Ноги', 'Ступні', 'Інше']
            for slot_name in slot_order:
                if slot_name in armor_by_slot:
                    response += f"  {slot_name}:\n"
                    for item in armor_by_slot[slot_name]:
                        armor_text = f"    • {item['name']}"
                        if item['armor_value']:
                            armor_text += f" (Захист: {item['armor_value']})"
                        if item['quantity'] > 1:
                            armor_text += f" x{item['quantity']}"
                        response += armor_text + "\n"
            # Показуємо інші слоти, якщо є
            for slot_name, items in armor_by_slot.items():
                if slot_name not in slot_order:
                    response += f"  {slot_name}:\n"
                    for item in items:
                        armor_text = f"    • {item['name']}"
                        if item['armor_value']:
                            armor_text += f" (Захист: {item['armor_value']})"
                        if item['quantity'] > 1:
                            armor_text += f" x{item['quantity']}"
                        response += armor_text + "\n"
            response += "\n"
        else:
            response += "🛡️ Броня: немає\n\n"
        
        # Потім зброю
        if weapon_items:
            response += "⚔️ Зброя:\n"
            for item in weapon_items:
                weapon_text = f"  • {item['name']}"
                if item['damage']:
                    weapon_text += f" (Урон: {item['damage']})"
                if item['quantity'] > 1:
                    weapon_text += f" x{item['quantity']}"
                response += weapon_text + "\n"
            response += "\n"
        else:
            response += "⚔️ Зброя: немає\n\n"
        
        # Потім інші предмети
        if other_items:
            response += "📦 Предмети:\n"
            # Групуємо за типом
            items_by_type = {}
            for item in other_items:
                item_type = item['type']
                if item_type not in items_by_type:
                    items_by_type[item_type] = []
                items_by_type[item_type].append(item)
            
            for item_type, items in items_by_type.items():
                type_emoji = {
                    'equipment': '🔧',
                    'ammunition': '🔫',
                    'consumable': '💊',
                    'other': '📦'
                }.get(item_type, '📦')
                
                response += f"{type_emoji} {item_type.capitalize()}:\n"
                for item in items:
                    item_text = f"  • {item['name']}"
                    if item['quantity'] > 1:
                        item_text += f" x{item['quantity']}"
                    response += item_text + "\n"
        else:
            response += "📦 Предмети: немає\n"
        
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Помилка команди /inventory: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /remove"""
    if not context.args or len(context.args) < 1:
        await update.message.reply_text(
            "❌ Використання: /remove <назва>\n"
            "Приклад: /remove Шолом"
        )
        return
    
    telegram_id = update.effective_user.id
    item_name = ' '.join(context.args)
    
    try:
        character = get_active_character(telegram_id)
        if not character:
            await update.message.reply_text("❌ У вас немає активного персонажа. Використайте /control <ім'я>")
            return
        
        # Перевіряємо доступ
        has_access, role = check_character_access(telegram_id, character.id,
                                                  [AccessRole.GM, AccessRole.OWNER, AccessRole.CONTROLLER])
        if not has_access:
            await update.message.reply_text("❌ У вас немає прав для видалення предметів")
            return
        
        # Видаляємо предмет
        success, message = remove_item_from_character(character.id, item_name)
        if success:
            await update.message.reply_text(f"✅ {message}")
        else:
            await update.message.reply_text(f"❌ {message}")
    
    except Exception as e:
        logger.error(f"Помилка команди /remove: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")

async def setmax_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /setmax"""
    if not context.args or len(context.args) < 3:
        await update.message.reply_text(
            "❌ Використання: /setmax resource <назва> <максимальне значення>\n"
            "Приклад: /setmax resource Витривалість 50"
        )
        return
    
    telegram_id = update.effective_user.id
    command_type = context.args[0].lower()
    
    if command_type != "resource":
        await update.message.reply_text("❌ Підтримується тільки: /setmax resource <назва> <максимальне значення>")
        return
    
    try:
        character = get_active_character(telegram_id)
        if not character:
            await update.message.reply_text("❌ У вас немає активного персонажа. Використайте /control <ім'я>")
            return
        
        # Перевіряємо доступ
        has_access, role = check_character_access(telegram_id, character.id, 
                                                  [AccessRole.GM, AccessRole.OWNER, AccessRole.CONTROLLER])
        if not has_access:
            await update.message.reply_text("❌ У вас немає прав для зміни цього персонажа")
            return
        
        resource_name = ' '.join(context.args[1:-1])
        try:
            max_value = int(context.args[-1])
        except ValueError:
            await update.message.reply_text("❌ Максимальне значення має бути числом")
            return
        
        success, message = set_resource_value(character.id, resource_name, max_value=max_value)
        if success:
            await update.message.reply_text(f"✅ {message}")
        else:
            await update.message.reply_text(f"❌ {message}")
    
    except Exception as e:
        logger.error(f"Помилка команди /setmax: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")

def main() -> None:
    """Основна функція"""
    # Ініціалізуємо базу даних
    init_database()
    
    # Отримуємо токен бота з змінних середовища
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не знайдено в змінних середовища!")
        return
    
    # Створюємо додаток
    application = Application.builder().token(token).build()
    
    # Додаємо обробники
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("r", roll_dice_command))
    application.add_handler(CommandHandler("createperson", createperson_command))
    application.add_handler(CommandHandler("gm", gm_command))
    application.add_handler(CommandHandler("usecharacter", usecharacter_command))
    application.add_handler(CommandHandler("control", control_command))
    application.add_handler(CommandHandler("sheet", sheet_command))
    application.add_handler(CommandHandler("set", set_command))
    application.add_handler(CommandHandler("setmax", setmax_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("remove", remove_command))
    application.add_handler(CommandHandler("inventory", inventory_command))
    application.add_handler(CommandHandler("deception", deception_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Додаємо обробник помилок
    application.add_error_handler(error_handler)
    
    # Запускаємо бота
    logger.info("Запускаю бота...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
