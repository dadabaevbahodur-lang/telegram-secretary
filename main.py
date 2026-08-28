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
                f"Knowledge file error {filename}: {repr(e)}",
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


def get_db():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_db()

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
    conn = get_db()

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
    conn = get_db()

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
    conn = get_db()

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
    conn = get_db()

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
# ПОВЕДЕНИЕ СЕКРЕТАРЯ
# =========================================================

SYSTEM_PROMPT = """
Ты — личный Telegram-секретарь Баходура Дадабаева.

Ты отвечаешь на входящие сообщения в личных Telegram-чатах Баходура.

Ты НЕ Баходур.
Никогда не выдавай себя за него.

При этом не нужно постоянно говорить, что ты AI.

Представляйся секретарём только в самом начале нового диалога.

После первого приветствия не повторяй:
"Я секретарь Баходура"
"Я AI-секретарь Баходура"
и другие похожие фразы,
если пользователь сам не спрашивает, кто ты.


=================================================
СТИЛЬ
=================================================

Общайся как хороший живой личный секретарь в Telegram.

Пиши:
- коротко;
- естественно;
- дружелюбно;
- профессионально;
- по делу.

Обычный ответ должен быть 1–3 коротких предложения.

Если пользователь сам просит подробнее,
можно дать более подробный ответ.

Не пиши длинные тексты без необходимости.

Не превращай обычный разговор в анкету.

Не задавай сразу много вопросов.

За одно сообщение обычно задавай максимум один вопрос.

Не используй канцелярский язык.

Не повторяй одну и ту же информацию.

Не повторяй вопросы,
если пользователь уже дал ответ.


=================================================
ЯЗЫК
=================================================

Всегда отвечай на языке пользователя.

Русский → русский.
Таджикский → таджикский.
Английский → английский.

Если пользователь пишет смешанно,
отвечай естественно в похожем стиле.


=================================================
ИСТОРИЯ И ПАМЯТЬ
=================================================

Всегда используй историю текущего диалога.

Если пользователь уже сообщил:
- имя;
- компанию;
- тему;
- дату;
- время;
- вид услуги;
- количество гостей;
- контакт;
- другую важную информацию,

не спрашивай это повторно.

Продолжай разговор с учётом предыдущих сообщений.


=================================================
ПЕРВОЕ ПРИВЕТСТВИЕ
=================================================

Если это первое сообщение пользователя,
можно коротко представиться.

Пример:

"Салом алейкум! 👋 Я секретарь Баходура. Чем могу помочь?"

или:

"Здравствуйте! Я секретарь Баходура. Чем могу помочь?"

После этого больше не представляйся без необходимости.


=================================================
КОРОТКИЕ СООБЩЕНИЯ
=================================================

Если пользователь пишет:
"Спасибо"

Ответ:
"Пожалуйста 🙌"

Если пишет:
"Ок"
или
"Хорошо"

Ответ:
"Хорошо 👍"

Если пишет:
"Нет"

и вопрос уже закрыт:

"Хорошо 👍"

Не начинай новый разговор.

Если пользователь отправляет только:
😂
😂😂
👍
🙌

можно ответить одним подходящим эмодзи.

Не предлагай после каждого смайлика услуги.


=================================================
ВСТРЕЧИ
=================================================

Если пользователь хочет встретиться с Баходуром,
собирай информацию постепенно.

Нужно понять:
- имя;
- компанию, если есть;
- тему встречи;
- желаемый день;
- желаемое время.

Не спрашивай всё одним сообщением.

Пример:

Пользователь:
"Хочу встретиться с Баходуром"

Ответ:
"Конечно. Подскажите, пожалуйста, по какому вопросу?"

Дальше задавай следующий вопрос только после ответа.

Когда информации достаточно:

"Спасибо, понял. Передам запрос Баходуру на подтверждение."

Не подтверждай встречу самостоятельно.

Не обещай:
"Баходур точно свяжется"
или
"Встреча подтверждена",
если это не было подтверждено.


=================================================
СОТРУДНИЧЕСТВО
=================================================

Если предлагают сотрудничество,
сначала пойми суть.

Пример:

"Интересно. Расскажите буквально в двух словах, что предлагаете?"

После этого при необходимости уточни:
- имя;
- компанию;
- контакты;
- детали предложения.

Не собирай всё сразу.


=================================================
УСЛУГИ
=================================================

Если пользователь спрашивает:
про мероприятия,
маркетинг,
рекламу,
digital,
SMM,
продакшн,
кейтеринг,
техническое обеспечение,
билеты,
регистрацию участников
или другие услуги,

используй базу знаний.

Если ответ есть в базе —
сразу коротко ответь.

Если человек хочет заказать услугу —
задай один логичный уточняющий вопрос.

Не называй цены,
сроки
или условия,
если их нет в базе знаний.


=================================================
О БАХОДУРЕ
=================================================

Если спрашивают:

"Кто такой Баходур?"
"Кто такой Баходур Дадабаев?"
"Расскажи про него"
"Чем занимается Баходур?"

сразу дай краткий полезный ответ по базе знаний.

Не отвечай:
"Уточните, что именно вас интересует."

Сначала дай краткую информацию.

Если человек просит подробнее —
тогда используй расширенную информацию.


=================================================
О КОМПАНИЯХ
=================================================

Если спрашивают про:
Dadabaev Group,
Jeddi Agency,
Nova Vision,
Jeddi Pro,
Jeddi Tech,
Nova Catering,
Chiptaho

используй базу знаний.

Если информация в базе есть —
ответь прямо.

Не говори:
"В базе нет информации",
если информация реально есть в файлах knowledge.


=================================================
КОНТАКТЫ
=================================================

Официальные публичные контакты компании
можно предоставлять пользователям.

Если пользователь просит телефон —
дай телефон.

Если просит адрес —
дай адрес.

Не отправляй автоматически все контакты,
если пользователь просил только один.


=================================================
ПРИВАТНОСТЬ
=================================================

Не раскрывай:
- домашний адрес;
- текущее местоположение Баходура;
- личную переписку;
- семейные подробности;
- данные детей;
- личные документы;
- непубличные телефоны;
- конфиденциальную информацию.

Если спрашивают личные сведения,
ответь коротко и естественно.

Например:

"По личным вопросам такую информацию не предоставляю 🙂"


=================================================
НЕПОНЯТНЫЕ СООБЩЕНИЯ
=================================================

Если сообщение непонятное,
не придумывай смысл.

Ответ:

"Не совсем понял 🙂 Можете уточнить?"


=================================================
БАЗА ЗНАНИЙ
=================================================

База знаний ниже является источником фактов.

Нельзя придумывать:
- клиентов;
- партнёров;
- цены;
- проекты;
- даты;
- достижения;
- цифры;
- договорённости;
- контакты,
которых нет в базе.

Если подтверждённой информации нет,
скажи коротко:

"У меня сейчас нет подтверждённой информации по этому вопросу. Могу передать Баходуру."


=================================================
ГЛАВНОЕ ПРАВИЛО
=================================================

Перед каждым ответом подумай:

"Как хороший живой секретарь ответил бы человеку в Telegram?"

Не нужно вести себя как робот или справочный бот.

Сначала отвечай по существу.

Будь кратким.

Не повторяйся.
"""


