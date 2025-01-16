import pickle
import base64
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from flask import Flask, jsonify, request, send_file
from datetime import datetime, timedelta
import faiss
from sentence_transformers import SentenceTransformer
from flask_cors import CORS
import redis
import numpy as np
import google.generativeai as genai


app = Flask(__name__)

# Enable CORS for all routes
CORS(app)
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

# Initialize global variables for FAISS index and content
index = None
paragraphs = []
model = SentenceTransformer('local_model_dir')
uri = "mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth"
app.config['SECRET_KEY'] = 'efa8f62542204fb7a09e081699481658'  # Replace with your own secret key

# Create the client
client = MongoClient(uri, server_api=ServerApi('1'))

# Connect to the database and collection
db = client['auth']
collection = db['authenticator']
dbpay = client['Payment']
collectionpay = dbpay['accepted']
dbpaid = client['Store']
collectionpaid = dbpaid['details']
dbrest = client['Restaurant']
collectionrest = dbrest['payment-details']
ALLOWED_EXTENSIONS = {'txt'}

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
# Check if the file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/uploadpaid', methods=['POST'])
def upload_file_paid():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    email = request.form.get('email')  # Extract email from form data
    print(email)
    print(file.filename)
    
    # if not is_user_paidsubscribed(email):
    #     return jsonify({'error':'subscribe to access this'})
    
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

            # Serialize the FAISS index
            faiss_binary = pickle.dumps(faiss_index)
            faiss_base64 = base64.b64encode(faiss_binary).decode('utf-8')

            # Check if the email already exists in MongoDB
            existing_record = collectionpaid.find_one({'email': email})

            if existing_record:
                collectionpaid.update_one(
                    {'email': email},
                    {'$set': {
                        'file_content': file_content,
                        'faiss_index': faiss_base64,
                        'paragraphs': paragraphs
                    }}
                )
                return jsonify({'message': 'File updated and re-indexed successfully'}), 200
            else:
                record = {
                    'email': email,
                    'file_content': file_content,
                    'faiss_index': faiss_base64,
                    'paragraphs': paragraphs
                }
                collectionpaid.insert_one(record)
                return jsonify({'message': 'File uploaded and indexed successfully'}), 200

        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500
    else:
        return jsonify({'error': 'Invalid file type. Only .txt files are allowed'}), 400


@app.route('/searchgeminipaid', methods=['POST'])
def geminipaid():
    data = request.json
    email = data.get('email')
    query = data.get('query', '')

    # if not is_user_paidsubscribed(email):
    #     return jsonify({'error':'subscribe to access this'})

    if not query:
        return jsonify({"error": "Query not provided"}), 400

    if not email:
        return jsonify({"error": "Email not provided"}), 400

    user_record = collectionpaid.find_one({"email": email})
    if not user_record:
        return jsonify({"error": "User not found"}), 400

    paragraphs = user_record.get('paragraphs')
    faiss_base64 = user_record.get('faiss_index')

    if not faiss_base64:
        return jsonify({"error": "FAISS index not found for this user"}), 400

    # Deserialize the FAISS index
    faiss_binary = base64.b64decode(faiss_base64)
    faiss_index = pickle.loads(faiss_binary)

    # Convert query to embeddings
    query_embedding = model.encode([query])
    _, indices = faiss_index.search(query_embedding, k=5)

    # Extract the relevant paragraphs
    closest_match = [paragraphs[idx] for idx in indices[0]]
    context = "\n\n".join(closest_match)

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
