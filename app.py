import os
import time
import random
import threading
from flask import Flask
from instagrapi import Client
import groq  # Changed from 'from groq import Groq'
from dotenv import load_dotenv

load_dotenv()

# ---------- Configuration ----------
INSTA_USER = os.getenv("INSTA_USER")
INSTA_PASS = os.getenv("INSTA_PASS")
OWNER_ID = os.getenv("OWNER_ID")          # Instagram user ID (numeric) of Veto
API_KEY = os.getenv("GROQ_API_KEY")

# Groq client - updated initialization
groq_client = groq.Groq(api_key=API_KEY)
MODEL = "llama-3.1-8b-instant"

# Instagram client
cl = Client()

# Flask app for port binding (Render requirement)
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Psycho Bot is running!"

# ---------- Helper Functions ----------
def generate_savage_reply(user_text, username, is_owner):
    """Generate brutal roast based on SOUL.md personality."""
    if is_owner:
        system_p = "You are a loyal psycho clone of Veto. Respond with extreme devotion and brutality when talking to your owner."
        user_p = f"Veto Baapji ne kaha: {user_text}. Iska reply de ek loyal kutte ki tarah, lekin savage bhi."
    else:
        system_p = "You are a brutal psycho clone. Roast everyone except Veto. Use Hinglish, be gory and savage. No hesitation."
        user_p = f"@{username} ne kaha: {user_text}. Iski gaand faad de, gore gaali de, maa-behen ek kar de."

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
        return f"@{username} Teri MKC, Groq API ki gaand phat gayi! Error: {str(e)[:50]}"

def save_session():
    """Save session to file for reuse."""
    try:
        cl.dump_settings("session.json")
    except:
        pass

def load_session():
    """Load saved session if valid."""
    try:
        cl.load_settings("session.json")
        cl.get_timeline_feed()  # Test if session works
        return True
    except:
        return False

def login_with_retry(max_retries=3):
    """Login with retry logic and session reuse."""
    for attempt in range(max_retries):
        try:
            if load_session():
                print("✅ Session loaded successfully!")
                return True

            print(f"🔄 Login attempt {attempt + 1}/{max_retries}...")
            cl.login(INSTA_USER, INSTA_PASS)
            save_session()
            print("✅ Login successful!")
            return True
        except Exception as e:
            print(f"❌ Login failed: {e}")
            if attempt < max_retries - 1:
                wait = 30 * (attempt + 1)
                print(f"⏳ Waiting {wait} seconds...")
                time.sleep(wait)
            else:
                print("❌ All login attempts failed")
                return False

def run_bot():
    """Main bot loop – processes Instagram messages."""
    print("🚀 Starting Instagram Psycho Bot...")

    if not login_with_retry():
        print("❌ Cannot login. Bot will not run.")
        return

    processed_msgs = set()
    last_check = time.time()
    print("🤖 Bot is live! Listening for messages...")

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

                    m = msgs[0]  # most recent message
                    if m.id in processed_msgs or m.user_id == cl.user_id:
                        continue

                    is_group = thread.is_group or len(thread.users) > 2
                    sender_id = str(m.user_id)
                    username = cl.user_info(sender_id).username

                    is_owner = sender_id == OWNER_ID

                    # In groups, only reply if mentioned (unless owner)
                    if is_group and not is_owner:
                        bot_username = INSTA_USER.replace("_", "")
                        if f"@{bot_username}" not in m.text and "bot" not in m.text.lower():
                            continue

                    processed_msgs.add(m.id)
                    user_text = m.text or "Kuch to bole madarchod"

                    print(f"🎯 Target: @{username} | {'👑 OWNER' if is_owner else '👤 USER'} | Text: {user_text[:30]}...")

                    reply = generate_savage_reply(user_text, username, is_owner)
                    cl.direct_send(reply, thread_ids=[thread.id])
                    print(f"💀 Roast sent to @{username}")

                    time.sleep(random.randint(5, 10))

                except Exception as e:
                    print(f"⚠️ Thread error: {e}")
                    continue

            # Clean up old message IDs
            if len(processed_msgs) > 1000:
                processed_msgs = set(list(processed_msgs)[-500:])

        except Exception as e:
            print(f"❌ Main loop error: {e}")
            time.sleep(60)
            # Re-login if session expired
            try:
                cl.get_timeline_feed()
            except:
                print("🔄 Session expired, re-logging...")
                login_with_retry()

# ---------- Entry Point ----------
if __name__ == "__main__":
    # Run Flask in a separate thread to bind the port (required by Render)
    port = int(os.environ.get("PORT", 10000))
    flask_thread = threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()
    print(f"🌐 Flask server started on port {port}")

    # Run the bot
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
