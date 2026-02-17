import os
import time
import random
import threading
import requests
from flask import Flask
from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()

# ---------- Configuration ----------
INSTA_USER = os.getenv("INSTA_USER")
OWNER_ID = os.getenv("OWNER_ID")
API_KEY = os.getenv("GROQ_API_KEY")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.1-8b-instant"

cl = Client()

# Flask app for port binding
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Psycho Bot is running!"

@flask_app.route('/health')
def health():
    return "OK", 200

def load_session():
    """Session ID se session load karo"""
    session_id = os.getenv("IG_SESSION_ID")
    if not session_id:
        print("❌ IG_SESSION_ID environment variable missing!")
        return False
    
    try:
        cl.login_by_sessionid(session_id)
        cl.dump_settings("session.json")
        print("✅ Session loaded from session ID!")
        return True
    except Exception as e:
        print(f"❌ Session load failed: {e}")
        return False

def generate_reply(user_text, username, is_owner):
    if is_owner:
        system_p = "You are a loyal psycho clone of Veto."
        user_p = f"Veto: {user_text}"
    else:
        system_p = "You are a brutal psycho clone. Roast in Hinglish."
        user_p = f"@{username} said: {user_text}"

    try:
        response = requests.post(
            GROQ_API_URL,
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system_p},
                    {"role": "user", "content": user_p}
                ],
                "temperature": 1.3
            },
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            timeout=20
        )
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"@{username} Error: {str(e)[:30]}"

def run_bot():
    print("🚀 Bot starting...")
    
    if not load_session():
        print("❌ Cannot load session. Exiting.")
        return

    processed = set()
    print("🤖 Bot is live!")

    while True:
        try:
            threads = cl.direct_threads(amount=5)
            for thread in threads:
                try:
                    msgs = cl.direct_messages(thread.id, amount=3)
                    if not msgs:
                        continue
                    
                    m = msgs[0]
                    if m.id in processed or m.user_id == cl.user_id:
                        continue
                    
                    username = cl.user_info(str(m.user_id)).username
                    processed.add(m.id)
                    
                    print(f"📩 @{username}")
                    reply = generate_reply(m.text or "", username, str(m.user_id) == OWNER_ID)
                    cl.direct_send(reply, thread_ids=[thread.id])
                    print(f"✅ Reply sent")
                    
                    time.sleep(random.randint(3, 6))
                    
                except Exception as e:
                    print(f"⚠️ {e}")
                    
            time.sleep(10)
            
        except Exception as e:
            print(f"❌ {e}")
            time.sleep(30)

if __name__ == "__main__":
    # Flask thread mein chalao
    port = int(os.environ.get("PORT", 10000))
    flask_thread = threading.Thread(
        target=lambda: flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    )
    flask_thread.daemon = True
    flask_thread.start()
    print(f"🌐 Flask server on port {port}")

    # Bot chalao
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped")
