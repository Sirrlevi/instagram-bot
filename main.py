import os
import random
import time
import sqlite3
from datetime import datetime
from instagrapi import Client
from openai import OpenAI

# ── Env se load ──
IG_SESSION_ID     = os.getenv('IG_SESSION_ID')
OWNER_IG_USER_ID  = int(os.getenv('OWNER_IG_USER_ID', '0'))
OWNER_IG_USERNAME = os.getenv('OWNER_IG_USERNAME', '').lower()
API_KEY           = os.getenv('API_KEY')
BASE_URL          = os.getenv('BASE_URL', 'https://api.groq.com/openai/v1')
MODEL             = os.getenv('MODEL', 'llama-3.1-8b-instant')

if not IG_SESSION_ID or OWNER_IG_USER_ID == 0 or not API_KEY:
    raise ValueError("IG_SESSION_ID, OWNER_IG_USER_ID ya API_KEY missing! Railway Variables check kar.")

print("Instagram Brutal Clone starting (Session ID mode)...")
print(f"Owner: {OWNER_IG_USERNAME} (ID: {OWNER_IG_USER_ID})")

# Instagram login – session ID se
cl = Client()
cl.delay_range = [1, 3]

try:
    cl.login_by_sessionid(IG_SESSION_ID)
    print("Instagram session ID se login successful! 🔥")
except Exception as e:
    print("Session ID login fail:", str(e))
    raise

# Groq API
grok = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# souls.md
try:
    with open('souls.md', 'r', encoding='utf-8') as f:
        SOUL_PROMPT = f.read().strip()
except:
    raise FileNotFoundError("souls.md missing!")

# Database + fallbacks
conn = sqlite3.connect('brutal_insta.db', check_same_thread=False)
c = conn.cursor()
c.executescript('''
CREATE TABLE IF NOT EXISTS fallbacks (id INTEGER PRIMARY KEY, template TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS message_log (id INTEGER PRIMARY KEY, sender_id INTEGER, text TEXT, timestamp TEXT);
''')
conn.commit()

fallbacks = [
    "Arre {user} madarchod, {msg} bol raha hai jaise teri maa khoon ugal rahi ho aur tu lauda choos raha 😂 Gaand faad dunga teri!",
    "{user} chutiye, {msg} sunke teri behen ko 10 laude padne ka mann kar raha. Khoon nikalega tera aaj!",
    "Bhenchod {user}, teri gaand se aag nikalegi {msg} bolke. Maa chud gayi teri gory style mein!",
    "Randi ke bache {user}, {msg} bolke apni maa bech diya? Ab main tujhe zinda gaad ke roast karunga!",
    "Madarchod {user}, tere muh se {msg} nikal raha jaise gaand se shit. Khoon aur aag dono nikalenge!"
]
for tpl in fallbacks:
    c.execute("INSERT OR IGNORE INTO fallbacks (template) VALUES (?)", (tpl,))
conn.commit()

def get_fallback(sender_name, msg):
    c.execute("SELECT template FROM fallbacks ORDER BY RANDOM() LIMIT 1")
    tpl = c.fetchone()[0]
    return tpl.format(user=sender_name, msg=msg[:50]) + " 🩸🔥 Maa chud gayi!"

# Main loop
last_check = datetime.now().timestamp()

print("Bot chal raha hai... DM ka wait kar raha hu 🔥")

while True:
    try:
        threads = cl.direct_threads(amount=20)

        for thread in threads:
            messages = cl.direct_messages(thread.id, amount=10)

            for msg in messages:
                if msg.timestamp.timestamp() <= last_check:
                    continue

                sender_id = msg.user_id
                sender_name = msg.user.username if msg.user else f"user_{sender_id}"
                text = msg.text or "[media/sticker]"

                now = datetime.now().isoformat()
                c.execute("INSERT INTO message_log (sender_id, text, timestamp) VALUES (?,?,?)",
                          (sender_id, text[:200], now))
                conn.commit()

                c.execute("SELECT COUNT(*) FROM message_log WHERE sender_id=? AND timestamp > datetime('now','-1 hour')",
                          (sender_id,))
                if c.fetchone()[0] > 15:
                    continue

                is_owner = (sender_id == OWNER_IG_USER_ID) or (sender_name.lower() == OWNER_IG_USERNAME.lower())

                if is_owner:
                    reply = "Haan boss, sun raha hu 🔥 Order do, kya gaand faadna hai?"
                else:
                    try:
                        resp = grok.chat.completions.create(
                            model=MODEL,
                            messages=[
                                {"role": "system", "content": SOUL_PROMPT},
                                {"role": "user", "content": f"Gory brutal roast this madarchod hard: {text} (from @{sender_name})"}
                            ],
                            max_tokens=300,
                            temperature=1.35,
                            top_p=0.95
                        )
                        reply = resp.choices[0].message.content.strip()
                    except Exception as e:
                        print(f"Groq API error: {e}")
                        reply = "API so gaya bc madarchod"

                    if "cannot" in reply.lower() or "sorry" in reply.lower() or len(reply) < 30:
                        reply = get_fallback(sender_name, text)

                    reply += random.choice([
                        " Madarchod destroy ho gaya! 🩸",
                        " Gaand faad di teri bhenchod! 🔥",
                        " Maa chud gayi gory way mein 😂",
                        " Khoon nikal gaya randi ke! ⚔️"
                    ])

                cl.direct_send(reply, thread_ids=[thread.id])
                print(f"→ @{sender_name}: {text[:40]}...  →  {reply[:40]}...")

        last_check = datetime.now().timestamp()
        time.sleep(12)

    except Exception as e:
        print("Loop error:", str(e))
        time.sleep(60)
