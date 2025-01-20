from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import redis
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
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import google.generativeai as genai


app = Flask(__name__)
# Initialize Prometheus metrics
metrics = PrometheusMetrics(app, defaults_prefix='my_app')


# Enable CORS for all routes
CORS(app)

index = None
paragraphs = []
# model = None
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

scraped_data_dict = {}
temporary_storage = {}
# Step 1: Extract full links synchronously
@app.route('/extractlinks', methods=['POST'])
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

# Step 2: Process the selected links and store content in a dictionary
from concurrent.futures import ThreadPoolExecutor
@app.route('/process-links', methods=['POST'])
@token_required
def process_links():
    global scraped_data_dict  # Store scraped data globally for each email

    data = request.get_json()
    email = request.headers.get('email')
    if not email:
        return jsonify({'message': 'Email not provided'}), 400

    scraped_data_dict[email] = {'paragraphs': "", 'index': None}

    selected_links = data.get('selected_links', [])
    crawler = WebCrawler()
    crawler.warmup()

    def process_single_link(link):
        try:
            result = crawler.run(url=link)
            if result and result.markdown:
                return result.markdown
            else:
                return ""  # Return an empty string if result or result.markdown is None
        except Exception as e:
            print(f"Error processing link {link}: {e}")
            return ""  # Return an empty string in case of an error

    # Use a thread pool to process the links in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(process_single_link, selected_links)

    # Filter out any empty results
    results = [r for r in results if r]

    paragraphs = "\n\n".join(results).strip()  # Combine results from all links
    scraped_data_dict[email]['paragraphs'] = paragraphs

    if not paragraphs:
        return jsonify({"message": "No content to index"}), 400

    # Split paragraphs into a list for indexing
    paragraph_list = paragraphs.split("\n\n")
    embeddings = model.encode(paragraph_list)
    dimension = embeddings.shape[1]

    # Initialize FAISS index
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings))

    # Update the index in the dictionary
    scraped_data_dict[email]['index'] = index

    return jsonify({
        "message": "FAISS index created",
    })

@app.route('/download-scraped-data', methods=['GET'])
def download_scraped_data():
    email = request.args.get('email')
    if not email:
        return jsonify({'message': 'Email not provided'}), 400

    # Check if the email exists in the dictionary
    if email not in scraped_data_dict or 'paragraphs' not in scraped_data_dict[email]:
        return jsonify({"message": "No data found for this email"}), 404

    # Get the scraped paragraphs for the email
    paragraphs = scraped_data_dict[email]['paragraphs']
    
    # Create a temporary .txt file from the paragraphs
    txt_file_path = os.path.join(os.getcwd(), 'scraped_data.txt')
    
    # Use 'utf-8' encoding to avoid encoding errors
    with open(txt_file_path, 'w', encoding='utf-8') as f:
        f.write(paragraphs)

    return send_file(txt_file_path, as_attachment=True)

def is_user_subscribed(email):
    # Get the user subscription from the payment collection
    user_subscription = collectionpay.find_one({"email": email, "status": "successful"})
    print("i came here - 1")
    if user_subscription:
        # Check if the subscription has expired by comparing LastDate with current time
        last_date = user_subscription.get("LastDate", 0)  # Default to 0 if LastDate doesn't exist
        current_time = int(time.time())  # Get current time in Unix timestamp
        print("i came here - 2")
        print("current",current_time)

        print("last",last_date)

        
        # If the current time is greater than the LastDate, subscription has expired
        if current_time > last_date:
            print("i came here - 3")

            return {"error": "Subscription has expired. Please re-subscribe."}, False
        
        # If the subscription is still valid
        print("i came here - 4")

        return None, True
    
    # If no successful subscription is found
    print("i came here - 5")

    return {"error": "User has no active subscription."}, False
def check_and_increment_count(email):
    # Check subscription status
    error_response, is_subscribed = is_user_subscribed(email)
    print(f"Subscription status: {is_subscribed}, Error: {error_response}")

    if is_subscribed:
        print("User is subscribed, proceed with operation.")
        return None, True

    elif not is_subscribed:
        print("User is not subscribed, checking free trial count.")
        user = collection.find_one({"email": email})
        if user is None:
            print("User not found in the database.")
            return {"error": "User not found"}, False

        count = user.get("count", 0)
        print(f"Free trial count: {count}")

        if count >= 5:
            print("Free trial limit reached.")
            return {"error": "Free message limit reached. Please subscribe."}, False

        # Increment the count for free trial and update the user record
        print("Incrementing free trial count.")
        collection.update_one({"email": email}, {"$inc": {"count": 1}})
        return None, True


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
@app.route('/searchgemini', methods=['POST'])
@token_required
def gemini():
    data = request.get_json()
    query = data.get('query', '')
    email = request.headers.get('Email')
    
    if not email:
        return jsonify({"error": "Email not provided"}), 400

    # Check if the email has scraped data
    if email not in scraped_data_dict:
        return jsonify({"error": "No scraped data found for this email"}), 404

    # Retrieve the paragraphs and index for the given email
    user_data = scraped_data_dict[email]
    paragraphs = user_data.get('paragraphs', '')
    index = user_data.get('index', None)

    if not index:
        return jsonify({"message": "FAISS index not created"}), 400

    # Check user's message count and increment if under the limit
    error, success = check_and_increment_count(email)
    if not success:
        return jsonify(error), 403    # Forbidden when limit is reached

    # Proceed with the regular FAISS search and response generation
    query_embedding = model.encode([query])
    _, indices = index.search(query_embedding, k=5)

    paragraph_list = paragraphs.split("\n\n")
    closest_match = [paragraph_list[idx] for idx in indices[0]]
    context = "\n\n".join(closest_match)

    chat_prompt = (
        f"Here are 5 most relevant paragraphs:\n\n{context}\n\n"
        f"Answer the following question based on this context: {query}"
    )

    # Replace this with your actual Gemini API call
    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    response = gemini_client.generate_response(chat_prompt)
    
    return jsonify({"answer": response})




if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5001)
