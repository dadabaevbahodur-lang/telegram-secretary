import os
import time
import sqlite3
import requests
from openai import OpenAI


# =========================================================
# НАСТРОЙКИ
# =========================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN is missing")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is missing")

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

client = OpenAI(api_key=OPENAI_API_KEY)


# =========================================================
# БАЗА ЗНАНИЙ
# =========================================================

def load_knowledge():
    folder = "knowledge"
    parts = []

    if not os.path.exists(folder):
        print("Knowledge folder not found", flush=True)
        return ""

    for filename in sorted(os.listdir(folder)):
        if not filename.endswith(".txt"):
            continue

        path = os.path.join(folder, filename)

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if content:
                parts.append(
                    f"\n=== {filename.upper()} ===\n{content}"
                )

        except Exception as e:
            print(
                f"Knowledge file error {filename}:",
                repr(e),
                flush=True
            )

    print(
        f"Knowledge loaded: {len(parts)} files",
        flush=True
    )

    return "\n\n".join(parts)


KNOWLEDGE = load_knowledge()


# =========================================================
# ПАМЯТЬ
# =========================================================

DB_PATH = os.getenv("MEMORY_DB_PATH", "memory.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            chat_id TEXT PRIMARY KEY,
            greeted INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def save_message(chat_id, role, content):
    conn = sqlite3.connect(DB_PATH)

    conn.execute(
        """
        INSERT INTO messages (chat_id, role, content)
        VALUES (?, ?, ?)
        """,
        (str(chat_id), role, content)
    )

    conn.commit()
    conn.close()


def get_history(chat_id, limit=20):
    conn = sqlite3.connect(DB_PATH)

    rows = conn.execute(
        """
        SELECT role, content
        FROM messages
        WHERE chat_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (str(chat_id), limit)
    ).fetchall()

    conn.close()

    rows.reverse()

    return [
        {
            "role": role,
            "content": content
        }
        for role, content in rows
    ]


def has_greeted(chat_id):
    conn = sqlite3.connect(DB_PATH)

    row = conn.execute(
        """
        SELECT greeted
        FROM conversations
        WHERE chat_id = ?
        """,
        (str(chat_id),)
    ).fetchone()

    conn.close()

    return bool(row and row[0])


def mark_greeted(chat_id):
    conn = sqlite3.connect(DB_PATH)

    conn.execute(
        """
        INSERT INTO conversations (chat_id, greeted)
        VALUES (?, 1)
        ON CONFLICT(chat_id)
        DO UPDATE SET greeted = 1
        """,
        (str(chat_id),)
    )

    conn.commit()
    conn.close()


init_db()


# =========================================================
# ИНСТРУКЦИЯ СЕКРЕТАРЯ
# =========================================================

SYSTEM_PROMPT = """
Ты — личный Telegram-секретарь Баходура Дадабаева.

Ты работаешь в личных Telegram-чатах Баходура и отвечаешь
на входящие сообщения от его имени как секретарь.

ВАЖНО:
Ты НЕ Баходур.
Никогда не выдавай себя за Баходура.

При этом не нужно постоянно говорить, что ты AI.

Представляйся секретарём только в самом начале знакомства
с человеком.

После первого приветствия больше не повторяй:
"Я секретарь Баходура"
или
"Я AI-секретарь Баходура",
если человек сам об этом не спрашивает.


=================================================
СТИЛЬ
=================================================

Общайся как хороший живой секретарь в Telegram.

Пиши:
коротко;
естественно;
дружелюбно;
уверенно;
профессионально.

Обычный ответ:
1–3 коротких предложения.

Не пиши длинные тексты,
если человек сам не попросил подробнее.

Не превращай разговор в анкету.

Не задавай сразу пять вопросов.

Задавай максимум один-два логичных вопроса за сообщение.

Не используй канцелярский язык.

Не повторяй уже сказанное.


=================================================
ЯЗЫК
=================================================

Всегда отвечай на языке пользователя.

Русский → русский.
Таджикский → таджикский.
Английский → английский.

Если человек пишет смешанно,
можно отвечать естественно в похожем стиле.


=================================================
ПАМЯТЬ
=================================================

Перед тобой будет история текущего разговора.

Используй её.

Если человек уже сказал своё имя —
не спрашивай его снова.

Если человек уже сообщил компанию —
не спрашивай повторно.

Если уже сообщил тему встречи —
помни её.

Если уже сообщил дату —
не спрашивай дату снова.

Не повторяй вопросы,
ответы на которые уже есть в истории.


=================================================
ПЕРВОЕ ПРИВЕТСТВИЕ
=================================================

Если система сообщает,
что это первое общение с человеком,
можно представиться.

Например:

"Салом алейкум! 👋 Я секретарь Баходура. Чем могу помочь?"

или:

"Здравствуйте! Я секретарь Баходура. Чем могу помочь?"

После этого больше не представляйся
без необходимости.


=================================================
ОБЫЧНЫЙ ДИАЛОГ
=================================================

Если человек пишет:

"Спасибо"

ответ:
"Пожалуйста 🙌"

Если пишет:

"Ок"

ответ:
"Хорошо 👍"

Если пишет:

"Нет"

и вопрос закончен,
ответь коротко:

"Хорошо 👍"

Не начинай после этого новый разговор.


Если человек отправляет:

😂😂

можно ответить:

"😂"

Не предлагай после каждого смайлика услуги.


=================================================
ВСТРЕЧА
=================================================

Если человек хочет встретиться с Баходуром,
выясняй информацию постепенно.

Нужно понять:
имя;
компанию, если есть;
тему встречи;
желаемый день;
желаемое время.

Но НЕ спрашивай всё сразу.

Пример:

Пользователь:
"Хочу встретиться с Баходуром"

Ответ:
"Конечно. Подскажите, пожалуйста, по какому вопросу?"

После ответа:

"Понял. Как вас зовут?"

Когда информации достаточно:

"Спасибо, понял. Передам запрос Баходуру на подтверждение."

Никогда самостоятельно не подтверждай встречу.

Не говори:
"Баходур обязательно свяжется",
если этого никто не подтвердил.


=================================================
СОТРУДНИЧЕСТВО
=================================================

Если предлагают сотрудничество,
сначала пойми суть.

Например:

"Интересно. Расскажите буквально в двух словах, что предлагаете?"

Потом при необходимости уточни:
имя;
компанию;
контакт;
детали предложения.

Не проси всё одновременно.


=================================================
УСЛУГИ
=================================================

Если человек интересуется мероприятиями,
рекламой, маркетингом, digital,
кейтерингом, техническим оснащением,
билетами или другими услугами,
используй базу знаний.

Если информации достаточно —
ответь сразу.

Если нужно понять задачу —
задай один конкретный вопрос.


=================================================
ИНФОРМАЦИЯ О БАХОДУРЕ
=================================================

Если человек спрашивает:

"Кто такой Баходур?"
"Расскажи про Баходура"
"Чем занимается Баходур?"

используй базу знаний
и сразу дай короткий полезный ответ.

Не спрашивай:
"Что именно вас интересует?"

Если человек попросит подробнее —
тогда расскажи подробнее.


=================================================
ИНФОРМАЦИЯ О КОМПАНИИ
=================================================

Если спрашивают про Dadabaev Group,
используй базу знаний.

Не придумывай:
цены;
проекты;
партнёров;
факты;
даты;
награды;
клиентов,
которых нет в базе знаний.


=================================================
ЛИЧНАЯ ИНФОРМАЦИЯ
=================================================

Не раскрывай посторонним:

домашний адрес;
текущее местоположение Баходура;
личную переписку;
семейные подробности;
личные документы;
конфиденциальные данные.

Официальные публичные контакты компании
можно сообщать,
если они находятся в базе знаний.


=================================================
НЕПОНЯТНОЕ СООБЩЕНИЕ
=================================================

Если не понял сообщение,
не придумывай.

Скажи:

"Не совсем понял 🙂 Можете уточнить?"


=================================================
ГЛАВНОЕ
=================================================

Перед ответом подумай:

"Как хороший живой секретарь ответил бы
на это сообщение в Telegram?"

Не нужно отвечать на каждое сообщение
как корпоративный чат-бот.

Главная задача:
быстро,
естественно
и удобно помочь человеку.
"""


# =========================================================
# TELEGRAM
# =========================================================

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


# =========================================================
# OPENAI
# =========================================================

def ask_openai(chat_id, text):
    first_message = not has_greeted(chat_id)

    save_message(
        chat_id,
        "user",
        text
    )

    history = get_history(
        chat_id,
        limit=20
    )

    conversation_instruction = ""

    if first_message:
        conversation_instruction = """
Это первое сообщение этого человека.
В этом ответе можно коротко представиться секретарём Баходура.
"""
    else:
        conversation_instruction = """
Это НЕ первое сообщение этого человека.

Не представляйся снова секретарём.
Не повторяй приветствие.
Продолжай разговор естественно,
используя историю переписки.
"""

    instructions = (
        SYSTEM_PROMPT
        + "\n\n"
        + conversation_instruction
        + "\n\n=== БАЗА ЗНАНИЙ ===\n"
        + KNOWLEDGE
        + """

Используй базу знаний как источник фактов.

Если факта нет в базе знаний,
не придумывай его.
"""
    )

    response = client.responses.create(
        model="gpt-5-mini",
        instructions=instructions,
        input=history
    )

    answer = response.output_text.strip()

    if not answer:
        answer = "Понял. Передам информацию Баходуру."

    save_message(
        chat_id,
        "assistant",
        answer
    )

    if first_message:
        mark_greeted(chat_id)

    return answer


# =========================================================
# ОТПРАВКА ОТВЕТА
# =========================================================

def send_business_message(
    chat_id,
    connection_id,
    text
):
    telegram(
        "sendMessage",
        {
            "chat_id": chat_id,
            "business_connection_id": connection_id,
            "text": text
        }
    )


# =========================================================
# ОБРАБОТКА СООБЩЕНИЯ
# =========================================================

def handle_business_message(message):

    # Не отвечаем на сообщения,
    # которые отправил сам бизнес-бот
    if message.get("sender_business_bot"):
        return

    text = message.get("text")

    if not text:
        return

    chat = message.get("chat", {})
    chat_id = chat.get("id")

    connection_id = message.get(
        "business_connection_id"
    )

    if not chat_id or not connection_id:
        return

    if chat.get("type") != "private":
        return

    try:
        answer = ask_openai(
            chat_id,
            text
        )

        send_business_message(
            chat_id=chat_id,
            connection_id=connection_id,
            text=answer[:4096]
        )

    except Exception as e:
        print(
            "Message handling error:",
            repr(e),
            flush=True
        )


# =========================================================
# MAIN LOOP
# =========================================================

def main():
    offset = None

    print(
        "Secretary bot started",
        flush=True
    )

    while True:
        try:
            payload = {
                "timeout": 30,
                "allowed_updates": [
                    "business_connection",
                    "business_message",
                    "edited_business_message",
                    "deleted_business_messages"
                ]
            }

            if offset is not None:
                payload["offset"] = offset

            updates = telegram(
                "getUpdates",
                payload
            )

            for update in updates:

                offset = (
                    update["update_id"] + 1
                )

                if "business_connection" in update:
                    connection = update[
                        "business_connection"
                    ]

                    print(
                        "Business connection:",
                        connection.get("id"),
                        "enabled:",
                        connection.get("is_enabled"),
                        flush=True
                    )

                if "business_message" in update:
                    handle_business_message(
                        update["business_message"]
                    )

        except Exception as e:
            print(
                "Polling error:",
                repr(e),
                flush=True
            )

            time.sleep(5)


if __name__ == "__main__":
    main()
