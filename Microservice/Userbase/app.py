
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from flask import Flask, jsonify, request
from flask_cors import CORS
import pickle
import base64
import time
from sentence_transformers import SentenceTransformer
import google.generativeai as genai


app = Flask(__name__)


CORS(app)


model = SentenceTransformer('all-MiniLM-L6-v2')



uri = "mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth"
client = MongoClient(uri, server_api=ServerApi('1'))



db = client['ChatterPy']
collectionVector = db['knowledgebase']
collectionChatAI = db['chatAI']
collectionPayment = db['payment']



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
    user_subscription = collectionPayment.find_one({"email": email, "status": "successful"})
    if user_subscription:
        last_date = user_subscription.get("LastDate", 0)  
        current_time = int(time.time()) 
        if current_time > last_date:
            return {"error": "Subscription has expired. Please re-subscribe."}, False
        return None, True
    return {"error": "User has no active subscription."}, False




@app.route('/v1/free', methods=['POST'])
def freeUserbase():
    data = request.json 

    email = data.get('email','')    
    query = data.get('query', '')
    api_key = data.get('key','')
    
    if not query:
        return jsonify({"error": "Query not provided"}), 400

    if not email:
        return jsonify({"error": "Email not provided"}), 400
    
    if not api_key:
        return jsonify({"error": "API not provided"}), 400
    
    user_record = collectionVector.find_one({"email": email}) or collectionChatAI.find_one({"email": email})
    if not user_record:
        return jsonify({"error": "User not found"}), 400

    paragraphs = user_record.get('paragraphs')
    faiss_base64 = user_record.get('faiss_index')

    if not faiss_base64 or not paragraphs:
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


@app.route('/v1/paid', methods=['POST'])
def paidUserBase():
    data = request.json  

    email = data.get('email','')    
    query = data.get('query', '')
    api_key = data.get('key','')

    if not is_user_paidsubscribed(email):
        return jsonify({'error':'subscribe to access this'})

    if not query:
        return jsonify({"error": "Query not provided"}), 400

    if not email:
        return jsonify({"error": "Email not provided"}), 400
    
    if not api_key:
        return jsonify({"error": "API not provided"}), 400
    
    user_record = collectionVector.find_one({"email": email})
    if not user_record:
        return jsonify({"error": "User not found"}), 400

    paragraphs = user_record.get('paragraphs')
    faiss_base64 = user_record.get('faiss_index')

    if not faiss_base64 or not paragraphs:
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


if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5002)