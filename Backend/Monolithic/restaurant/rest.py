import uuid
import random
import string
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import pickle
import base64
from flask import Flask, jsonify, request, send_file, Response
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask_cors import CORS
from prometheus_flask_exporter import PrometheusMetrics
import time
import jwt
from functools import wraps
import smtplib
import time
import random
import redis
import json
from email.mime.multipart import MIMEMultipart
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from crawl4ai import WebCrawler
import faiss
from sentence_transformers import SentenceTransformer
import numpy as np
import google.generativeai as genai
import os
import razorpay
import hmac
import hashlib

app = Flask(__name__)
# Initialize Prometheus metrics
metrics = PrometheusMetrics(app, defaults_prefix='my_app')
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

# Enable CORS for all routes
CORS(app)

# Initialize global variables for FAISS index and content
index = None
paragraphs = []
model = None
# model = SentenceTransformer('local_model_dir')
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
collectionorders = dbrest['orders']
dbknow = client['Knowledgebase']
collectionknow = dbknow['extract-details']
# Allowed file extensions for upload
ALLOWED_EXTENSIONS = {'txt'}
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

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


@app.route('/protected', methods=['GET'])
@token_required
def protected():
    return jsonify({'message': 'This is protected data'})


# Check if the file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
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
@app.route('/process-links', methods=['POST'])
@token_required
def process_links():
    global scraped_data_dict  # Store scraped data globally for each email

    data = request.get_json()
    email = request.headers.get('email')
    if not email:
        return jsonify({'message': 'Email not provided'}), 400

    if email not in scraped_data_dict:
        scraped_data_dict[email] = {'paragraphs': "", 'index': None}

    selected_links = data.get('selected_links', [])
    crawler = WebCrawler()
    crawler.warmup()

    # Process each link and append its content directly to paragraphs
    for link in selected_links:
        result = crawler.run(url=link)
        scraped_data_dict[email]['paragraphs'] += f"{result.markdown}\n\n"

    paragraphs = scraped_data_dict[email]['paragraphs'].strip()  # Remove trailing newlines
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
    with open(txt_file_path, 'w') as f:
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



# Function to generate a random 64-bit key
def generate_random_key(length=64):

    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

