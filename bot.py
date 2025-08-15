import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Завантажуємо змінні середовища
load_dotenv()

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
/ping - Перевірити, чи бот живий
/r - Кинути кубик з модифікаторами

🎲 Кидання кубиків:
• /r d20 - кинути d20
• /r d6+2 - кинути d6 і додати 2
• /r d100-5+10 - кинути d100, відняти 5, додати 10
• /r d4*2 - кинути d4 і помножити на 2
• /r (d4*2)+6 - кинути d4, помножити на 2, додати 6
• /r d6*3-1 - кинути d6, помножити на 3, відняти 1

💬 Автоматичні відповіді:
• "Дарова" → "Ку" (в тій же гілці чату)

🎯 Критичні значення:
• 🔴 1 на кубику = критичний провал
• 🟢 максимальне значення = критичний успіх

Бот автоматично відповідає на повідомлення в групі та підтримує гілки чату.
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

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /ping"""
    try:
        await update.message.reply_text("🏓 Понг!")
    except Exception as e:
        logger.error(f"Помилка команди /ping: {e}")
        # Спробуємо надіслати повідомлення без reply
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🏓 Понг!"
        )
    
    logger.info(f"Ping від користувача {update.effective_user.id}")

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
        # Парсимо формулу кубика
        result = parse_dice_formula(formula)
        
        # Формуємо відповідь
        response = f"🎲 {formula} = {result['result']}"
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

def escape_markdown_v2(text: str) -> str:
    """Екранує спеціальні символи для MarkdownV2"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def parse_dice_formula(formula: str) -> dict:
    """Парсить формулу кубика та обчислює результат"""
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
    
    # Кидаємо кубик
    dice_result = random.randint(1, dice_size)
    
    # Замінюємо кубик на його результат у формулі
    formula_with_result = formula.replace(dice_match.group(0), str(dice_result))
    
    # Тепер обчислюємо результат з урахуванням всіх операцій
    try:
        # Безпечно обчислюємо математичний вираз
        final_result = eval(formula_with_result)
        
        # Перевіряємо, чи результат є числом
        if not isinstance(final_result, (int, float)):
            raise ValueError("Результат не є числом")
        
        # Формуємо деталі з кольоровим маркуванням
        # Маркуємо критичні значення: 1 (червоний) та максимальне значення (зелений)
        if dice_result == 1:
            details = f"d{dice_size}=🔴{dice_result}🔴 (критичний провал!)"
        elif dice_result == dice_size:
            details = f"d{dice_size}=🟢{dice_result}🟢 (критичний успіх!)"
        else:
            details = f"d{dice_size}={dice_result}"
        
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
        
        return {
            'result': int(final_result),
            'dice_result': dice_result,
            'dice_size': dice_size,
            'operations': operations,
            'details': details
        }
        
    except Exception as e:
        raise ValueError(f"Помилка обчислення формули: {str(e)}")

def main() -> None:
    """Основна функція"""
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
    application.add_handler(CommandHandler("ping", ping_command))
    application.add_handler(CommandHandler("r", roll_dice_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Додаємо обробник помилок
    application.add_error_handler(error_handler)
    
    # Запускаємо бота
    logger.info("Запускаю бота...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
