
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import redis
from flask import Flask, jsonify, request, send_file
from werkzeug.utils import secure_filename
from flask_cors import CORS
from crawl4ai import WebCrawler
import faiss
from functools import wraps
import json
import jwt
import os
import time
from prometheus_flask_exporter import PrometheusMetrics
from sentence_transformers import SentenceTransformer
import numpy as np
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import google.generativeai as genai


app = Flask(__name__)
# Initialize Prometheus metrics
metrics = PrometheusMetrics(app, defaults_prefix='my_app')
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)


# Enable CORS for all routes
CORS(app)

index = None
paragraphs = []
model = SentenceTransformer('all-MiniLM-L6-v2')



uri = "mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth"
client = MongoClient(uri, server_api=ServerApi('1'))
app.config['SECRET_KEY'] = 'efa8f62542204fb7a09e081699481658'  # Replace with your own secret key
dbpay = client['Payment']
collectionpay = dbpay['accepted']
dbpaid = client['Store']
collectionpaid = dbpaid['details']
db = client['auth']
collection = db['authenticator']

ALLOWED_EXTENSIONS = {'txt'}

@app.route('/metrics')
def metrics_route():

    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if token and token.startswith('Bearer '):
            token = token.split(' ')[1]  # Strip 'Bearer' from token
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


# Check if the file extension is allowed
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
        

def is_user_paidsubscribed(email):
    # Get the user subscription from the payment collection
    user_subscription = collectionpay.find_one({"email": email, "status": "successful"})
    if user_subscription:
        last_date = user_subscription.get("LastDate", 0)  
        current_time = int(time.time()) 
  
        
        if current_time > last_date:

            return {"error": "Subscription has expired. Please re-subscribe."}, False
        


        return None, True


    return {"error": "User has no active subscription."}, False

@app.route('/uploadpaid', methods=['POST'])
def upload_file_paid():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    email = request.form.get('email')  # Extract email from form data
    print(email)
    print(file.filename)
    
    if not is_user_paidsubscribed(email):
        return jsonify({'error': 'Subscribe to access this'})
    
    if file.filename == '' or not email:
        return jsonify({'error': 'No file selected or email missing'}), 400

    if file and allowed_file(file.filename):
        try:
            # Read the file content in memory (without saving it to disk)
            file_content = file.read().decode('utf-8', errors='ignore')
            
            # Debugging log to check the file content
            print(f"File content: {file_content}")

            # Split the content into paragraphs
            paragraphs = file_content.split("\n\n")

            # Create embeddings for each paragraph
            embeddings = model.encode(paragraphs)
            embeddings_list = embeddings.tolist()

            # Debug log for embeddings
            print("Embeddings:", embeddings_list)

            # Store or update data in Redis
            record = {
                'embeddings': embeddings_list,
                'paragraphs': paragraphs
            }
            
            # Convert the record to JSON and store in Redis using email as the key
            redis_client.set(email, json.dumps(record))

            return jsonify({'message': 'File uploaded and indexed successfully'}), 200

        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500
    else:
        return jsonify({'error': 'Invalid file type. Only .txt files are allowed'}), 400


@app.route('/searchgeminipaid', methods=['POST'])
def geminipaid():
    data = request.json  # Use request.json to handle JSON payload
    email = data.get('email')    
    query = data.get('query', '')
    print(email)

    if not is_user_paidsubscribed(email):
        return jsonify({'error': 'Subscribe to access this'})

    if not query:
        return jsonify({"error": "Query not provided"}), 400

    if not email:
        return jsonify({"error": "Email not provided"}), 400

    # Fetch the user's record from Redis
    user_data = redis_client.get(email)
    if not user_data:
        return jsonify({"error": "User not found"}), 400

    # Deserialize the JSON data
    user_record = json.loads(user_data)
    embeddings_list = user_record.get('embeddings')
    paragraphs = user_record.get('paragraphs')

    if not embeddings_list:
        return jsonify({"error": "Embeddings not found for this user"}), 400

    # Convert the embeddings list back to a numpy array
    embeddings = np.array(embeddings_list)

    # Rebuild the FAISS index
    dimension = embeddings.shape[1]  # Get the dimension of the embeddings
    faiss_index = faiss.IndexFlatL2(dimension)  # Use L2 distance for similarity
    faiss_index.add(embeddings)  # Add embeddings to FAISS index

    # Convert query to embeddings
    query_embedding = model.encode([query])
    _, indices = faiss_index.search(query_embedding, k=5)  # Get top 5 relevant paragraphs

    # Extract the relevant paragraphs from the indices
    closest_match = [paragraphs[idx] for idx in indices[0]]
    context = "\n\n".join(closest_match)

    # Generate the prompt for Gemini
    chat_prompt = (
        f"Here are 5 most relevant paragraphs:\n\n{context}\n\n"
        f"Answer the following question based on this context: {query}"
    )

    # Create a Gemini AI client and get the response
    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    response = gemini_client.generate_response(chat_prompt)

    return jsonify({"answer": response})


@app.route('/getapikey', methods=['POST'])
def get_apikey():
    # Extract email from the POST request body
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Find the user by email in the MongoDB collection
    user = collection.find_one({"email": email})
    print(email)
    # print(user)
    print(user["key"])
    if user and "key" in user:
        return jsonify({"key": user["key"]}), 200

    return jsonify({"error": "API key not found for the user"}), 404


@app.route('/searchgeminipaiduser', methods=['POST'])
def geminipaiduser():
    data = request.json  # Use request.json to handle JSON payload

    email = data.get('email','')    
    query = data.get('query', '')
    api_key = data.get('key','')
    print(email)
    user_data = redis_client.get(email)

    if not is_user_paidsubscribed(email):
        return jsonify({'error':'subscribe to access this'})

    if not query:
        return jsonify({"error": "Query not provided"}), 400

    if not email:
        return jsonify({"error": "Email not provided"}), 400
    
    if not api_key:
        return jsonify({"error": "API not provided"}), 400

    if not user_data:
        return jsonify({"error": "User not found"}), 400

    # Deserialize the JSON data
    user_record = json.loads(user_data)
    embeddings_list = user_record.get('embeddings')
    paragraphs = user_record.get('paragraphs')
    if not user_record:
        return jsonify({"error": "User not found"}), 400
    embeddings_list = user_record.get('embeddings')

    paragraphs = user_record.get('paragraphs')

    if not embeddings_list:
        return jsonify({"error": "Embeddings not found for this user"}), 400

    # Convert the embeddings list back to a numpy array
    embeddings = np.array(embeddings_list)

    # Rebuild the FAISS index
    dimension = embeddings.shape[1]  # Get the dimension of the embeddings
    faiss_index = faiss.IndexFlatL2(dimension)  # Use L2 distance for similarity
    faiss_index.add(embeddings)  # Add embeddings to FAISS index

    # Convert query to embeddings
    query_embedding = model.encode([query])
    _, indices = faiss_index.search(query_embedding, k=5)  # Get top 5 relevant paragraphs

    # Extract the relevant paragraphs from the indices
    closest_match = [paragraphs[idx] for idx in indices[0]]
    context = "\n\n".join(closest_match)

    # Generate the prompt for Gemini
    chat_prompt = (
        f"Here are 5 most relevant paragraphs:\n\n{context}\n\n"
        f"Answer the following question based on this context: {query}"
    )

    # Create a Gemini AI client and get the response
    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    response = gemini_client.generate_response(chat_prompt)

    return jsonify({"answer": response})

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5000)