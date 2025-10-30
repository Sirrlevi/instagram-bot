from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import json
import os
from difflib import SequenceMatcher
import random
import re
from pymongo import MongoClient
from datetime import datetime
import logging

app = Flask(__name__, template_folder="templates")
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['UPLOAD_EXTENSIONS'] = ['.json', '.jsonl']

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGO_URI = os.environ.get('MONGO_URI')
if not MONGO_URI or MONGO_URI == 'your_mongodb_connection_string':
    logger.error("MongoDB URI not configured!")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.server_info()
    db = client['instagram-bot']
    # If a specific DB name is desired, change to: db = client['instagram_bot']
    training_collection = db['training_data'] if db is not None else None
    files_collection = db['uploaded_files'] if db is not None else None
    exception_collection = db['exception_list'] if db is not None else None
    processed_messages = db['processed_messages'] if db is not None else None
    logger.info("MongoDB connected successfully!")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    db = None
    training_collection = files_collection = exception_collection = processed_messages = None

class AdvancedReplyBot:
    def __init__(self):
        self.training_data = []
        self.exception_list = []
        if db is not None:
            self.load_training_data()
            self.load_exception_list()

        self.media_responses = {
            'reel': ["nice reel bsdk 💀", "cringe reel stfu ☠️", "teri maa ka reel better hoga 🥀"],
            'sticker': ["sticker bhej ke funny ban gya? 💔", "stfu with stickers ngga 😭"],
            'gif': ["gif bhej ke cool ban rha? 💀", "cringe gif bsdk ☠️"],
            'image': ["pic dekh li bc 🥀", "blur hai teri shakal jaisa 💀"],
            'video': ["video dekh li boring af ☠️", "teri maa ki video better 💔"],
            'audio': ["song suna chutiye 🥀", "gaana acha tha teri shakal nhi 💀"],
            'voice': ["voice note sun li bsdk ☠️", "awaaz bhi ghatiya personality bhi 💔"],
            'call': ["call mat kar bhikhari 💀", "phone utha le kutte 🥀"],
            'video_call': ["video call? muh mat dikha 😭", "teri shakal dekhni hai kya bc ☠️"]
        }

    def load_training_data(self):
        self.training_data = []
        try:
            if training_collection is not None:
                data = training_collection.find()
                for item in data:
                    self.training_data.append({'instruction': item.get('instruction', ''), 'response': item.get('response', '')})
                logger.info(f"Loaded {len(self.training_data)} training examples")
        except Exception as e:
            logger.error(f"Error loading training data: {e}")

    def load_exception_list(self):
        self.exception_list = []
        try:
            if exception_collection is not None:
                exceptions = exception_collection.find()
                for item in exceptions:
                    username = item.get('username', '').lower().strip()
                    if username:
                        self.exception_list.append(username)
                logger.info(f"Loaded {len(self.exception_list)} exceptions")
        except Exception as e:
            logger.error(f"Error loading exceptions: {e}")

    def is_user_excepted(self, username):
        if not username:
            return False
        username_clean = username.lower().strip().replace('@', '')
        return username_clean in self.exception_list

    def is_message_processed(self, message_id):
        try:
            if processed_messages is not None:
                result = processed_messages.find_one({'message_id': message_id})
                return result is not None
        except:
            pass
        return False

    def mark_message_processed(self, message_id):
        try:
            if processed_messages is not None:
                processed_messages.insert_one({'message_id': message_id, 'processed_at': datetime.now()})
        except Exception as e:
            logger.error(f"Error marking message: {e}")

    def clean_text(self, text):
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)
        return text

    def extract_keywords(self, text):
        stop_words = {'a', 'an', 'the', 'is', 'are', 'was', 'were'}
        words = re.findall(r'\b\w+\b', text.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return keywords

    def fuzzy_similarity(self, a, b):
        try:
            return SequenceMatcher(None, a.lower(), b.lower()).ratio()
        except:
            return 0.0

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
        return "dekh lia bc 💀"

    def get_default_response(self):
        defaults = ["sybau wtf u want 🥀", "stfu ngga ☠️", "teri maa ki chut 💀", "bhag bsdk 🤣", "die ngga ☠️"]
        return random.choice(defaults)

    def get_response(self, incoming_message, username=None, is_group=False, media_type=None):
        if media_type:
            response = self.get_media_response(media_type)
        elif not incoming_message or len(incoming_message.strip()) == 0:
            response = "stfu empty msg 💀"
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
            if training_collection is not None:
                training_collection.insert_one({'instruction': instruction, 'response': response, 'added_at': datetime.now()})
                self.load_training_data()
                return True
        except Exception as e:
            logger.error(f"Error adding data: {e}")
        return False

    def process_uploaded_file(self, file_content):
        added_count = 0
        error_count = 0
        try:
            content_str = file_content.decode('utf-8')
            lines = content_str.split('\n')

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    instruction = data.get('instruction', '').strip()
                    response = data.get('response', '').strip()

                    if instruction and response and training_collection:
                        existing = training_collection.find_one({'instruction': instruction})
                        if not existing:
                            training_collection.insert_one({'instruction': instruction, 'response': response, 'added_at': datetime.now()})
                            added_count += 1
                except json.JSONDecodeError:
                    error_count += 1
                    continue

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

            if exception_collection is not None:
                existing = exception_collection.find_one({'username': username_clean})
                if not existing:
                    exception_collection.insert_one({'username': username_clean, 'added_at': datetime.now()})
                    self.load_exception_list()
                    return True, f"User @{username_clean} added to exception list"
                else:
                    return False, "User already in exception list"
        except Exception as e:
            logger.error(f"Add exception error: {e}")
        return False, "Internal error"

    def remove_exception(self, username):
        try:
            username_clean = username.lower().strip().replace('@', '')
            if exception_collection is not None:
                result = exception_collection.delete_one({'username': username_clean})
                if result.deleted_count > 0:
                    self.load_exception_list()
                    return True, f"User @{username_clean} removed from exception list"
                else:
                    return False, "User not found in exception list"
        except Exception as e:
            logger.error(f"Remove exception error: {e}")
        return False, "Internal error"

    def get_all_exceptions(self):
        try:
            if exception_collection is not None:
                exceptions = exception_collection.find()
                return [item['username'] for item in exceptions]
        except Exception as e:
            logger.error(f"Get exceptions error: {e}")
        return []

bot = AdvancedReplyBot()

@app.route('/')
def dashboard():
    try:
        return render_template('dashboard.html')
    except Exception as e:
        logger.error(f"Failed to render dashboard: {e}")
        return "<h3>Dashboard template missing. Please ensure templates/dashboard.html exists.</h3>", 500

@app.route('/health')
def health():
    mongo_status = "connected" if db is not None else "disconnected"
    return jsonify({'status': 'ok', 'mongodb': mongo_status, 'training_data': len(bot.training_data), 'exceptions': len(bot.exception_list)})

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
        return jsonify({'success': False, 'error': 'Invalid file type. Only .json and .jsonl allowed'}), 400

    try:
        file_content = file.read()

        if files_collection is not None:
            files_collection.insert_one({'filename': filename, 'uploaded_at': datetime.now(), 'size': len(file_content)})

        result = bot.process_uploaded_file(file_content)

        if result.get('success'):
            return jsonify({
                'success': True,
                'message': f"Successfully uploaded! Added {result['added']} new examples",
                'stats': {'added': result['added'], 'errors': result['errors'], 'total': result['total']}
            })
        else:
            return jsonify({'success': False, 'error': result.get('error', 'Unknown error')}), 500

    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/add_data', methods=['POST'])
def add_data():
    data = request.json or {}
    instruction = (data.get('instruction') or '').strip()
    response_text = (data.get('response') or '').strip()

    if not instruction or not response_text:
        return jsonify({'success': False, 'error': 'Both instruction and response required'}), 400

    if bot.add_single_data(instruction, response_text):
        return jsonify({'success': True, 'message': 'Training example added successfully', 'total': len(bot.training_data)})
    else:
        return jsonify({'success': False, 'error': 'Failed to add training example'}), 500

@app.route('/test', methods=['POST'])
def test():
    data = request.json or {}
    message = data.get('message', '') or ''
    username = data.get('username', '') or ''
    is_group = data.get('is_group', False)
    media_type = data.get('media_type', None)

    if not message and not media_type:
        return jsonify({'error': 'Message or media_type required'}), 400

    if username and bot.is_user_excepted(username):
        return jsonify({'message': message, 'response': '[USER IN EXCEPTION LIST - NO REPLY]', 'excepted': True})

    response = bot.get_response(message, username, is_group, media_type)
    return jsonify({'message': message, 'response': response, 'username': username, 'is_group': is_group, 'excepted': False})

@app.route('/exception/add', methods=['POST'])
def add_exception_route():
    data = request.json or {}
    username = (data.get('username') or '').strip()

    if not username:
        return jsonify({'success': False, 'error': 'Username is required'}), 400

    success, message = bot.add_exception(username)

    if success:
        return jsonify({'success': True, 'message': message, 'total': len(bot.exception_list)})
    else:
        return jsonify({'success': False, 'error': message}), 400

@app.route('/exception/remove', methods=['POST'])
def remove_exception_route():
    data = request.json or {}
    username = (data.get('username') or '').strip()

    if not username:
        return jsonify({'success': False, 'error': 'Username is required'}), 400

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
    try:
        return jsonify({
            'total_examples': training_collection.count_documents({}) if training_collection is not None else len(bot.training_data),
            'files_uploaded': files_collection.count_documents({}) if files_collection is not None else 0,
            'exceptions': exception_collection.count_documents({}) if exception_collection is not None else len(bot.exception_list),
            'messages_processed': processed_messages.count_documents({}) if processed_messages is not None else 0,
            'status': 'active' if db is not None else 'database_error'
        })
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({'total_examples': 0, 'files_uploaded': 0, 'exceptions': 0, 'messages_processed': 0, 'status': 'error'})

@app.route('/reload', methods=['POST'])
def reload_data():
    bot.load_training_data()
    bot.load_exception_list()
    return jsonify({'success': True, 'message': 'Data reloaded successfully', 'training': len(bot.training_data), 'exceptions': len(bot.exception_list)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Use debug=False for production (Render)
    app.run(host='0.0.0.0', port=port, debug=False)
