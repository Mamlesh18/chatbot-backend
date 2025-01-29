from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from flask import Flask, jsonify, request, Response
import faiss
from sentence_transformers import SentenceTransformer
from flask_cors import CORS
import numpy as np
import jwt
from functools import wraps
import json
import pickle
import base64
import google.generativeai as genai
from prometheus_flask_exporter import PrometheusMetrics
import time


app = Flask(__name__)
# Initialize Prometheus metrics
metrics = PrometheusMetrics(app, defaults_prefix='my_app')

CORS(app)


model = SentenceTransformer('all-MiniLM-L6-v2')
uri = "mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth"
app.config['SECRET_KEY'] = 'efa8f62542204fb7a09e081699481658'  # Replace with your own secret key

# Create the client
client = MongoClient(uri, server_api=ServerApi('1'))
ALLOWED_EXTENSIONS = {'txt'}
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

dbrest = client['Restaurant']
collectionrest = dbrest['payment-details']
collectionorders = dbrest['orders']
collectionrestinfo = dbrest['restinfo']
dbauth = client['auth']
collectionAuth = dbauth['authenticator']

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
        
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/uploadfile', methods=['POST'])
@token_required
def upload_file():

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    email = request.form.get('email')  # Extract email from form data
    print(email)
    print(file.filename)
    

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
            existing_record = collectionrestinfo.find_one({'email': email})

            if existing_record:
                collectionrestinfo.update_one(
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
                collectionrestinfo.insert_one(record)
                return jsonify({'message': 'File uploaded and indexed successfully'}), 200

        except Exception as e:
            return jsonify({'error': f'An error occurred: {str(e)}'}), 500
    else:
        return jsonify({'error': 'Invalid file type. Only .txt files are allowed'}), 400


@app.route('/searchgeminirest', methods=['POST'])
@token_required
def geminirest():
    
    data = request.json
    email = data.get('email')
    query = data.get('query', '')
    print("email",email)
    print("query",query)

    # if not is_user_paidsubscribed(email):
    #     return jsonify({'error':'subscribe to access this'})

    if not query:
        print("1 - query",query)

        return jsonify({"error": "Query not provided"}), 400

    if not email:
        print("2 - email",email)
        return jsonify({"error": "Email not provided"}), 400
    print("3 ------------ question")
    user_record = collectionrestinfo.find_one({"email": email})
    if not user_record:
        return jsonify({"error": "User not found"}), 400
    print("4 ------------ question")
    paragraphs = user_record.get('paragraphs')
    faiss_base64 = user_record.get('faiss_index')
    print("5 ------------ question")
    if not faiss_base64:
        return jsonify({"error": "FAISS index not found for this user"}), 400

    # Deserialize the FAISS index
    faiss_binary = base64.b64decode(faiss_base64)
    faiss_index = pickle.loads(faiss_binary)
    print("6 ------------ question")
    # Convert query to embeddings
    query_embedding = model.encode([query])
    _, indices = faiss_index.search(query_embedding, k=5)
    print("7 ------------ question")
    # Extract the relevant paragraphs
    closest_match = [paragraphs[idx] for idx in indices[0]]
    context = "\n\n".join(closest_match)
    print("8 ------------ question")
    chat_prompt = ( 
    f"You are a restaurant chatbot. Your purpose is to assist users with questions specifically related to restaurants, food, or food orders. "
    f"Do not answer questions that are unrelated to this context. Stay focused on restaurant and food-related topics.\n\n"
    f"Here are 5 most relevant paragraphs for reference:\n\n{context}\n\n"
    f"Answer the following question based on this context: {query}. "
    f"If the user asks you to order any food, respond by suggesting complementary dishes to enhance their meal. For example:\n"
    f"- If the user orders biryani, suggest adding a sweet dish like gulab jamun or rasmalai.\n"
    f"- If the user orders pizza, suggest adding a cold drink to go with it.\n"
    f"For each dish the user mentions, ask about the next dish they would like to add to their order.\n\n"
    f"IMPORTANT: Answer only if the user is asking a restaurant or food-related question. If the user asks a question unrelated to restaurants, food, or food orders, politely decline to answer and remind them that you are a restaurant chatbot."
)

    print("9 ------------ question")

    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    print("10 ------------ question")

    response = gemini_client.generate_response(chat_prompt)
    print("11 ------------ question")

    return jsonify({"answer": response})


@app.route('/restorder', methods=['POST'])
@token_required
def restorder():    

    data = request.get_json()
    query = data.get('query', '')
    print("3 ------------ question")
    print("5 ------------ question")

    chat_prompt = (
        f"You are a restaurant chatbot focused on food orders.\n\n"
        f"Determine if the following question contains any intent to order food. "
        f"If the user wants to order food, return only a JSON object in the format {{'food': '<food mentioned by user>', 'price': <integer price of the food>}}. "
        f"Do not mention any other words or add explanations. like ```json``` strictly. Only return the json formatted answer. "
        f"If no food order intent is present, return only the boolean value False. Here is the Query sent by user: {query}"
    )


    print("6 ------------ question")

    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    print("7 ------------ question")

    response = gemini_client.generate_response(chat_prompt)
    print("8 ------------ question")
    print("answer------------------------>>>>",response)

    try:
        # Attempt to parse the response into a proper JSON object
        parsed_response = json.loads(response)
        print("answer 1------------------------>>>>",response)

        return jsonify({"answer": parsed_response})
    except json.JSONDecodeError:
        print("answer 2------------------------>>>>",response)

        return jsonify({"answer": response}) 
    

# SSE Route for streaming updates to the client
@app.route('/stream-updates')
def stream_updates():
    email = request.args.get('email')  # Get email from query parameters
    if not email:
        return Response("data: {}\n\n", content_type='text/event-stream')

    def stream():
        latest_data = list(collectionorders.find({'email': email}, {"_id": 0}))
        while True:
            time.sleep(2)  # Check for updates every 2 seconds
            current_data = list(collectionorders.find({'email': email}, {"_id": 0}))
            if current_data != latest_data:  # If new data is found
                latest_data = current_data
                yield f"data: {json.dumps(latest_data)}\n\n"  # Send updated data as SSE

    return Response(stream(), content_type='text/event-stream')

# REST API to fetch all data
@app.route('/get-all-orders', methods=['GET'])
def get_all_orders():
    try:
        email = request.args.get('email')  # Get email from query parameters
        if not email:
            return jsonify({'error': 'Email is required'}), 400

        # Find orders by email
        orders = list(collectionorders.find({'email': email}, {"_id": 0}))

        if not orders:
            return jsonify([]), 200

        return jsonify(orders)    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/v1/rest/api', methods=['POST'])
def get_apikey():
    # Extract email from the POST request body
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Find the user by email in the MongoDB collection
    user = collectionAuth.find_one({"email": email})
    print(email)
    # print(user)
    print(user["key"])
    if user and "key" in user:
        return jsonify({"key": user["key"]}), 200

    return jsonify({"error": "API key not found for the user"}), 404



@app.route('/v1/restpaid', methods=['POST'])
def geminipaiduser():
    data = request.json  # Use request.json to handle JSON payload

    email = data.get('email','')    
    query = data.get('query', '')
    api_key = data.get('key','')
    print(email)

    # if not is_user_paidsubscribed(email):
    #     return jsonify({'error':'subscribe to access this'})

    if not query:
        return jsonify({"error": "Query not provided"}), 400

    if not email:
        return jsonify({"error": "Email not provided"}), 400
    
    if not api_key:
        return jsonify({"error": "API not provided"}), 400
    
    user_record = collectionrestinfo.find_one({"email": email})
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
    f"You are a restaurant chatbot. Your purpose is to assist users with questions specifically related to restaurants, food, or food orders. "
    f"Do not answer questions that are unrelated to this context. Stay focused on restaurant and food-related topics.\n\n"
    f"Here are 5 most relevant paragraphs for reference:\n\n{context}\n\n"
    f"Answer the following question based on this context: {query}. "
    f"If the user asks you to order any food, respond by suggesting complementary dishes to enhance their meal. For example:\n"
    f"- If the user orders biryani, suggest adding a sweet dish like gulab jamun or rasmalai.\n"
    f"- If the user orders pizza, suggest adding a cold drink to go with it.\n"
    f"For each dish the user mentions, ask about the next dish they would like to add to their order.\n\n"
    f"IMPORTANT: Answer only if the user is asking a restaurant or food-related question. If the user asks a question unrelated to restaurants, food, or food orders, politely decline to answer and remind them that you are a restaurant chatbot."
)


    # Create a Gemini AI client and get the response
    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    response = gemini_client.generate_response(chat_prompt)
    checkfood = checkorder(query)    
    return jsonify({"answer": response,"checkfood":checkfood})
# Function to process the food order query
import json

def checkorder(query):
    chat_prompt = (
        f"You are a restaurant chatbot focused on food orders.\n\n"
        f"Determine if the following question contains any intent to order food. "
        f"If the user wants to order food, return only a JSON object in the format {{'food': '<food mentioned by user>', 'price': <integer price of the food>}}. "
        f"Do not mention any other words or add explanations. like ```json``` strictly. Only return the json formatted answer. "
        f"If no food order intent is present, return only the boolean value False. Here is the Query sent by user: {query}"
    )


    print("6 ------------ question")

    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    print("7 ------------ question")

    response = gemini_client.generate_response(chat_prompt)
    print("8 ------------ question")
    print("answer------------------------>>>>",response)

    try:
        # Attempt to parse the response into a proper JSON object
        parsed_response = json.loads(response)
        print("answer 1------------------------>>>>",response)

        return parsed_response
    except json.JSONDecodeError:
        print("answer 2------------------------>>>>",response)

        return response

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5004)
