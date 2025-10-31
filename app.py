from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import json
import os
from difflib import SequenceMatcher
import random
import re
import logging
from flask_cors import CORS  # 👈 NEW ADDED

app = Flask(__name__, template_folder='templates')
CORS(app)  # 👈 NEW ADDED - Roblox ke liye CORS enable karo
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['UPLOAD_EXTENSIONS'] = ['.json', '.jsonl']

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from pymongo import MongoClient
    MONGO_URI = os.environ.get('MONGO_URI')
    if MONGO_URI and MONGO_URI != 'your_mongodb_connection_string':
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.server_info()
        db = client['instagram_bot']
        training_collection = db['training_data']
        exception_collection = db['exception_list']
        MONGO_ENABLED = True
        logger.info("MongoDB connected!")
    else:
        MONGO_ENABLED = False
except:
    MONGO_ENABLED = False

LOCAL_TRAINING_FILE = 'training_data.json'
LOCAL_EXCEPTIONS_FILE = 'exceptions.json'

def load_local_training():
    if os.path.exists(LOCAL_TRAINING_FILE):
        with open(LOCAL_TRAINING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_local_training(data):
    with open(LOCAL_TRAINING_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_local_exceptions():
    if os.path.exists(LOCAL_EXCEPTIONS_FILE):
        with open(LOCAL_EXCEPTIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_local_exceptions(data):
    with open(LOCAL_EXCEPTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class AdvancedReplyBot:
    def __init__(self):
        self.training_data = []
        self.exception_list = []
        self.load_training_data()
        self.load_exception_list()
        # 👇 ROBLOX KE LIYE MEDIA RESPONSES HATA DIYE
        self.fallback_responses = [  # 👈 NEW FALLBACKS FOR ROBLOX
            "Cry about it 😂",
            "Mad cuz bad 💀", 
            "Skill issue bro",
            "You wish 🚀",
            "Stay mad 😎",
            "Bro I'm legit 💪",
            "Stop accusing 😴",
            "You're just bad 🤣",
            "Get good 💀",
            "Stay salty 🧂"
        ]
    
    def load_training_data(self):
        try:
            if MONGO_ENABLED:
                self.training_data = [{'instruction': item.get('instruction', ''), 'response': item.get('response', '')} for item in training_collection.find()]
            else:
                self.training_data = load_local_training()
            logger.info(f"Loaded {len(self.training_data)} examples")
        except Exception as e:
            logger.error(f"Load error: {e}")
    
    def load_exception_list(self):
        try:
            if MONGO_ENABLED:
                self.exception_list = [item.get('username', '').lower().strip() for item in exception_collection.find()]
            else:
                self.exception_list = load_local_exceptions()
            logger.info(f"Loaded {len(self.exception_list)} exceptions")
        except Exception as e:
            logger.error(f"Load exceptions error: {e}")
    
    def is_user_excepted(self, username):
        if not username:
            return False
        return username.lower().strip().replace('@', '') in self.exception_list
    
    def clean_text(self, text):
        return re.sub(r'\s+', ' ', text.lower().strip())
    
    def extract_keywords(self, text):
        stop_words = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'you', 'your', 'i', 'me', 'my'}
        return [w for w in re.findall(r'\b\w+\b', text.lower()) if w not in stop_words and len(w) > 2]
    
    def fuzzy_similarity(self, a, b):
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    def word_overlap_score(self, msg_keywords, instruction_keywords):
        if not msg_keywords or not instruction_keywords:
            return 0
        intersection = len(set(msg_keywords) & set(instruction_keywords))
        union = len(set(msg_keywords) | set(instruction_keywords))
        return intersection / union if union > 0 else 0
    
    def find_best_matches(self, incoming_message, top_n=3):
        incoming_clean = self.clean_text(incoming_message)
        incoming_keywords = self.extract_keywords(incoming_clean)
        scores = []
        for item in self.training_data:
            instruction = item.get('instruction', '')
            instruction_clean = self.clean_text(instruction)
            instruction_keywords = self.extract_keywords(instruction_clean)
            fuzzy = self.fuzzy_similarity(incoming_clean, instruction_clean)
            keyword = self.word_overlap_score(incoming_keywords, instruction_keywords)
            substring = 0.3 if instruction_clean in incoming_clean else 0
            score = fuzzy * 0.4 + keyword * 0.5 + substring
            scores.append({'instruction': instruction, 'response': item.get('response', ''), 'score': score})
        return sorted(scores, key=lambda x: x['score'], reverse=True)[:top_n]
    
    def get_response(self, message, username=None):
        # 👇 SIMPLIFIED FOR ROBLOX - NO MEDIA, NO GROUP MENTIONS
        if not message.strip():
            response = random.choice(self.fallback_responses)
        else:
            matches = self.find_best_matches(message, 3)
            if matches and matches[0]['score'] > 0.3:
                response = matches[0]['response']
            else:
                response = random.choice(self.fallback_responses)
        return response
    
    def add_single_data(self, instruction, response):
        try:
            if MONGO_ENABLED:
                training_collection.insert_one({'instruction': instruction, 'response': response})
            else:
                data = load_local_training()
                data.append({'instruction': instruction, 'response': response})
                save_local_training(data)
            self.load_training_data()
            return True
        except:
            return False
    
    def process_uploaded_file(self, file_content):
        added_count, error_count = 0, 0
        try:
            lines = file_content.decode('utf-8').split('\n')
            for line in lines:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    instruction, response = data.get('instruction', '').strip(), data.get('response', '').strip()
                    if instruction and response:
                        if MONGO_ENABLED:
                            if not training_collection.find_one({'instruction': instruction}):
                                training_collection.insert_one({'instruction': instruction, 'response': response})
                        else:
                            existing = load_local_training()
                            if not any(x['instruction'] == instruction for x in existing):
                                existing.append({'instruction': instruction, 'response': response})
                                save_local_training(existing)
                        added_count += 1
                except:
                    error_count += 1
            self.load_training_data()
            return {'success': True, 'added': added_count, 'errors': error_count, 'total': len(self.training_data)}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def add_exception(self, username):
        try:
            username_clean = username.lower().strip().replace('@', '')
            if not username_clean:
                return False, "Empty username"
            if MONGO_ENABLED:
                if not exception_collection.find_one({'username': username_clean}):
                    exception_collection.insert_one({'username': username_clean})
                else:
                    return False, "Already exists"
            else:
                exceptions = load_local_exceptions()
                if username_clean not in exceptions:
                    exceptions.append(username_clean)
                    save_local_exceptions(exceptions)
                else:
                    return False, "Already exists"
            self.load_exception_list()
            return True, f"@{username_clean} added"
        except:
            return False, "Error"
    
    def remove_exception(self, username):
        try:
            username_clean = username.lower().strip().replace('@', '')
            if MONGO_ENABLED:
                if exception_collection.delete_one({'username': username_clean}).deleted_count > 0:
                    self.load_exception_list()
                    return True, f"@{username_clean} removed"
                return False, "Not found"
            else:
                exceptions = load_local_exceptions()
                if username_clean in exceptions:
                    exceptions.remove(username_clean)
                    save_local_exceptions(exceptions)
                    self.load_exception_list()
                    return True, f"@{username_clean} removed"
                return False, "Not found"
        except:
            return False, "Error"
    
    def get_all_exceptions(self):
        if MONGO_ENABLED:
            return [item['username'] for item in exception_collection.find()]
        return load_local_exceptions()

bot = AdvancedReplyBot()

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

# 👇 NEW ADDED - ROBLOX HEALTH CHECK ENDPOINT
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy', 
        'service': 'VETO Bot Backend',
        'training_data_count': len(bot.training_data),
        'exceptions_count': len(bot.exception_list)
    })

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    if os.path.splitext(file.filename)[1].lower() not in app.config['UPLOAD_EXTENSIONS']:
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400
    try:
        result = bot.process_uploaded_file(file.read())
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/add_data', methods=['POST'])
def add_data():
    data = request.json
    instruction, response = data.get('instruction', '').strip(), data.get('response', '').strip()
    if not instruction or not response:
        return jsonify({'success': False, 'error': 'Both required'}), 400
    if bot.add_single_data(instruction, response):
        return jsonify({'success': True, 'total': len(bot.training_data)})
    return jsonify({'success': False, 'error': 'Failed'}), 500

@app.route('/test', methods=['POST'])
def test():
    data = request.json
    message = data.get('message', '')
    username = data.get('username', '')
    
    if not message:
        return jsonify({'error': 'Message required'}), 400
    
    # Check if user is in exception list
    if username and bot.is_user_excepted(username):
        return jsonify({'response': '[EXCEPTED]', 'excepted': True})
    
    # Get response from bot
    response = bot.get_response(message, username)
    return jsonify({
        'response': response, 
        'excepted': False,
        'backend': 'VETO Python Backend',
        'timestamp': os.times().system
    })

@app.route('/exception/add', methods=['POST'])
def add_exception():
    username = request.json.get('username', '').strip()
    if not username:
        return jsonify({'success': False, 'error': 'Username required'}), 400
    success, msg = bot.add_exception(username)
    return jsonify({'success': success, 'message': msg, 'total': len(bot.exception_list)})

@app.route('/exception/remove', methods=['POST'])
def remove_exception():
    username = request.json.get('username', '').strip()
    if not username:
        return jsonify({'success': False, 'error': 'Username required'}), 400
    success, msg = bot.remove_exception(username)
    return jsonify({'success': success, 'message': msg, 'total': len(bot.exception_list)})

@app.route('/exception/list', methods=['GET'])
def list_exceptions():
    return jsonify({'exceptions': bot.get_all_exceptions(), 'total': len(bot.exception_list)})

@app.route('/stats', methods=['GET'])
def stats():
    try:
        if MONGO_ENABLED:
            total = training_collection.count_documents({})
            exceptions = exception_collection.count_documents({})
        else:
            total = len(load_local_training())
            exceptions = len(load_local_exceptions())
        return jsonify({
            'total_examples': total, 
            'exceptions': exceptions, 
            'status': 'active',
            'backend': 'python_flask'
        })
    except:
        return jsonify({'total_examples': 0, 'exceptions': 0, 'status': 'error'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
