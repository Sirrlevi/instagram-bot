import os
import random
import time
from datetime import datetime
from dotenv import load_dotenv
from instagrapi import Client
from openai import OpenAI

load_dotenv()

IG_USERNAME = os.getenv('IG_USERNAME')
IG_PASSWORD = os.getenv('IG_PASSWORD')
OWNER_ID = int(os.getenv('OWNER_IG_USER_ID'))
OWNER_USERNAME = os.getenv('OWNER_IG_USERNAME')
API_KEY = os.getenv('API_KEY')
BASE_URL = os.getenv('BASE_URL', 'https://api.x.ai/v1')
MODEL = os.getenv('MODEL', 'grok-beta')

print("✅ Instagram Brutal Bot Starting...")

cl = Client()
cl.login(IG_USERNAME, IG_PASSWORD)
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# souls.md
with open('souls.md', 'r', encoding='utf-8') as f:
    SOUL_PROMPT = f.read().strip()

def generate_roast(text, sender_username):
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SOUL_PROMPT},
                {"role": "user", "content": f"Gory brutal roast this madarchod hard: {text} (sender: {sender_username})"}
            ],
            max_tokens=300,
            temperature=1.35
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"API error: {e}")
        return "API so gaya bc 🩸"

# Last checked time (to avoid old messages)
last_check = datetime.now()

while True:
    try:
        # Get all direct threads (DMs + Group DMs)
        threads = cl.direct_threads(amount=20)
        
        for thread in threads:
            for msg in thread.messages:
                if msg.timestamp < last_check:
                    continue  # purane messages ignore
                
                sender_id = msg.user_id
                sender_username = msg.user.username if msg.user else "unknown"
                text = msg.text or "media bheja hai bc"
                
                # Owner check (user_id ya username dono se)
                is_owner = (sender_id == OWNER_ID) or (sender_username.lower() == OWNER_USERNAME.lower())
                
                if is_owner:
                    # Owner ko obey + respect
                    if text.lower().startswith(('/', 'order', 'bol')):
                        reply = "Haan baapji, order do 🔥 Kya gaand faadna hai aaj?"
                    else:
                        reply = "Haan boss, sun raha hu. Bol kya scene hai? 🔥"
                else:
                    # Baaki sabko full savage roast
                    reply = generate_roast(text, sender_username)
                    # Extra brutal touch
                    reply += random.choice([" Madarchod destroy ho gaya! 🩸", " Gaand faad di teri! 🔥", " Maa chud gayi gory style mein 😂"])
                
                # Reply karo
                cl.direct_send(reply, thread_id=thread.id)
                print(f"Roasted {sender_username}: {text} → {reply[:50]}...")
                
        last_check = datetime.now()
        time.sleep(8)  # 8 second mein check (rate limit safe)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(30)
