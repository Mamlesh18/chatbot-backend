from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from crawl4ai import WebCrawler
import faiss
from functools import wraps
import jwt
import os
import time
from prometheus_flask_exporter import PrometheusMetrics
from sentence_transformers import SentenceTransformer
import numpy as np
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor
import pickle
import base64
import random

app = Flask(__name__)
metrics = PrometheusMetrics(app, defaults_prefix='my_app')
CORS(app)


model = SentenceTransformer('all-MiniLM-L6-v2')


app.config['SECRET_KEY'] = 'efa8f62542204fb7a09e081699481658'  

uri = "mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth"
client = MongoClient(uri, server_api=ServerApi('1'))


db = client['ChatterPy']
collectionVector = db['knowledgebase']
collection = db['auth']
collectionPayment = db['payment']



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


@app.route('/v1/knowledgebase/extract', methods=['POST'])
@token_required
def extract_full_links():
    data = request.json
    base_url = data.get('base_url')

    crawler = WebCrawler()
    crawler.warmup()
    
    result = crawler.run(url=base_url)
    internal_links = result.links.get('internal', [])
    full_links = [base_url + link['href'] if link['href'].startswith('/') else link['href'] for link in internal_links]
    
    return jsonify({"links": full_links})


api_urls_paid = ['http://localhost:5006/v1/knowledgebase/process']
@app.route('/v1/knowledgebase/process', methods=['POST'])
@token_required
def process_links():

    data = request.get_json()
    email = request.headers.get('email')
    if not email:
        return jsonify({'message': 'Email not provided'}), 400

    selected_links = data.get('selected_links', [])
    crawler = WebCrawler()
    crawler.warmup()

    def process_single_link(link):
        try:
            result = crawler.run(url=link)
            if result and result.markdown:
                return result.markdown
            else:
                return ""  
        except Exception as e:
            print(f"Error processing link {link}: {e}")
            return ""  

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(process_single_link, selected_links)

    results = [r for r in results if r]

    paragraphs = "\n\n".join(results).strip()  
    if not paragraphs:
        return jsonify({"message": "No content to index"}), 400

    paragraph_list = paragraphs.split("\n\n")
    embeddings = model.encode(paragraph_list)
    dimension = embeddings.shape[1]

    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings))

    faiss_binary = pickle.dumps(index)
    faiss_base64 = base64.b64encode(faiss_binary).decode('utf-8')

    existing_record = collectionVector.find_one({'email': email})

    if existing_record:
            collectionVector.update_one(
                    {'email': email},
                    {'$set': {
                        'paragraphs': paragraphs,
                        'faiss_index': faiss_base64,

                    }}
                )
            return jsonify({'message': 'File updated and re-indexed successfully'}), 200
    else:
            record = {
                    'email': email,
                    'paragraphs': paragraphs,
                    'faiss_index': faiss_base64,
                }
            collectionVector.insert_one(record)
            return jsonify({'message': 'File uploaded and indexed successfully'}), 200

@app.route('/v1/knowledgebase/download-scraped-data', methods=['GET'])
def download_scraped_data():

    email = request.args.get('email')
    if not email:
        return jsonify({'message': 'Email not provided'}), 400

    document = collectionVector.find_one({'email': email})
    if not document:
        return jsonify({"message": "No data found for this email"}), 404

    file_content = document['paragraphs']

    txt_file_path = os.path.join(os.getcwd(), 'scraped_data.txt')
    
    with open(txt_file_path, 'w', encoding='utf-8') as f:
        f.write(file_content)

    return send_file(
        txt_file_path,
        as_attachment=True,
        download_name=f'scraped_data_{email}.txt',  
        mimetype='text/plain'
    )

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
        

@app.route('/v1/knowledgebase/query', methods=['POST'])
@token_required
def gemini():
    data = request.get_json()
    query = data.get('query', '')
    email = request.headers.get('Email')
    
    if not email:
        return jsonify({"error": "Email not provided"}), 400


    user_record = collectionVector.find_one({"email": email})
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

    paragraph_list = paragraphs.split("\n\n")
    closest_match = [paragraph_list[idx] for idx in indices[0]]
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




@app.route('/v1/knowledgebase/apikey', methods=['POST'])
@token_required
def get_apikey():
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = collection.find_one({"email": email})
  
    if user and "key" in user:
        return jsonify({"key": user["key"]}), 200

    return jsonify({"error": "API key not found for the user"}), 404

@app.route('/v1/knowledgebase/apiurl', methods=['POST'])
@token_required
def get_apiurl():
    data = request.get_json()
    email = data.get("email")
    apiurls_free = ['http://localhost:5002/v1/free']
    api_urls_paid = ['http://localhost:5002/v1/paid','http://localhost:5002/v2/paid']
    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = collectionVector.find_one({"email": email})
  

    if user and is_user_paidsubscribed(email):
        random.shuffle(api_urls_paid) 
        return jsonify({"api_url": random.choice(api_urls_paid)}), 200
    else:
        return jsonify({"api_url": apiurls_free}), 200

def is_user_paidsubscribed(email):
    user_subscription = collectionPayment.find_one({"email": email, "status": "successful"})
    if user_subscription:
        last_date = user_subscription.get("LastDate", 0)  
        current_time = int(time.time()) 
        if current_time > last_date:
            return {"error": "Subscription has expired. Please re-subscribe."}, False
        return None, True
    return {"error": "User has no active subscription."}, False


if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5001)
