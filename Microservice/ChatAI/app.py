
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from flask import Flask, jsonify, request
from flask_cors import CORS
import faiss
from functools import wraps
import pickle
import base64
import json
import jwt
import time
from prometheus_flask_exporter import PrometheusMetrics
from sentence_transformers import SentenceTransformer
import numpy as np
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import google.generativeai as genai


app = Flask(__name__)

metrics = PrometheusMetrics(app, defaults_prefix='my_app')

CORS(app)


model = SentenceTransformer('all-MiniLM-L6-v2')



uri = "mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth"
client = MongoClient(uri, server_api=ServerApi('1'))
app.config['SECRET_KEY'] = 'efa8f62542204fb7a09e081699481658' 


db = client['ChatterPy']
collectionChatAI = db['chatAI']
collection = db['auth']


ALLOWED_EXTENSIONS = {'txt','pdf'}

@app.route('/metrics')
def metrics_route():

    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if token and token.startswith('Bearer '):
            token = token.split(' ')[1]  
        else:
            return jsonify({'Alert!': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({'Message': 'Token has expired'}), 403
        except jwt.InvalidTokenError:
            return jsonify({'Message': 'Invalid token'}), 403
        return f(*args, **kwargs)
    return decorated


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



class GeminiAI:
    def __init__(self, api_key, model_name):
        self.api_key = api_key
        self.model_name = model_name
        genai.configure(api_key=self.api_key)

    def generate_response(self, prompt):
        try:
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error occurred: {e}"
        
@app.route('/v1/chatai/upload', methods=['POST'])
def upload_file_paid():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    email = request.form.get('email')  

    if file.filename == '' or not email:
        return jsonify({'error': 'No file selected or email missing'}), 400

    if file and allowed_file(file.filename):
        try:
            file_content = file.read().decode('utf-8', errors='ignore')
            print(f"File content: {file_content}")

            paragraphs = file_content.split("\n\n")
            embeddings = model.encode(paragraphs)

            dimension = embeddings.shape[1]
            faiss_index = faiss.IndexFlatL2(dimension)
            faiss_index.add(np.array(embeddings))

            faiss_binary = pickle.dumps(faiss_index)
            faiss_base64 = base64.b64encode(faiss_binary).decode('utf-8')

            existing_record = collectionChatAI.find_one({'email': email})

            if existing_record:
                collectionChatAI.update_one(
                    {'email': email},
                    {'$set': {
                        'faiss_index': faiss_base64,
                        'paragraphs': paragraphs
                    }}
                )
                return jsonify({'message': 'File updated and re-indexed successfully'}), 200
            else:
                record = {
                    'email': email,
                    'faiss_index': faiss_base64,
                    'paragraphs': paragraphs
                }
                collectionChatAI.insert_one(record)
                return jsonify({'message': 'File uploaded and indexed successfully'}), 200

        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500
    else:
        return jsonify({'error': 'Invalid file type. Only .txt files are allowed'}), 400


@app.route('/v1/chatai/search', methods=['POST'])
def geminipaid():
    data = request.json
    email = data.get('email')
    query = data.get('query', '')


    if not query:
        return jsonify({"error": "Query not provided"}), 400

    if not email:
        return jsonify({"error": "Email not provided"}), 400

    user_record = collectionChatAI.find_one({"email": email})
    if not user_record:
        return jsonify({"error": "User not found"}), 400

    paragraphs = user_record.get('paragraphs')
    faiss_base64 = user_record.get('faiss_index')

    if not faiss_base64:
        return jsonify({"error": "FAISS index not found for this user"}), 400

    faiss_binary = base64.b64decode(faiss_base64)
    faiss_index = pickle.loads(faiss_binary)

    query_embedding = model.encode([query])
    _, indices = faiss_index.search(query_embedding, k=5)

    closest_match = [paragraphs[idx] for idx in indices[0]]
    context = "\n\n".join(closest_match)

    chat_prompt = (
        f"Here are 5 most relevant paragraphs:\n\n{context}\n\n"
        f"Answer the following question based on this context: {query}"
    )

    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    response = gemini_client.generate_response(chat_prompt)

    return jsonify({"answer": response})



@app.route('/v1/chatai/getapikey', methods=['POST'])
def get_apikey():
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = collection.find_one({"email": email})
    
    if user and "key" in user:
        return jsonify({"key": user["key"]}), 200

    return jsonify({"error": "API key not found for the user"}), 404


@app.route('/v1/chatai/apiurl', methods=['POST'])
def get_apiurl():
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = collectionChatAI.find_one({"email": email})
  
    if user and "api_url" in user:
        return jsonify({"api_url": user["api_url"]}), 200

    return jsonify({"error": "API key not found for the user"}), 404



if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5002)