@app.route('/auth', methods=['POST'])
def auth():
    try:
        # Parse incoming JSON data
        data = request.json
        if not data:
            raise ValueError("No JSON data provided")
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if not username or not email or not password:
            return jsonify({"error": "Username, email, and password are required"}), 400

        # Check if the email already exists in the database
        existing_user = collection.find_one({"email": email})
        if existing_user:
            return jsonify({"error": "Email already exists"}), 409  # 409 Conflict

        # Create a new document
        document = {
            "uuid": str(uuid.uuid4()),  # Generate a random UUID
            "username": username,  # Use provided username
            "email": email,  # Use provided email
            "password": password,  # Use provided password
            "key": generate_random_key(),  # Generate a random 64-bit key
            "isNew": True,  # Set isNew to True initially
            "count": 0,
            "create_at": datetime.now(),
            "jwttoken": False
        }

        # Insert the document into the collection
        collection.insert_one(document)
        return jsonify({"message": "Document inserted successfully", "document": document}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


from functools import wraps

@app.route('/login', methods=['POST'])
def login():
    try:
        # Parse incoming JSON data
        data = request.json
        if not data:
            raise ValueError("No JSON data provided")

        # Extract username/email and password
        identifier = data.get('username') or data.get('email')  # Accept either username or email
        password = data.get('password')

        if not identifier or not password:
            return jsonify({"error": "Username/email and password are required"}), 400

        # Find the user in the database
        query = {"$or": [{"username": identifier}, {"email": identifier}]}
        user = collection.find_one(query)

        if not user:
            return jsonify({"error": "Invalid username/email or password"}), 401

        # Verify the password (here, we are comparing plain-text; you should hash passwords in production)
        if user['password'] != password:
            return jsonify({"error": "Invalid username/email or password"}), 401

        # Generate JWT token
        token_payload = {
            "uuid": user['uuid'],
            "username": user['username'],
            "email": user['email'],
            "exp": datetime.utcnow() + timedelta(hours=24)  # Token expires in 1 hour
        }
        token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm="HS256")

        # Update the user's `jwttoken` field in the database
        collection.update_one({"_id": user["_id"]}, {"$set": {"jwttoken": token}})

        # Return the token to the client
        return jsonify({"message": "Login successful", "token": token}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def send_otp_email(email, otp):
    sender_email = "mamleshsurya6@gmail.com"  # Replace with your email
    password = "iffc dxur pbkt fsir"  # Replace with your email app password
    receiver_email = email

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = "Your OTP for Authentication"
    msg.attach(MIMEText(f"Your OTP code for ChatBot: {otp}", 'plain'))

    try:
        # Send the email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Start TLS encryption
        server.login(sender_email, password)  # Log in to the server
        server.send_message(msg)  # Send the email
        server.quit()  # Close the server connection

        print("OTP sent successfully!")
    except Exception as e:
        print(f"Failed to send OTP email: {e}")

otp = str(random.randint(1000, 9999))  # Generate a 4-digit OTP

@app.route('/send_otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    send_otp_email(email, otp)

    return jsonify({"message": "OTP sent to your email"}), 200

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    user_otp = data.get("otp")

    correct_otp = otp

    if user_otp == correct_otp:
        return jsonify({"message": "OTP verified successfully"}), 200
    else:
        return jsonify({"error": "Invalid OTP"}), 400

@app.route('/uploadfile', methods=['POST'])
@token_required
def upload_file():
    print("1 ------------ upload")

    global index, paragraphs  # Make the content global for FAISS indexing

    if 'file' not in request.files:
        return jsonify({"message": "No file part in the request"}), 400
    
    file = request.files['file']
    print("1 ------------ upload")
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400
        print("1 ------------ upload")
    if file:
        # Read the file content
        content = file.read().decode('utf-8')

        # Split the content into paragraphs
        paragraphs = content.split("\n\n")
        print("1 ------------ upload")
        # Encode the paragraphs
        embeddings = model.encode(paragraphs)
        dimension = embeddings.shape[1]
        print("1 ------------ upload")
        # Initialize FAISS index
        index = faiss.IndexFlatL2(dimension)
        index.add(np.array(embeddings))
        print("1 ------------ upload")
        return jsonify({"message": "File processed and FAISS index created", "paragraphs": paragraphs})
global_context = ""

@app.route('/searchgeminirest', methods=['POST'])
@token_required
def geminirest():
    print("1 ------------ question")
    global index, paragraphs

    if not index:
        return jsonify({"message": "FAISS index not created"})
    print("2 ------------ question")

    data = request.get_json()
    query = data.get('query', '')
    print("3 ------------ question")

    # Encode the query and search the FAISS index
    query_embedding = model.encode([query])
    _, indices = index.search(query_embedding, k=5)
    print("4 ------------ question")

    closest_match = [paragraphs[idx] for idx in indices[0]]
    global_context  = "\n\n".join(closest_match)
    print("5 ------------ question")

    chat_prompt = (
    f"You are a restaurant chatbot. Your purpose is to assist users with questions specifically related to restaurants, food, or food orders. "
    f"Do not answer questions that are unrelated to this context. Stay focused on restaurant and food-related topics.\n\n"
    f"Here are 5 most relevant paragraphs for reference:\n\n{global_context}\n\n"
    f"Answer the following question based on this context: {query}. "
    f"If the user asks you to order any food, respond by suggesting complementary dishes to enhance their meal. For example:\n"
    f"- If the user orders biryani, suggest adding a sweet dish like gulab jamun or rasmalai.\n"
    f"- If the user orders pizza, suggest adding a cold drink to go with it.\n"
    f"For each dish the user mentions, ask about the next dish they would like to add to their order.\n\n"
    f"IMPORTANT: Answer only if the user is asking a restaurant or food-related question. If the user asks a question unrelated to restaurants, food, or food orders, politely decline to answer and remind them that you are a restaurant chatbot."
)

    print("6 ------------ question")

    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    print("7 ------------ question")

    response = gemini_client.generate_response(chat_prompt)
    print("8 ------------ question")

    return jsonify({"answer": response})


@app.route('/restorder', methods=['POST'])
@token_required
def restorder():
    print("1 ------------ question")
    global index, paragraphs

    if not index:
        return jsonify({"message": "FAISS index not created"})
    print("2 ------------ question")

    data = request.get_json()
    query = data.get('query', '')
    print("3 ------------ question")
    print("5 ------------ question")

    chat_prompt = (
        f"You are a restaurant chatbot focused on food orders. Use the following context to identify food order intent:\n\n{global_context}\n\n"
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
# Setup Razorpay client
razorpay_client = razorpay.Client(auth=("rzp_test_ls8UyEU66pm1Y6", "nATjdwiqiKuKDqJLxMluczid"))
razorpay_secret = "nATjdwiqiKuKDqJLxMluczid"  # Razorpay key secret

subscription_plans = {
    "basic": 10000,   # 10000 paise = ₹100.00
    "standard": 20000,  # 20000 paise = ₹200.00
    "premium": 39900   # 39900 paise = ₹399.00
}


@app.route('/create-order', methods=['POST'])
def create_order():
    try:
        # Get data from the request (React frontend will send this)
        data = request.json
        user_email = data.get('email')

      
        subscription_type = data.get('subscription_type')

        if subscription_type not in subscription_plans:
            return jsonify({'error': 'Invalid subscription type'}), 400

        # Create Razorpay order
        order_data = {
            "amount": subscription_plans[subscription_type],  # Amount in paise
            "currency": "INR",
            "receipt": f"receipt_{user_email}",
        }
        payment = razorpay_client.order.create(data=order_data)

        # Save the order in MongoDB with status 'created'
        collectionpay.insert_one({
            "email": user_email,
            "subscription_type": subscription_type,
            "amount": subscription_plans[subscription_type],
            "payment_id": payment['id'],
            "status": "created",
            "createAt": int(time.time()),
            "LastDate": 0
        })

        # Return the payment order details to React frontend
        return jsonify(payment)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    try:
        data = request.json
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_signature = data.get('razorpay_signature')

        # Verify the payment signature using HMAC SHA256
        generated_signature = hmac.new(
            bytes(razorpay_secret, 'utf-8'),
            msg=bytes(razorpay_order_id + "|" + razorpay_payment_id, 'utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()

        if generated_signature == razorpay_signature:
            # Fetch the order from MongoDB to get the subscription type
            order = collectionpay.find_one({"payment_id": razorpay_order_id})
            if order:
                subscription_type = order.get('subscription_type')

                # Calculate the LastDate based on subscription type
                if subscription_type == 'basic':
                    last_date = datetime.now() + timedelta(days=1)
                elif subscription_type == 'standard':
                    last_date = datetime.now() + timedelta(days=7)
                elif subscription_type == 'premium':
                    last_date = datetime.now() + timedelta(days=30)
                else:
                    return jsonify({'error': 'Invalid subscription type'}), 400

                # Update the order status and set the LastDate in MongoDB
                collectionpay.update_one(
                    {"payment_id": razorpay_order_id},
                    {"$set": {
                        "status": "successful",
                        "razorpay_payment_id": razorpay_payment_id,
                        "LastDate": int(last_date.timestamp())
                    }}
                )

                return jsonify({'status': 'Payment verified successfully'})
            else:
                return jsonify({'error': 'Order not found'}), 404
        else:
            # Signature mismatch, payment failed
            return jsonify({'error': 'Signature verification failed'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500



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


@app.route('/searchgeminilaw', methods=['POST'])
def geminirestlaw():
    print("1 ------------ question")

    data = request.get_json()
    query = data.get('query', '')
    print("3 ------------ question")

    chat_prompt = (
            """
        RESIDENTIAL RENTAL AGREEMENT
        This agreement made at #city, #state on this #ddmmyy between #landlordname, residing at #landlordaddress1, #lordaddressline2, #lordcity, #lordstate, #lordpincode hereinafter referred to as the `LESSOR` of the One Part AND #tenantname, residing at  #tenantaddress1, #tenantaddressline2, #tencity, #tenstate, #tenpincode hereinafter referred to as the `LESSEE` of the other Part;
        WHEREAS the Lessor is the lawful owner of, and otherwise well sufficiently entitled to #leasepropertyaddress1, #leaseaddressline2, #leasecity, #leasestate, #leasepincode falling in the category, #independenthouse / #apartment / #farmhouse / #residentialproperty and comprising of #xbedrooms, #xbathrooms, #xcarparks with an extent of #xxxxsquarefeet hereinafter referred to as the `said premises`. 
        AND WHEREAS at the request of the Lessee, the Lessor has agreed to let the said premises to the tenant for a term of #leaseterm commencing from #leasestartdate in the manner hereinafter appearing. 

        NOW THIS AGREEMENT WITNESSETH AND IT IS HEREBY AGREED BY AND BETWEEN THE PARTIES AS UNDER:
        1.	That the Lessor hereby grants to the Lessee, the right to enter into use and remain in the said premises along with the existing fixtures and fittings listed in Annexure 1 to this Agreement and that the Lessee shall be entitled to peacefully possess, and enjoy possession of the said premises, and the other rights herein.
        2.	That the lease hereby granted shall, unless cancelled earlier under any provision of this Agreement, remain in force for a period of #leaseterm. 
        3.	That the Lessee will have the option to terminate this lease by giving #onemonthnotice in writing to the Lessor.
        4.	That the Lessee shall have no right to create any sub-lease or assign or transfer in any manner the lease or give to anyone the possession of the said premises or any part thereof.
        5.	That the Lessee shall use the said premises only for residential purposes.
        6.	That the Lessor shall, before handing over the said premises, ensure the working of sanitary, electrical and water supply connections and other fittings pertaining to the said premises. It is agreed that it shall be the responsibility of the Lessor for their return in the working condition at the time of re-possession of the said premises (reasonable wear and tear and loss or damage by fire, flood, rains, accident, irresistible force or act of God excepted).
        7.	That the Lessee is not authorized to make any alteration in the construction of the said premises. The Lessee may however install and remove his own fittings and fixtures, provided this is done without causing any excessive damage or loss to the said premises.
        8.	That the day-to-day repair jobs such as fuse blow out, replacement of light bulbs/tubes, leakage of water taps, maintenance of the water pump and other minor repairs, etc., shall be effected by the Lessee at its own cost, and any major repairs, either structural or to the electrical or water connection, plumbing leaks, water seepage shall be attended to by the Lessor. In the event of the Lessor failing to carry out the repairs on receiving notice from the Lessee, the Lessee shall undertake the necessary repairs and the Lessor will be liable to immediately reimburse costs incurred by the Lessee.
        9.	That the Lessor or its duly authorized agent shall have the right to enter into or upon the said premises or any part thereof at a mutually arranged convenient time for the purpose of inspection. 
        10.	That the Lessee shall use the said premises along with its fixtures and fitting in careful and responsible manner and shall handover the premises to the Lessor in working condition (reasonable wear and tear and loss or damage by fire, flood, rains, accidents, irresistible force or act of God excepted).
        11.	That in consideration of use of the said premises the Lessee agrees that he shall pay to the Lessor during the period of this agreement, a monthly rent at the rate of #monthlyrentalinnumber&words. The amount will be paid in advance on or before the date of #paiday of every English calendar month.
        12.	It is hereby agreed that if default is made by the lessee in payment of the rent for a period of three months, or in observance and performance of any of the covenants and stipulations hereby contained and on the part to be observed and performed by the lessee, then on such default, the lessor shall be entitled in addition to or in the alternative to any other remedy that may be available to him at this discretion, to terminate the lease and eject the lessee from the said premises; and to take possession thereof as full and absolute owner thereof, provided that a notice in writing shall be given by the lessor to the lessee of his intention to terminate the lease and to take possession of the said premises. If the arrears of rent are paid or the lessee comply with or carry out the covenants and conditions or stipulations, within fifteen days from the service of such notice, then the lessor shall not be entitled to take possession of the said premises.
        13.	That in addition to the compensation mentioned above, the Lessee shall pay the actual electricity, shared maintenance, water bills for the period of the agreement directly to the authorities concerned. The relevant `start date` meter readings are #startingmetereading. 
        14.	That the Lessee has paid to the Lessor a sum of #rentaldepositinumber&words as deposit, free of interest, which the Lessor does accept and acknowledge. This deposit is for the due performance and observance of the terms and conditions of this Agreement. The deposit shall be returned to the Lessee simultaneously with the Lessee vacating the said premises. In the event of failure on the part of the Lessor to refund the said deposit amount to the Lessee as aforesaid, the Lessee shall be entitled to continue to use and occupy the said premises without payment of any rent until the Lessor refunds the said amount (without prejudice to the Lessee`s rights and remedies in law to recover the deposit).
        15.	That the Lessor shall be responsible for the payment of all taxes and levies pertaining to the said premises including but not limited to House Tax, Property Tax, other cesses, if any, and any other statutory taxes, levied by the Government or Governmental Departments. During the term of this Agreement, the Lessor shall comply with all rules, regulations and requirements of any statutory authority, local, state and central government and governmental departments in relation to the said premises.
        IN WITNESS WHEREOF, the parties hereto have set their hands on the day and year first hereinabove mentioned. 

        Lessor,	Lessee,
        #name	#name
        # landlordaddress1	# tenantaddress1
        #lordaddressline2	#tenantaddressline2
        #lordcity, #lordstate, #lordpincode	#tencity, #tenstate, #tenpincode


        WITNESS ONE	WITNESS TWO


        [Name & Address]	[Name & Address]

        ANNEXURE I
        List of fixtures and fittings provided in #leasepropertyaddress1, #leaseaddressline2, #leasecity, #leasestate, #leasepincode: 
        1.	#item1
        2.	#item2
        3.	#item3
        """
    f"You are an assistant tasked with filling out a Residential Rental Agreement based on the user's query. The agreement contains placeholders that need to be replaced with specific details from the user's input. The placeholders are as in #city like this, itll start with a # so you need to replace those fileds only and return the full aggremmentYour task is to process the following user query and extract the required information to replace the placeholders in the agreement accordingly. The query is: {query}"
)

    print("6 ------------ question")

    api_key = "AIzaSyDcP3_6sDB3P8lZkIyv0YSeFfvMsh_5RsQ"
    model_name = 'gemini-1.5-flash-latest'
    gemini_client = GeminiAI(api_key, model_name)
    print("7 ------------ question")

    response = gemini_client.generate_response(chat_prompt)
    print("8 ------------ question")

    return jsonify({"answer": response})
@app.route('/create-order-rest', methods=['POST'])
def create_order_rest():
    try:
        # Get data from the request (React frontend will send this)
        data = request.json
        user_email = data.get('email')

        amount = data.get('amount')  # Amount in paise (sent from React)

        if not amount or amount <= 0:
            return jsonify({'error': 'Invalid amount'}), 400

        # Create Razorpay order
        order_data = {
            "amount": amount,  # Amount in paise
            "currency": "INR",
            "receipt": f"receipt_{user_email}",
        }
        payment = razorpay_client.order.create(data=order_data)

        # Save the order in MongoDB with status 'created'
        collectionrest.insert_one({
            "email": user_email,
            "amount": amount,
            "payment_id": payment['id'],
            "status": "created",
            "createAt": int(time.time()),
        })

        # Return the payment order details to React frontend
        return jsonify(payment)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/verify-payment-rest', methods=['POST'])
def verify_payment_rest():
    try:
        data = request.json
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_signature = data.get('razorpay_signature')
        food_items = data.get('food', [])  # Get the food array from the request
        email = data.get('email')
        print(email)
        # Verify the payment signature using HMAC SHA256
        generated_signature = hmac.new(
            bytes(razorpay_secret, 'utf-8'),
            msg=bytes(razorpay_order_id + "|" + razorpay_payment_id, 'utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()

        if generated_signature == razorpay_signature:
            # Format the food details
            food_names = [item['name'] for item in food_items]
            food_costs = [item['price'] for item in food_items]
            created_at = int(time.time())

            # Update the order status in MongoDB
            collectionrest.update_one(
                {"payment_id": razorpay_order_id},
                {"$set": {
                    "status": "successful",
                    "razorpay_payment_id": razorpay_payment_id,
                }}
            )

            # Insert the formatted data into the database
            collectionorders.insert_one({
                "email": email,
                "food": food_names,
                "cost": food_costs,
                "createdAt": created_at,
            
            })

            return jsonify({'status': 'Payment verified successfully'})
        else:
            # Signature mismatch, payment failed
            return jsonify({'error': 'Signature verification failed'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500


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

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5000)
