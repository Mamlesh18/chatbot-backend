import os
import numpy as np
import faiss
from flask import Flask, request, jsonify
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from werkzeug.utils import secure_filename
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
from pymongo import MongoClient
from bson import ObjectId
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
import os


# MongoDB URI and client setup
uri = "mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth"
client = MongoClient(uri, server_api=ServerApi('1'))
db = client['Store']
collection = db['details']

# Allowed file extensions for upload
ALLOWED_EXTENSIONS = {'txt'}

# Initialize FAISS, Sentence Transformer and other global variables
index = None
paragraphs = []
model = SentenceTransformer('all-MiniLM-L6-v2')

# Check if the file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Class to interact with Gemini API
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
        
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    email = request.form['email']

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

            # Create embeddings for each paragraph and initialize FAISS index
            embeddings = model.encode(paragraphs)
            dimension = embeddings.shape[1]  # Get the dimension of the embeddings
            faiss_index = faiss.IndexFlatL2(dimension)  # Use L2 distance for similarity
            faiss_index.add(np.array(embeddings))  # Add embeddings to FAISS index

            embeddings_list = embeddings.tolist()
            print("here it is -------->", embeddings_list)

            # Save the embeddings and paragraphs into MongoDB
            record = {
                'email': email,
                'file_content': file_content,
                'embeddings': embeddings_list,  
            }

            collection.insert_one(record)

            return jsonify({'message': 'File uploaded and indexed successfully'}), 200
        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500
    else:
        return jsonify({'error': 'Invalid file type. Only .txt files are allowed'}), 400



@app.route('/searchgemini', methods=['POST'])
def gemini():
    data = request.get_json()
    query = data.get('query', '')
    email = request.headers.get('Email')

    if not query:
        return jsonify({"error": "Query not provided"}), 400

    if not email:
        return jsonify({"error": "Email not provided"}), 400

    # Fetch the user's record from MongoDB to get the embeddings and paragraphs
    user_record = collection.find_one({"email": email})
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
    app.run(debug=True, port=5000)

