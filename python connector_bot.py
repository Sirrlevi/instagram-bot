#!/usr/bin/env python3
import time
import requests
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Load from environment variables
USERNAME = os.environ.get('INSTA_USER')
PASSWORD = os.environ.get('INSTA_PASS')
API_URL = os.environ.get('API_URL', 'https://instagram-bot-46tg.onrender.com')

if not USERNAME or not PASSWORD:
    logger.error("❌ Set INSTA_USER and INSTA_PASS environment variables!")
    exit(1)

from instagrapi import Client

def run_bot():
    client = Client()
    seen = set()
    
    try:
        logger.info("🔐 Login...")
        client.login(USERNAME, PASSWORD)
        logger.info("✅ OK!")
    except Exception as e:
        logger.error(f"❌ {e}")
        return
    
    logger.info("🤖 Bot Running...")
    
    while True:
        try:
            for thread in client.direct_threads(amount=10):
                try:
                    for msg in client.direct_messages(thread.id, amount=2):
                        if msg.message_type != 'text' or msg.id in seen:
                            continue
                        
                        logger.info(f"📨 @{msg.user.username}: {msg.text}")
                        
                        try:
                            r = requests.post(f"{API_URL}/test", 
                                json={"message": msg.text, "username": msg.user.username}, 
                                timeout=10)
                            if r.status_code == 200:
                                reply = r.json().get('response')
                                if reply and not r.json().get('excepted'):
                                    time.sleep(1)
                                    client.direct_send(reply, user_ids=[msg.user.id])
                                    logger.info(f"✅ Sent: {reply[:25]}")
                        except:
                            pass
                        
                        seen.add(msg.id)
                except:
                    pass
            
            time.sleep(20)
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error: {str(e)[:40]}")
            time.sleep(60)

if __name__ == "__main__":
    run_bot()
