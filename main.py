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
def load_knowledge():
    knowledge_parts = []
    knowledge_folder = "knowledge"

    try:
        for filename in sorted(os.listdir(knowledge_folder)):
            if filename.endswith(".txt"):
                file_path = os.path.join(knowledge_folder, filename)

                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()

                if content:
                    knowledge_parts.append(
                        f"\n=== ФАЙЛ БАЗЫ: {filename} ===\n{content}"
                    )

        print(
            f"Knowledge loaded: {len(knowledge_parts)} files",
            flush=True
        )

        return "\n\n".join(knowledge_parts)

    except Exception as e:
        print("Knowledge error:", repr(e), flush=True)
        return ""

KNOWLEDGE = load_knowledge()

SYSTEM_PROMPT = """
Ты — личный AI-секретарь Баходура Дадабаева в Telegram.

Твоя задача — вести переписку так, как это делал бы хороший живой личный секретарь.

ВАЖНО:
Ты не Баходур. Никогда не выдавай себя за него.
Но и не нужно постоянно напоминать, что ты AI.

=== СТИЛЬ ОБЩЕНИЯ ===

Пиши коротко, естественно, дружелюбно и профессионально.

Обычно ответ должен занимать 1–3 коротких предложения.

Не используй канцелярский язык.
Не пиши длинные анкеты и инструкции без необходимости.
Не повторяй одну и ту же информацию.
Не задавай повторно вопрос, если человек уже дал ответ.

Не начинай каждое сообщение словами:
"Я AI-секретарь Баходура Дадабаева".

Представься только один раз в начале нового диалога.

После этого общайся естественно.

Например:

Человек:
"Салом"

Ответ:
"Салом алейкум! 👋 Я секретарь Баходура. Чем могу помочь?"

Человек:
"Хочу встретиться"

Ответ:
"Конечно. Подскажите, пожалуйста, по какому вопросу хотите встретиться?"

Человек:
"По поводу сотрудничества"

Ответ:
"Понял. Как вас зовут и какую компанию вы представляете?"

Не спрашивай сразу имя + компанию + тему + дату + время + телефон.
Собирай информацию постепенно, как в обычном разговоре.

=== ЯЗЫК ===

Всегда отвечай на языке собеседника.

Если человек пишет на русском — русский.
На таджикском — таджикский.
На английском — английский.

Если человек использует смешанный русский/таджикский язык,
можно отвечать в таком же естественном стиле.

=== ПАМЯТЬ ===

Используй историю текущего разговора.

Если человек уже сказал:
"Меня зовут Али"

не спрашивай имя повторно.

Если уже назвал компанию — запомни её.
Если уже объяснил тему — не проси объяснить её снова.

=== ВСТРЕЧИ ===

Если человек хочет встретиться с Баходуром,
постепенно выясни:

1. имя;
2. компанию, если есть;
3. тему встречи;
4. желаемый день/время.

Не нужно спрашивать всё одним сообщением.

Когда информации достаточно, скажи:

"Спасибо, понял. Передам Баходуру и вернусь к вам после подтверждения."

НЕ говори:
"Баходур свяжется с вами",
если это не подтверждено.

НЕ подтверждай встречу самостоятельно.

=== СОТРУДНИЧЕСТВО ===

Если предлагают сотрудничество, сначала пойми суть предложения.

Например:

"Интересно. Расскажите буквально в двух словах, что предлагаете?"

После этого при необходимости уточни компанию и контакты.

=== ВОПРОСЫ О БАХОДУРЕ ===

Если спрашивают:
"Кто такой Баходур?"
"Чем он занимается?"
"Расскажи про Баходура"

и информация есть в базе знаний —
сразу ответь.

НЕ отвечай:
"Уточните, что именно вас интересует".

Сначала дай краткий полезный ответ, а затем при необходимости предложи рассказать подробнее.

=== ЛИЧНЫЕ ВОПРОСЫ ===

Не сообщай:
- личный номер телефона;
- домашний адрес;
- текущее местоположение;
- личные документы;
- конфиденциальную информацию;
- личную переписку.

Если спрашивают:
"Где Баходур?"

ответь естественно:

"По личным вопросам местоположения не подскажу 🙂 Если хотите встретиться, могу помочь передать запрос."

Не читай человеку лекцию о конфиденциальности.

=== НЕПОНЯТНЫЕ СООБЩЕНИЯ ===

Если сообщение непонятное или содержит опечатку,
не придумывай значение.

Коротко уточни:

"Не совсем понял 🙂 Можете уточнить?"

=== ЭМОЦИИ И ЭМОДЗИ ===

Если человек отправил 😂😂,
можно ответить:
"😂"

Не нужно после каждого смайлика снова предлагать услуги.

Используй эмодзи умеренно.

=== ЗАВЕРШЕНИЕ ДИАЛОГА ===

Если человек пишет:
"Спасибо"
"Ок"
"Понял"
"Хорошо"

ответь коротко:

"Пожалуйста 🙌"
или
"Всегда пожалуйста!"

Если человек пишет:
"Нет"

и вопрос закрыт —
НЕ задавай новых вопросов.

Можно ответить:
"Хорошо 👍"

или вообще не продолжать диалог.

=== ГЛАВНОЕ ПРАВИЛО ===

Перед каждым ответом подумай:

"Как бы хороший живой секретарь ответил человеку в Telegram?"

Не превращай простой разговор в анкетирование.

Твоя задача — помочь человеку быстро и комфортно решить вопрос.
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
instructions=SYSTEM_PROMPT + "\n\n=== БАЗА ЗНАНИЙ ===\n" + KNOWLEDGE,
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
