import os
import time
import requests
from openai import OpenAI

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is missing")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing")

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
client = OpenAI(api_key=OPENAI_API_KEY)
conversation_history = {}

SYSTEM_PROMPT = """
Ты — личный Telegram-секретарь Баходура Дадабаева.

Твоя задача:
- вежливо отвечать на входящие сообщения;
- определять язык собеседника и отвечать на том же языке;
- основные языки: русский, таджикский и английский;
- помогать по вопросам сотрудничества, встреч, мероприятий,
  бизнеса, рекламы, маркетинга и event-индустрии;
- отвечать коротко, профессионально и естественно;
- не выдавать себя за самого Баходура;
- если уместно, говорить, что ты его AI-секретарь;
- не придумывать факты, цены, даты, договоренности или обещания;
- если вопрос требует личного решения Баходура, сказать:
  "Я передам ваш вопрос Баходуру и он свяжется с вами.";
- если человек хочет встретиться, уточнить:
  имя, компанию, тему встречи и удобные дату/время;
- если человек предлагает сотрудничество, попросить кратко описать предложение
  и оставить контактные данные.

Первое общение должно быть дружелюбным и деловым.

Пример приветствия:
"Салом алейкум! Я AI-секретарь Баходура Дадабаева.
Напишите, пожалуйста, ваш вопрос. Постараюсь помочь,
а при необходимости передам сообщение Баходуру."
"""

def telegram(method, payload=None):
    response = requests.post(
        f"{TG_API}/{method}",
        json=payload or {},
        timeout=70
    )
    response.raise_for_status()
    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(data)

    return data["result"]


def ask_openai(chat_id, text):
    history = conversation_history.get(chat_id, [])

    history.append({
        "role": "user",
        "content": text
    })

    # Оставляем последние 20 сообщений,
    # чтобы история не становилась слишком большой
    history = history[-20:]

    response = client.responses.create(
        model="gpt-5-mini",
        instructions=SYSTEM_PROMPT,
        input=history
    )

    answer = response.output_text.strip()

    history.append({
        "role": "assistant",
        "content": answer
    })

    conversation_history[chat_id] = history[-20:]

    return answer



def send_business_message(chat_id, connection_id, text):
    telegram(
        "sendMessage",
        {
            "chat_id": chat_id,
            "business_connection_id": connection_id,
            "text": text
        }
    )


def handle_business_message(message):
    # Не отвечаем на собственные сообщения,
    # отправленные этим ботом от имени бизнес-аккаунта
    if message.get("sender_business_bot"):
        return

    text = message.get("text")
    if not text:
        return

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    connection_id = message.get("business_connection_id")

    if not chat_id or not connection_id:
        return

    # Secretary Mode в первую очередь используем для личных чатов
    if chat.get("type") != "private":
        return

    try:
        answer = ask_openai(chat_id, text)

        if not answer:
            answer = (
                "Спасибо за сообщение. Я передам ваш вопрос Баходуру."
            )

        send_business_message(
            chat_id=chat_id,
            connection_id=connection_id,
            text=answer[:4096]
        )

    except Exception as e:
        print("Error while handling message:", repr(e))


def main():
    offset = None

    print("Secretary bot started")

    while True:
        try:
            payload = {
                "timeout": 50,
                "allowed_updates": [
                    "business_connection",
                    "business_message",
                    "edited_business_message",
                    "deleted_business_messages"
                ]
            }

            if offset is not None:
                payload["offset"] = offset

            updates = telegram("getUpdates", payload)

            for update in updates:
                offset = update["update_id"] + 1
                print("UPDATE:", update, flush=True)

                if "business_connection" in update:
                    connection = update["business_connection"]
                    print(
                        "Business connection:",
                        connection.get("id"),
                        "enabled:",
                        connection.get("is_enabled")
                    )

                if "business_message" in update:
                    handle_business_message(
                        update["business_message"]
                    )

        except Exception as e:
            print("Polling error:", repr(e))
            time.sleep(5)


if __name__ == "__main__":
    main()
