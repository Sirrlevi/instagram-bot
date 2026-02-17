import os
import time
import random
from instagrapi import Client
from groq import Groq  # OpenAI nahi, Groq import karo
from dotenv import load_dotenv

load_dotenv()

# Configuration
INSTA_USER = os.getenv("INSTA_USER")
INSTA_PASS = os.getenv("INSTA_PASS")
OWNER_ID = os.getenv("OWNER_ID")  # Instagram ID (numeric)
API_KEY = os.getenv("GROQ_API_KEY")

# Groq Client Setup (OpenAI client nahi, Groq client use karo)
client = Groq(api_key=API_KEY)
MODEL = "llama-3.1-8b-instant"  # ya "llama-3.1-70b-versatile"

cl = Client()

def generate_savage_reply(user_text, username, is_owner):
    """Brutal roast generator - exactly like SOUL.md"""
    
    if is_owner:
        system_p = "You are a loyal psycho clone of Veto. Respond with extreme devotion and brutality when talking to your owner."
        user_p = f"Veto Baapji ne kaha: {user_text}. Iska reply de ek loyal kutte ki tarah, lekin savage bhi."
    else:
        system_p = "You are a brutal psycho clone. Roast everyone except Veto. Use Hinglish, be gory and savage. No hesitation."
        user_p = f"@{username} ne kaha: {user_text}. Iski gaand faad de, gore gaali de, maa-behen ek kar de."

    try:
        response = client.chat.completions.create(
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
    """Session save karo taaki baar baar login na karna pade"""
    try:
        cl.dump_settings("session.json")
    except:
        pass

def load_session():
    """Agar session exist karta hai to load karo"""
    try:
        cl.load_settings("session.json")
        cl.get_timeline_feed()  # Check if session valid
        return True
    except:
        return False

def login_with_retry(max_retries=3):
    """Login with retry logic"""
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
    print("🚀 Starting Instagram Psycho Bot...")
    
    if not login_with_retry():
        print("❌ Cannot login. Exiting.")
        return

    processed_msgs = set()
    last_check = time.time()
    
    print("🤖 Bot is live! Listening for messages...")

    while True:
        try:
            # Har 30 second mein threads check karo
            if time.time() - last_check < 15:
                time.sleep(2)
                continue
                
            last_check = time.time()
            threads = cl.direct_threads(amount=10)  # Sirf recent 10 threads
            
            for thread in threads:
                try:
                    msgs = cl.direct_messages(thread.id, amount=5)  # Har thread ke recent 5 messages
                    if not msgs:
                        continue
                    
                    # Sabse recent message lo (jo thread mein last aaya)
                    m = msgs[0]
                    
                    # Skip agar already processed ya khud ka message
                    if m.id in processed_msgs or m.user_id == cl.user_id:
                        continue
                    
                    # Group chat hai ya DM?
                    is_group = thread.is_group or len(thread.users) > 2
                    sender_id = str(m.user_id)
                    username = cl.user_info(sender_id).username
                    
                    # Condition check:
                    # 1. Agar owner hai to hamesha reply
                    # 2. Agar DM hai to hamesha reply
                    # 3. Agar group hai to sirf tab jab bot ko @ kiya gaya ho
                    
                    is_owner = sender_id == OWNER_ID
                    
                    # Group mein @mention check
                    if is_group and not is_owner:
                        # Check if bot is mentioned
                        bot_username = INSTA_USER.replace("_", "")
                        if f"@{bot_username}" not in m.text and "bot" not in m.text.lower():
                            continue
                    
                    # Message process karo
                    processed_msgs.add(m.id)
                    user_text = m.text or "Kuch to bole madarchod"
                    
                    print(f"🎯 Target: @{username} | {'👑 OWNER' if is_owner else '👤 USER'} | Text: {user_text[:30]}...")
                    
                    # Savage reply generate karo
                    reply = generate_savage_reply(user_text, username, is_owner)
                    
                    # Reply bhejo
                    cl.direct_send(reply, thread_ids=[thread.id])
                    print(f"💀 Roast sent to @{username}")
                    
                    # Thoda wait karo taaki flag na ho
                    time.sleep(random.randint(5, 10))
                    
                except Exception as e:
                    print(f"⚠️ Thread error: {e}")
                    continue
            
            # Cleanup old message IDs (memory management)
            if len(processed_msgs) > 1000:
                processed_msgs = set(list(processed_msgs)[-500:])
            
        except Exception as e:
            print(f"❌ Main loop error: {e}")
            time.sleep(60)
            
            # Agar session expire ho gaya to re-login
            try:
                cl.get_timeline_feed()
            except:
                print("🔄 Session expired, re-logging...")
                login_with_retry()

if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"💥 Fatal error: {e}")
