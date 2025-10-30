# app.py - Advanced Instagram Auto-Reply Bot (FIXED INDENTATION)
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import json
import os
from difflib import SequenceMatcher
import random
import re
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_EXTENSIONS'] = ['.json', '.jsonl']

# MongoDB Connection
MONGO_URI = os.environ.get('MONGO_URI', 'your_mongodb_connection_string')
client = MongoClient(MONGO_URI)
db = client['instagram_bot']
training_collection = db['training_data']
files_collection = db['uploaded_files']
exception_collection = db['exception_list']
processed_messages = db['processed_messages']

class AdvancedReplyBot:
    def __init__(self):
        self.training_data = []
        self.exception_list = []
        self.load_training_data()
        self.load_exception_list()
        
        self.slang_groups = {
            'greetings': ['hey', 'hi', 'hello', 'sup', 'wassup', 'yo', 'namaste'],
            'compliments': ['cutie', 'hot', 'sexy', 'gorgeous', 'beautiful', 'babe'],
            'questions': ['wyd', 'what', 'where', 'when', 'why', 'how', 'kya'],
            'abuse': ['fuck', 'shit', 'bitch', 'ass', 'bc', 'mc', 'chutiya', 'madarchod'],
            'requests': ['send', 'give', 'show', 'share', 'dm', 'slide'],
        }
    
    def load_training_data(self):
        self.training_data = []
        try:
            data = training_collection.find()
            for item in data:
                self.training_data.append({
                    'instruction': item.get('instruction', ''),
                    'response': item.get('response', '')
                })
            print(f"✅ Loaded {len(self.training_data)} examples")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def load_exception_list(self):
        self.exception_list = []
        try:
            exceptions = exception_collection.find()
            for item in exceptions:
                username = item.get('username', '').lower().strip()
                if username:
                    self.exception_list.append(username)
            print(f"✅ Loaded {len(self.exception_list)} exceptions")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def is_user_excepted(self, username):
        if not username:
            return False
        username_clean = username.lower().strip().replace('@', '')
        return username_clean in self.exception_list
    
    def is_message_processed(self, message_id):
        try:
            result = processed_messages.find_one({'message_id': message_id})
            return result is not None
        except:
            return False
    
    def mark_message_processed(self, message_id):
        try:
            processed_messages.insert_one({
                'message_id': message_id,
                'processed_at': datetime.now()
            })
        except Exception as e:
            print(f"Error: {e}")
    
    def clean_text(self, text):
        text = text.lower().strip()
        text = re.sub(r's+', ' ', text)
        return text
    
    def extract_keywords(self, text):
        stop_words = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been',
                     'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would'}
        words = re.findall(r'\bw+\b', text.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return keywords
    
    def fuzzy_similarity(self, a, b):
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    def word_overlap_score(self, msg_keywords, instruction_keywords):
        if not msg_keywords or not instruction_keywords:
            return 0
        msg_set = set(msg_keywords)
        inst_set = set(instruction_keywords)
        intersection = msg_set.intersection(inst_set)
        union = msg_set.union(inst_set)
        return len(intersection) / len(union) if len(union) > 0 else 0
    
    def detect_slang_category(self, text):
        text_lower = text.lower()
        detected = []
        for category, words in self.slang_groups.items():
            for word in words:
                if word in text_lower:
                    detected.append(category)
                    break
        return detected
    
    def find_best_matches(self, incoming_message, top_n=3):
        incoming_clean = self.clean_text(incoming_message)
        incoming_keywords = self.extract_keywords(incoming_clean)
        incoming_categories = self.detect_slang_category(incoming_clean)
        
        scores = []
        for item in self.training_data:
            instruction = item.get('instruction', '')
            instruction_clean = self.clean_text(instruction)
            instruction_keywords = self.extract_keywords(instruction_clean)
            
            fuzzy_score = self.fuzzy_similarity(incoming_clean, instruction_clean)
            keyword_score = self.word_overlap_score(incoming_keywords, instruction_keywords)
            
            substring_boost = 0
            if instruction_clean in incoming_clean or incoming_clean in instruction_clean:
                substring_boost = 0.3
            
            category_boost = 0
            instruction_categories = self.detect_slang_category(instruction)
            if any(cat in instruction_categories for cat in incoming_categories):
                category_boost = 0.2
            
            combined_score = (
                fuzzy_score * 0.3 +
                keyword_score * 0.4 +
                substring_boost +
                category_boost
            )
            
            scores.append({
                'instruction': instruction,
                'response': item.get('response', ''),
                'score': combined_score
            })
        
        scores.sort(key=lambda x: x['score'], reverse=True)
        return scores[:top_n]
    
    def mix_responses(self, matches):
        if not matches:
            return self.get_default_response()
        if matches[0]['score'] > 0.6:
            return matches[0]['response']
        
        response_parts = []
        for match in matches[:2]:
            response = match['response']
            parts = re.split(r'[💀🥀☠️😭🤣💔🙏🏻]', response)
            if parts:
                response_parts.extend([p.strip() for p in parts if p.strip()])
        
        if response_parts:
            selected = random.sample(response_parts, min(2, len(response_parts)))
            emojis = ['💀', '🥀', '☠️', '😭', '🤣', '💔', '🙏🏻']
            emoji = random.choice(emojis)
            return f"{' '.join(selected)} {emoji}"
        return self.get_default_response()
    
    def get_default_response(self):
        defaults = [
            "sybau wtf u want moron 🥀",
            "stfu ngga busy rn ☠️",
            "ksmk leave me alone 💔",
            "teri maa ki chut bc 💀",
            "bhag bsdk time nhi hai 🤣",
            "die ngga nobody cares ☠️"
        ]
        return random.choice(defaults)
    
    def get_response(self, incoming_message, username=None, is_group=False):
        if not incoming_message or len(incoming_message.strip()) == 0:
            response = "stfu empty msg ngga 💀"
        else:
            matches = self.find_best_matches(incoming_message, top_n=3)
            if matches and matches[0]['score'] > 0.3:
                response = self.mix_responses(matches)
            else:
                response = self.get_default_response()
        
        if is_group and username:
            username_clean = username.strip().replace('@', '')
            response = f"@{username_clean} {response}"
        
        return response
    
    def add_single_data(self, instruction, response):
        try:
            training_collection.insert_one({
                'instruction': instruction,
                'response': response,
                'added_at': datetime.now()
            })
            self.load_training_data()
            return True
        except Exception as e:
            print(f"Error: {e}")
            return False
    
    def process_uploaded_file(self, file_content):
        added_count = 0
        error_count = 0
        try:
            lines = file_content.decode('utf-8').split('
')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    instruction = data.get('instruction', '').strip()
                    response = data.get('response', '').strip()
                    if instruction and response:
                        existing = training_collection.find_one({'instruction': instruction})
                        if not existing:
                            training_collection.insert_one({
                                'instruction': instruction,
                                'response': response,
                                'added_at': datetime.now()
                            })
                            added_count += 1
                except json.JSONDecodeError:
                    error_count += 1
                    continue
            self.load_training_data()
            return {
                'success': True,
                'added': added_count,
                'errors': error_count,
                'total': len(self.training_data)
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def add_exception(self, username):
        try:
            username_clean = username.lower().strip().replace('@', '')
            existing = exception_collection.find_one({'username': username_clean})
            if not existing:
                exception_collection.insert_one({
                    'username': username_clean,
                    'added_at': datetime.now()
                })
                self.load_exception_list()
                return True, "User added to exception list"
            else:
                return False, "User already in exception list"
        except Exception as e:
            return False, str(e)
    
    def remove_exception(self, username):
        try:
            username_clean = username.lower().strip().replace('@', '')
            result = exception_collection.delete_one({'username': username_clean})
            if result.deleted_count > 0:
                self.load_exception_list()
                return True, "User removed from exception list"
            else:
                return False, "User not found in exception list"
        except Exception as e:
            return False, str(e)
    
    def get_all_exceptions(self):
        try:
            exceptions = exception_collection.find()
            return [item['username'] for item in exceptions]
        except:
            return []

bot = AdvancedReplyBot()

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    filename = secure_filename(file.filename)
    file_ext = os.path.splitext(filename)[1].lower()
    if file_ext not in app.config['UPLOAD_EXTENSIONS']:
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400
    try:
        file_content = file.read()
        files_collection.insert_one({
            'filename': filename,
            'uploaded_at': datetime.now(),
            'size': len(file_content)
        })
        result = bot.process_uploaded_file(file_content)
        if result.get('success'):
            return jsonify({
                'success': True,
                'message': f"✅ File uploaded! Added {result['added']} new examples",
                'stats': {
                    'added': result['added'],
                    'errors': result['errors'],
                    'total': result['total']
                }
            })
        else:
            return jsonify({'success': False, 'error': result.get('error')}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/add_data', methods=['POST'])
def add_data():
    data = request.json
    instruction = data.get('instruction', '').strip()
    response = data.get('response', '').strip()
    if not instruction or not response:
        return jsonify({'success': False, 'error': 'Required fields missing'}), 400
    if bot.add_single_data(instruction, response):
        return jsonify({'success': True, 'message': 'Data added', 'total': len(bot.training_data)})
    else:
        return jsonify({'success': False, 'error': 'Failed to add'}), 500

@app.route('/test', methods=['POST'])
def test():
    data = request.json
    message = data.get('message', '')
    username = data.get('username', '')
    is_group = data.get('is_group', False)
    if not message:
        return jsonify({'error': 'Message required'}), 400
    if username and bot.is_user_excepted(username):
        return jsonify({
            'message': message,
            'response': '[USER IN EXCEPTION LIST - NO REPLY]',
            'excepted': True
        })
    response = bot.get_response(message, username, is_group)
    return jsonify({
        'message': message,
        'response': response,
        'username': username,
        'is_group': is_group,
        'excepted': False
    })

@app.route('/exception/add', methods=['POST'])
def add_exception():
    data = request.json
    username = data.get('username', '').strip()
    if not username:
        return jsonify({'success': False, 'error': 'Username required'}), 400
    success, message = bot.add_exception(username)
    if success:
        return jsonify({'success': True, 'message': message, 'total': len(bot.exception_list)})
    else:
        return jsonify({'success': False, 'error': message}), 400

@app.route('/exception/remove', methods=['POST'])
def remove_exception():
    data = request.json
    username = data.get('username', '').strip()
    if not username:
        return jsonify({'success': False, 'error': 'Username required'}), 400
    success, message = bot.remove_exception(username)
    if success:
        return jsonify({'success': True, 'message': message, 'total': len(bot.exception_list)})
    else:
        return jsonify({'success': False, 'error': message}), 400

@app.route('/exception/list', methods=['GET'])
def list_exceptions():
    exceptions = bot.get_all_exceptions()
    return jsonify({'success': True, 'exceptions': exceptions, 'total': len(exceptions)})

@app.route('/stats', methods=['GET'])
def stats():
    file_count = files_collection.count_documents({})
    training_count = training_collection.count_documents({})
    exception_count = exception_collection.count_documents({})
    processed_count = processed_messages.count_documents({})
    return jsonify({
        'total_examples': training_count,
        'files_uploaded': file_count,
        'exceptions': exception_count,
        'messages_processed': processed_count,
        'status': 'active'
    })

@app.route('/reload', methods=['POST'])
def reload_data():
    bot.load_training_data()
    bot.load_exception_list()
    return jsonify({
        'success': True,
        'message': 'All data reloaded',
        'training': len(bot.training_data),
        'exceptions': len(bot.exception_list)
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if 'message' in data:
        message_id = data['message'].get('id', '')
        incoming_msg = data['message']['text']
        sender_id = data['message']['sender']['id']
        sender_username = data['message']['sender'].get('username', '')
        is_group = data.get('is_group_thread', False)
        if bot.is_message_processed(message_id):
            return jsonify({'status': 'already_processed'})
        if bot.is_user_excepted(sender_username):
            return jsonify({'status': 'user_excepted'})
        response = bot.get_response(incoming_msg, sender_username, is_group)
        bot.mark_message_processed(message_id)
        return jsonify({
            'recipient': {'id': sender_id},
            'message': {'text': response},
            'reply_to_message_id': message_id
        })
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
