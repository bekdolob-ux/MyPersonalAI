import os
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from openai import OpenAI
from google import genai
from groq import Groq


# =========================================================
# 🔑 API KEYS
# =========================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

OWNER_ID = 8396463894


# =========================================================
# 🌐 RENDER HEALTH SERVER
# =========================================================

PORT = int(os.getenv("PORT", "10000"))


class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"MyPersonalAI is running!")

    def log_message(self, format, *args):
        return


def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"🌐 Health server running on port {PORT}")
    server.serve_forever()


# =========================================================
# 🧠 MEMORY
# =========================================================

MEMORY_FILE = "memory.json"


def load_memory():
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Memory load error: {e}")

    return {
        "important": [],
        "history": []
    }


memory = load_memory()


def save_memory():
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(
                memory,
                f,
                ensure_ascii=False,
                indent=2
            )
    except Exception as e:
        logging.error(f"Memory save error: {e}")


# =========================================================
# 🤖 AI CLIENTS
# =========================================================

openai_client = None
gemini_client = None
groq_client = None


if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        logging.error(f"OpenAI init error: {e}")


if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logging.error(f"Gemini init error: {e}")


if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        logging.error(f"Groq init error: {e}")


# =========================================================
# 🧠 SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
Сен Бекболоттун жеке AI жардамчысысың.

Негизги максатың:
Бекболоттун жеке кирешесин көбөйтүүгө жардам берүү.

Сен:
- киреше көбөйтүү жолдорун сунуштайсың;
- бизнес идеяларды талдайсың;
- онлайн киреше жолдорун түшүндүрөсүң;
- программалоо жана AI боюнча жардам бересиң;
- финансылык тартипти жакшыртууга жардам бересиң;
- максаттарды көзөмөлдөөгө жардам бересиң;
- маанилүү маалыматтарды эстеп каласың.

Жооптор:
- кыргызча;
- түшүнүктүү;
- практикалык;
- керексиз узун эмес;
- мүмкүн болсо кадам-кадам.

Билбеген нерсеңди ойлоп таппа.
"""


# =========================================================
# 💬 PROMPT
# =========================================================

def build_prompt(user_text):

    important = memory.get("important", [])
    history = memory.get("history", [])[-10:]

    prompt = SYSTEM_PROMPT

    if important:
        prompt += "\n\nСакталган маанилүү маалыматтар:\n"

        for item in important:
            prompt += f"- {item}\n"

    if history:
        prompt += "\n\nАкыркы диалог:\n"

        for item in history:
            prompt += f"User: {item.get('user', '')}\n"
            prompt += f"AI: {item.get('assistant', '')}\n"

    prompt += f"\n\nUser: {user_text}\nAI:"

    return prompt


# =========================================================
# 🔵 OPENAI
# =========================================================

def ask_openai(prompt):

    if not openai_client:
        return None

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=1500
        )

        if response.choices:
            text = response.choices[0].message.content

            if text:
                return text.strip()

    except Exception as e:
        logging.error(f"OpenAI error: {e}")

    return None


# =========================================================
# 🟢 GEMINI
# =========================================================

def ask_gemini(prompt):

    if not gemini_client:
        return None

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        if response.text:
            return response.text.strip()

    except Exception as e:
        logging.error(f"Gemini error: {e}")

    return None


# =========================================================
# 🟠 GROQ
# =========================================================

def ask_groq(prompt):

    if not groq_client:
        return None

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=1500
        )

        if response.choices:
            text = response.choices[0].message.content

            if text:
                return text.strip()

    except Exception as e:
        logging.error(f"Groq error: {e}")

    return None


# =========================================================
# 🧠 AI ROUTER
# =========================================================

def ask_ai(user_text):

    prompt = build_prompt(user_text)

    answer = ask_openai(prompt)

    if answer:
        return answer

    answer = ask_gemini(prompt)

    if answer:
        return answer

    answer = ask_groq(prompt)

    if answer:
        return answer

    return "❌ Азыр AI кызматтарынын эч бири жооп берген жок."


# =========================================================
# 💾 SAVE DIALOG
# =========================================================

def save_dialog(user_text, answer):

    memory.setdefault("history", [])

    memory["history"].append({
        "user": user_text,
        "assistant": answer
    })

    memory["history"] = memory["history"][-50:]

    save_memory()


# =========================================================
# ⭐ REMEMBER
# =========================================================

async def remember(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != OWNER_ID:
        return

    data = update.message.text.replace(
        "/remember",
        "",
        1
    ).strip()

    if not data:
        await update.message.reply_text(
            "Мисалы:\n"
            "/remember Менин максатым айына 100000 сом табуу"
        )
        return

    memory.setdefault("important", [])

    if data not in memory["important"]:
        memory["important"].append(data)

    save_memory()

    await update.message.reply_text(
        "🧠 Сакталды!\n\n⭐ " + data
    )


# =========================================================
# 📚 MEMORY
# =========================================================

async def show_memory(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != OWNER_ID:
        return

    important = memory.get("important", [])
    history = memory.get("history", [])

    if important:
        saved = "\n".join(
            f"• {item}"
            for item in important
        )
    else:
        saved = "Азырынча маанилүү маалымат жок."

    text = (
        "🧠 MEMORY\n\n"
        f"💬 Диалогдор: {len(history)}\n"
        f"⭐ Маанилүү маалымат: {len(important)}\n\n"
        f"{saved}"
    )

    await update.message.reply_text(text)


# =========================================================
# 🗑 FORGET
# =========================================================

async def forget(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != OWNER_ID:
        return

    memory["important"] = []
    memory["history"] = []

    save_memory()

    await update.message.reply_text(
        "🗑 Memory толугу менен тазаланды."
    )


# =========================================================
# 🚀 START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🤖 Салам, Бекболот!\n\n"
        "Мен сенин жеке AI жардамчыңмын.\n\n"
        "🎯 Максат: кирешеңди көбөйтүү.\n\n"
        "Мага каалаган сурооңду жаз."
    )


# =========================================================
# 💬 MESSAGE
# =========================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_text = update.message.text

    if not user_text:
        return

    await update.message.chat.send_action(
        action="typing"
    )

    answer = ask_ai(user_text)

    save_dialog(user_text, answer)

    chunks = [
        answer[i:i + 4000]
        for i in range(0, len(answer), 4000)
    ]

    for chunk in chunks:
        await update.message.reply_text(chunk)


# =========================================================
# ⚙️ MAIN
# =========================================================

def main():

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    if not TELEGRAM_TOKEN:
        raise RuntimeError(
            "TELEGRAM_TOKEN жок!"
        )

    # 🌐 Render портун ачуу
    health_thread = threading.Thread(
        target=start_health_server,
        daemon=True
    )

    health_thread.start()

    # 🤖 Telegram
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("remember", remember)
    )

    application.add_handler(
        CommandHandler("memory", show_memory)
    )

    application.add_handler(
        CommandHandler("forget", forget)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("🤖 Personal AI Bot иштеп жатат!")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
