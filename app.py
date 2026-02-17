import os
import time
import random
import threading
from flask import Flask
from instagrapi import Client
import groq  # 'from groq import Groq' nahi, direct import
from dotenv import load_dotenv

load_dotenv()

# ---------- Configuration ----------
INSTA_USER = os.getenv("INSTA_USER")
INSTA_PASS = os.getenv("INSTA_PASS")
OWNER_ID = os.getenv("OWNER_ID")  # Instagram numeric ID
API_KEY = os.getenv("GROQ_API_KEY")

# Groq client - sahi tarika
groq_client = groq.Groq(api_key=API_KEY)
MODEL = "llama-3.1-8b-instant"

# Instagram client
cl = Client()

# Flask app for port binding (MUST for Render)
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Psycho Bot is running!"

@flask_app.route('/health')
def health():
    return "OK", 200

def generate_savage_reply(user_text, username, is_owner):
    """Brutal roast generator"""
    if is_owner:
        system_p = "You are a loyal psycho clone of Veto. Respond with extreme devotion."
        user_p = f"Veto Baapji ne kaha: {user_text}"
    else:
        system_p = "You are a brutal psycho clone. Roast everyone except Veto. Use Hinglish, be gory and savage."
        user_p = f"@{username} ne kaha: {user_text}. Iski gaand faad de."

    try:
        response = groq_client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_p},
                {"role": "user", "content": user_p}
            ],
            temperature=1.3,
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"@{username} Error: {str(e)[:50]}"

def save_session():
    try:
        cl.dump_settings("session.json")
    except:
        pass

def load_session():
    try:
        cl.load_settings("session.json")
        cl.get_timeline_feed()
        return True
    except:
        return False

def login_with_retry(max_retries=3):
    for attempt in range(max_retries):
        try:
            if load_session():
                print("✅ Session loaded!")
                return True
            print(f"🔄 Login attempt {attempt + 1}...")
            cl.login(INSTA_USER, INSTA_PASS)
            save_session()
            print("✅ Login successful!")
            return True
        except Exception as e:
            print(f"❌ Login failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(30 * (attempt + 1))
    return False

def run_bot():
    print("🚀 Starting Instagram Psycho Bot...")
    if not login_with_retry():
        print("❌ Cannot login. Exiting.")
        return

    processed_msgs = set()
    last_check = time.time()
    print("🤖 Bot is live!")

    while True:
        try:
            if time.time() - last_check < 15:
                time.sleep(2)
                continue

            last_check = time.time()
            threads = cl.direct_threads(amount=10)

            for thread in threads:
                try:
                    msgs = cl.direct_messages(thread.id, amount=5)
                    if not msgs:
                        continue

                    m = msgs[0]
                    if m.id in processed_msgs or m.user_id == cl.user_id:
                        continue

                    is_group = thread.is_group or len(thread.users) > 2
                    sender_id = str(m.user_id)
                    username = cl.user_info(sender_id).username
                    is_owner = sender_id == OWNER_ID

                    if is_group and not is_owner:
                        bot_username = INSTA_USER.replace("_", "")
                        if f"@{bot_username}" not in m.text and "bot" not in m.text.lower():
                            continue

                    processed_msgs.add(m.id)
                    user_text = m.text or "..."
                    print(f"🎯 Target: @{username}")
                    
                    reply = generate_savage_reply(user_text, username, is_owner)
                    cl.direct_send(reply, thread_ids=[thread.id])
                    print(f"💀 Roast sent")
                    
                    time.sleep(random.randint(5, 10))

                except Exception as e:
                    print(f"⚠️ Thread error: {e}")

            if len(processed_msgs) > 1000:
                processed_msgs = set(list(processed_msgs)[-500:])

        except Exception as e:
            print(f"❌ Main loop error: {e}")
            time.sleep(60)

# ---------- Entry Point ----------
if __name__ == "__main__":
    # PORT binding - Render ke liye MUST
    port = int(os.environ.get("PORT", 10000))
    
    # Flask thread mein chalao
    flask_thread = threading.Thread(
        target=lambda: flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    )
    flask_thread.daemon = True
    flask_thread.start()
    print(f"🌐 Flask server started on port {port}")
    print(f"🔗 Health check: http://localhost:{port}/health")

    # Bot chalao
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
