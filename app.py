from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import json
import os
from difflib import SequenceMatcher
import random
import re
from datetime import datetime
import logging

app = Flask(__name__, template_folder='templates')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['UPLOAD_EXTENSIONS'] = ['.json', '.jsonl']

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try MongoDB, fallback to local JSON storage
MONGO_ENABLED = False
try:
    from pymongo import MongoClient
    MONGO_URI = os.environ.get('MONGO_URI')
    if MONGO_URI and MONGO_URI != 'your_mongodb_connection_string':
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.server_info()
        db = client['instagram_bot']
        training_collection = db['training_data']
        exception_collection = db['exception_list']
        files_collection = db['uploaded_files']
        MONGO_ENABLED = True
        logger.info("âœ… MongoDB connected!")
    else:
        logger.warning("MongoDB URI not set - using local JSON storage")
except Exception as e:
    logger.warning(f"MongoDB failed: {e} - using local JSON storage")

# Local JSON storage fallback
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

        self.media_responses = {
            'reel': ["nice reel bsdk ðŸ’€", "cringe reel stfu â˜ ï¸"],
            'sticker': ["sticker bhej ke funny ban gya? ðŸ’”"],
            'gif': ["gif bhej ke cool ban rha? ðŸ’€"],
            'image': ["pic dekh li bc ðŸ¥€"],
            'video': ["video dekh li boring af â˜ ï¸"],
            'audio': ["song suna chutiye ðŸ¥€"],
            'voice': ["voice note sun li bsdk â˜ ï¸"],
            'call': ["call mat kar bhikhari ðŸ’€"],
            'video_call': ["video call? muh mat dikha ðŸ˜­"]
        }

    def load_training_data(self):
        self.training_data = []
        try:
            if MONGO_ENABLED:
                data = list(training_collection.find())
                self.training_data = [{'instruction': item.get('instruction', ''), 'response': item.get('response', '')} for item in data]
            else:
                self.training_data = load_local_training()
            logger.info(f"âœ… Loaded {len(self.training_data)} training examples")
        except Exception as e:
            logger.error(f"Load training error: {e}")
            self.training_data = []

    def load_exception_list(self):
        self.exception_list = []
        try:
            if MONGO_ENABLED:
                exceptions = list(exception_collection.find())
                self.exception_list = [item.get('username', '').lower().strip() for item in exceptions if item.get('username')]
            else:
                self.exception_list = load_local_exceptions()
            logger.info(f"âœ… Loaded {len(self.exception_list)} exceptions")
        except Exception as e:
            logger.error(f"Load exceptions error: {e}")
            self.exception_list = []

    def is_user_excepted(self, username):
        if not username:
            return False
        username_clean = username.lower().strip().replace('@', '')
        return username_clean in self.exception_list

    def clean_text(self, text):
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)
        return text

    def extract_keywords(self, text):
        stop_words = {'a', 'an', 'the', 'is', 'are', 'was', 'were'}
        words = re.findall(r'\b\w+\b', text.lower())
        return [w for w in words if w not in stop_words and len(w) > 2]

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

    def find_best_matches(self, incoming_message, top_n=3):
        incoming_clean = self.clean_text(incoming_message)
        incoming_keywords = self.extract_keywords(incoming_clean)
        scores = []

        for item in self.training_data:
            instruction = item.get('instruction', '')
            instruction_clean = self.clean_text(instruction)
            instruction_keywords = self.extract_keywords(instruction_clean)

            fuzzy_score = self.fuzzy_similarity(incoming_clean, instruction_clean)
            keyword_score = self.word_overlap_score(incoming_keywords, instruction_keywords)
            substring_boost = 0.3 if instruction_clean in incoming_clean or incoming_clean in instruction_clean else 0

            combined_score = fuzzy_score * 0.4 + keyword_score * 0.5 + substring_boost
            scores.append({'instruction': instruction, 'response': item.get('response', ''), 'score': combined_score})

        scores.sort(key=lambda x: x['score'], reverse=True)
        return scores[:top_n]

    def get_media_response(self, media_type):
        if media_type in self.media_responses:
            return random.choice(self.media_responses[media_type])
        return "dekh lia bc ðŸ’€"

    def get_default_response(self):
        defaults = ["sybau wtf u want ðŸ¥€", "stfu ngga â˜ ï¸", "teri maa ki chut ðŸ’€", "bhag bsdk ðŸ¤£"]
        return random.choice(defaults)

    def get_response(self, incoming_message, username=None, is_group=False, media_type=None):
        if media_type:
            response = self.get_media_response(media_type)
        elif not incoming_message or len(incoming_message.strip()) == 0:
            response = "stfu empty msg ðŸ’€"
        else:
            matches = self.find_best_matches(incoming_message, top_n=3)
            if matches and matches[0]['score'] > 0.3:
                response = matches[0]['response']
            else:
                response = self.get_default_response()

        if is_group and username:
            username_clean = username.strip().replace('@', '')
            response = f"@{username_clean} {response}"

        return response

    def add_single_data(self, instruction, response):
        try:
            if MONGO_ENABLED:
                training_collection.insert_one({'instruction': instruction, 'response': response, 'added_at': datetime.now()})
            else:
                data = load_local_training()
                data.append({'instruction': instruction, 'response': response})
                save_local_training(data)
            self.load_training_data()
            return True
        except Exception as e:
            logger.error(f"Add data error: {e}")
            return False

    def process_uploaded_file(self, file_content):
        added_count = 0
        error_count = 0
        try:
            content_str = file_content.decode('utf-8')
            lines = content_str.split('\n')

            data_to_add = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    instruction = data.get('instruction', '').strip()
                    response = data.get('response', '').strip()
                    if instruction and response:
                        data_to_add.append({'instruction': instruction, 'response': response})
                        added_count += 1
                except:
                    error_count += 1

            if MONGO_ENABLED:
                for item in data_to_add:
                    existing = training_collection.find_one({'instruction': item['instruction']})
                    if not existing:
                        training_collection.insert_one({**item, 'added_at': datetime.now()})
            else:
                existing_data = load_local_training()
                for item in data_to_add:
                    if not any(x['instruction'] == item['instruction'] for x in existing_data):
                        existing_data.append(item)
                save_local_training(existing_data)

            self.load_training_data()
            return {'success': True, 'added': added_count, 'errors': error_count, 'total': len(self.training_data)}
        except Exception as e:
            logger.error(f"File processing error: {e}")
            return {'success': False, 'error': str(e)}

    def add_exception(self, username):
        try:
            username_clean = username.lower().strip().replace('@', '')
            if not username_clean:
                return False, "Username cannot be empty"

            if MONGO_ENABLED:
                existing = exception_collection.find_one({'username': username_clean})
                if not existing:
                    exception_collection.insert_one({'username': username_clean, 'added_at': datetime.now()})
            else:
                exceptions = load_local_exceptions()
                if username_clean not in exceptions:
                    exceptions.append(username_clean)
                    save_local_exceptions(exceptions)
                else:
                    return False, "User already in exception list"

            self.load_exception_list()
            return True, f"@{username_clean} added to exception list"
        except Exception as e:
            logger.error(f"Add exception error: {e}")
            return False, str(e)

    def remove_exception(self, username):
        try:
            username_clean = username.lower().strip().replace('@', '')

            if MONGO_ENABLED:
                result = exception_collection.delete_one({'username': username_clean})
                if result.deleted_count > 0:
                    self.load_exception_list()
                    return True, f"@{username_clean} removed"
                else:
                    return False, "User not found"
            else:
                exceptions = load_local_exceptions()
                if username_clean in exceptions:
                    exceptions.remove(username_clean)
                    save_local_exceptions(exceptions)
                    self.load_exception_list()
                    return True, f"@{username_clean} removed"
                else:
                    return False, "User not found"
        except Exception as e:
            logger.error(f"Remove exception error: {e}")
            return False, str(e)

    def get_all_exceptions(self):
        try:
            if MONGO_ENABLED:
                exceptions = list(exception_collection.find())
                return [item['username'] for item in exceptions if item.get('username')]
            else:
                return load_local_exceptions()
        except:
            return []

