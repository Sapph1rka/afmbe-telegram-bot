# AFMBE Telegram Bot

A simple Telegram bot that automatically replies to messages in a group.

## Features

- **Chat threads**: Automatically replies in the same chat thread where the message was posted
- **Commands**:
  - `/start` - Start using the bot
  - `/help` - Show help
  - `/status` - Bot status and chat info
  - `/ping` - Check that the bot is working
  - `/r` - Roll a die with modifiers
- **Dice rolling**: Supports complex formulas with multiplication, division, and parentheses (d20+5-2, d4*2, (d6*3)+5, etc.)
- **Critical values**: Automatically marks 1 (🔴 critical failure) and the maximum value (🟢 critical success)
- **Exploding d10 dice**: Special system for d10 with extra rolls and bonuses
- **Success levels**: Automatically determines the success level (1–7) based on the final result for d10 only
- **Async architecture**: Fully asynchronous code for efficient operation
- **Groups**: Works only in groups and supergroups

## Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd afmbe-telegram-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with the following structure:
```
TELEGRAM_BOT_TOKEN=your_actual_bot_token_here
DECEPTION_ALLOWED_IDS=123456789,987654321
```

- `TELEGRAM_BOT_TOKEN` — required bot token from @BotFather
- `DECEPTION_ALLOWED_IDS` — optional comma-separated Telegram user IDs allowed to use `/deception`

## Getting a bot token

1. Find @BotFather in Telegram
2. Send the `/newbot` command
3. Follow the instructions to create a bot
4. Copy the received token into the `.env` file

## Running

```bash
python bot.py
```

## Adding the bot to a group

1. Add the bot to a group as a regular member
2. The bot will automatically start replying to messages containing the word "Darova"

## Configuration

To change the bot's behavior, edit the `handle_message` function in `bot.py`.

## Logging

The bot logs all actions to the console. Check the logs to diagnose issues.

## Security

- Never commit the `.env` file to the repository
- Keep the bot token secret
- Add `.env` to `.gitignore`
