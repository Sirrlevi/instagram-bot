import os
import time
import random
from instagrapi import Client
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configuration
INSTA_USER = os.getenv("INSTA_USER")
INSTA_PASS = os.getenv("INSTA_PASS")
OWNER_ID = os.getenv("OWNER_ID")
API_KEY = os.getenv("GROQ_API_KEY")

# Groq Client Setup
client = OpenAI(api_key=API_KEY, base_url="https://api.groq.com/openai/v1")
MODEL = "llama-3.1-8b-instant"

cl = Client()

def generate_savage_reply(user_text, username, is_owner):
    # Wahi brutal prompt jo upar diya hai
    system_p = "You are a brutal psycho clone. Roast everyone except 'Carno'. Use Hinglish, be gory and savage. No hesitation."
    
    if is_owner:
        user_p = f"My Owner Carno said: {user_text}. Reply like a loyal psycho dog."
    else:
        user_p = f"Roast @{username} extremely hard. They said: {user_text}. Make it brutal, include gory insults and savage Hinglish slangs."

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_p},
                {"role": "user", "content": user_p}
            ],
            temperature=1.3 # Zyada randomness ke liye
        )
        return response.choices[0].message.content.strip()
    except:
        return f"@{username} Teri MKC, Groq API ki gaand phat gayi tera chehra dekh ke!"

def run_bot():
    print("Logging in...")
    try:
        cl.login(INSTA_USER, INSTA_PASS)
        print("Insta Bot Live! 🚀")
    except Exception as e:
        print(f"Login failed: {e}")
        return

    processed_msgs = set()

    while True:
        try:
            threads = cl.direct_threads()
            for thread in threads:
                msgs = cl.direct_messages(thread.id, amount=1)
                if not msgs: continue
                
                m = msgs[0]
                if m.id in processed_msgs or m.user_id == cl.user_id:
                    continue

                processed_msgs.add(m.id)
                user_text = m.text or ""
                sender_id = str(m.user_id)
                username = cl.user_info(sender_id).username
                
                # Logic: DM me reply, Group me Tag pe reply
                is_group = len(thread.users) > 1
                is_owner = sender_id == OWNER_ID
                
                if is_group and f"@{INSTA_USER}" not in user_text and not is_owner:
                    continue

                print(f"Target Acquired: {username}")
                reply = generate_savage_reply(user_text, username, is_owner)
                
                # Final brutal touch
                cl.message_send(reply, thread_id=thread.id)
                print(f"Roast sent to {username}")

            time.sleep(15) # Safety gap taaki Insta ban na kare
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_bot()