bot = AdvancedReplyBot()

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'mongodb': MONGO_ENABLED, 'storage': 'local' if not MONGO_ENABLED else 'mongodb'})

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
        return jsonify({'success': False, 'error': 'Invalid file type (use .json or .jsonl)'}), 400

    try:
        file_content = file.read()
        result = bot.process_uploaded_file(file_content)
        return jsonify(result if result.get('success') else {'success': False, 'error': result.get('error')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/add_data', methods=['POST'])
def add_data():
    data = request.json
    instruction = data.get('instruction', '').strip()
    response = data.get('response', '').strip()

    if not instruction or not response:
        return jsonify({'success': False, 'error': 'Both fields required'}), 400

    if bot.add_single_data(instruction, response):
        return jsonify({'success': True, 'message': 'Added', 'total': len(bot.training_data)})
    return jsonify({'success': False, 'error': 'Failed'}), 500

@app.route('/test', methods=['POST'])
def test():
    data = request.json
    message = data.get('message', '')
    username = data.get('username', '')
    is_group = data.get('is_group', False)
    media_type = data.get('media_type', None)

    if not message and not media_type:
        return jsonify({'error': 'Message or media_type required'}), 400

    if username and bot.is_user_excepted(username):
        return jsonify({'message': message, 'response': '[EXCEPTED]', 'excepted': True})

    response = bot.get_response(message, username, is_group, media_type)
    return jsonify({'message': message, 'response': response, 'excepted': False})

@app.route('/exception/add', methods=['POST'])
def add_exception():
    data = request.json
    username = data.get('username', '').strip()

    if not username:
        return jsonify({'success': False, 'error': 'Username required'}), 400

    success, message = bot.add_exception(username)
    return jsonify({'success': success, 'message': message, 'total': len(bot.exception_list)})

@app.route('/exception/remove', methods=['POST'])
def remove_exception():
    data = request.json
    username = data.get('username', '').strip()

    if not username:
        return jsonify({'success': False, 'error': 'Username required'}), 400

    success, message = bot.remove_exception(username)
    return jsonify({'success': success, 'message': message, 'total': len(bot.exception_list)})

@app.route('/exception/list', methods=['GET'])
def list_exceptions():
    exceptions = bot.get_all_exceptions()
    return jsonify({'success': True, 'exceptions': exceptions, 'total': len(exceptions)})

@app.route('/stats', methods=['GET'])
def stats():
    return jsonify({
        'total_examples': len(bot.training_data),
        'files_uploaded': len(bot.training_data),
        'exceptions': len(bot.exception_list),
        'messages_processed': 0,
        'status': 'active'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