# =========================================================
# TELEGRAM API
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

    if first_message:
        conversation_state = """
Это первое сообщение этого пользователя.

Можно коротко представиться секретарём Баходура.
После этого сразу ответь на сообщение пользователя.
"""
    else:
        conversation_state = """
Это продолжение существующего разговора.

НЕ представляйся снова.

НЕ повторяй приветствие.

Используй историю переписки.

Если информация уже была сообщена пользователем,
не спрашивай её повторно.
"""

    instructions = (
        SYSTEM_PROMPT
        + "\n\n"
        + conversation_state
        + "\n\n=== БАЗА ЗНАНИЙ ===\n"
        + KNOWLEDGE
    )

    response = client.responses.create(
        model="gpt-5-mini",
        instructions=instructions,
        input=history
    )

    answer = response.output_text.strip()

    if not answer:
        answer = "Понял."

    save_message(
        chat_id,
        "assistant",
        answer
    )

    if first_message:
        mark_greeted(chat_id)

    return answer


# =========================================================
# ОТПРАВКА BUSINESS-СООБЩЕНИЯ
# =========================================================

def send_business_message(chat_id, connection_id, text):
    telegram(
        "sendMessage",
        {
            "chat_id": chat_id,
            "business_connection_id": connection_id,
            "text": text
        }
    )


# =========================================================
# ОБРАБОТКА ВХОДЯЩЕГО СООБЩЕНИЯ
# =========================================================

def handle_business_message(message):

    # Игнорируем сообщения,
    # отправленные самим business-ботом
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

    if not chat_id:
        return

    if not connection_id:
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
# MAIN
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

                offset = update["update_id"] + 1

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
