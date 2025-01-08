import uuid
import random
import string
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from flask import Flask, jsonify, request, send_file
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

# Enable CORS for all routes
CORS(app)

# Initialize global variables for FAISS index and content
index = None
paragraphs = []
model = SentenceTransformer('all-MiniLM-L6-v2')
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

# Step 2: Process the selected links and store content as a single string
@app.route('/process-links', methods=['POST'])
@token_required
def process_links():
    global index, paragraphs  # Make the content global for FAISS indexing

    data = request.get_json()
    selected_links = data.get('selected_links', [])
    
    crawler = WebCrawler()
    crawler.warmup()

    content = []
    for link in selected_links:
        result = crawler.run(url=link)
        content.append(result.markdown)
    
    paragraphs = "\n\n".join(content)  # Store content as a single string

    if not paragraphs:
        return jsonify({"message": "No content to index"})

    # Split paragraphs into list for indexing
    paragraph_list = paragraphs.split("\n\n")
    embeddings = model.encode(paragraph_list)
    dimension = embeddings.shape[1]

    # Initialize FAISS index
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings))

    # Write the content to a .txt file
    txt_file_path = os.path.join(os.getcwd(), 'scraped_data.txt')
    with open(txt_file_path, 'w', encoding='utf-8') as f:
        f.write(paragraphs)

    return jsonify({"message": "FAISS index created", "paragraphs": paragraph_list, "file_path": "/download-scraped-data"})


@app.route('/download-scraped-data', methods=['GET'])
def download_scraped_data():
    txt_file_path = os.path.join(os.getcwd(), 'scraped_data.txt')
    if os.path.exists(txt_file_path):
        return send_file(txt_file_path, as_attachment=True)
    return jsonify({"message": "File not found"}), 404

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
    # First, check if the user is subscribed or on a free trial
    error_response, is_subscribed = is_user_subscribed(email)

    if not is_subscribed:
        print("Subscription expired or not found.")
        return error_response, False  # User is not subscribed, stop here
    if is_subscribed:
        print("User is subscribed, proceed with free trial check.")
        return None, True
    else:
        user = collection.find_one({"email": email})
        if user is None:
            return {"error": "User not found"}, False

        # Check the free trial count
        count = user.get("count", 0)
        if count >= 5:
            return {"error": "Free message limit reached. Please subscribe."}, False

        # Increment the count for free trial and update the user record
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
    global index, paragraphs

    if not index:
        return jsonify({"message": "FAISS index not created"})

    data = request.get_json()
    query = data.get('query', '')
    email = request.headers.get('Email')

    if not email:
        return jsonify({"error": "Email not provided"}), 400

    # Check user's message count and increment if under the limit
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
# MongoDB connection URI


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
    context = "\n\n".join(closest_match)
    print("5 ------------ question")

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
    f"Determine if the following question contains any intent to order food. "
    f"If the user wants to order food, return only a JSON object in the format {{'food': '<food mentioned by user>'}}. "
    f"If no food order intent is present, return only the boolean value False. Do not add any other words or information: {query}"
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
    if not is_user_paidsubscribed(email):
        return jsonify({'error':'subscribe to access this'})
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

            # Check if the email already exists in the MongoDB collection
            existing_record = collectionpaid.find_one({'email': email})

            if existing_record:
                # If email exists, update the file content and embeddings
                collectionpaid.update_one(
                    {'email': email},
                    {'$set': {
                        'file_content': file_content,
                        'embeddings': embeddings_list,
                        'paragraphs' : paragraphs
                    }}
                )
                return jsonify({'message': 'File updated and re-indexed successfully'}), 200
            else:
                # If email does not exist, insert a new record
                record = {
                    'email': email,
                    'file_content': file_content,
                    'embeddings': embeddings_list,
                    'paragraphs' : paragraphs


                }
                collectionpaid.insert_one(record)
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
        return jsonify({'error':'subscribe to access this'})

    if not query:
        return jsonify({"error": "Query not provided"}), 400

    if not email:
        return jsonify({"error": "Email not provided"}), 400

    # Fetch the user's record from MongoDB to get the embeddings and paragraphs
    user_record = collectionpaid.find_one({"email": email})
    if not user_record:
        return jsonify({"error": "User not found"}), 400
    print("1")
    embeddings_list = user_record.get('embeddings')
    print("2")

    paragraphs = user_record.get('paragraphs')
    print("3")

    if not embeddings_list:
        return jsonify({"error": "Embeddings not found for this user"}), 400
    print("4")

    # Convert the embeddings list back to a numpy array
    embeddings = np.array(embeddings_list)
    print("5")

    # Rebuild the FAISS index
    dimension = embeddings.shape[1]  # Get the dimension of the embeddings
    faiss_index = faiss.IndexFlatL2(dimension)  # Use L2 distance for similarity
    faiss_index.add(embeddings)  # Add embeddings to FAISS index
    print("6")

    # Convert query to embeddings
    query_embedding = model.encode([query])
    _, indices = faiss_index.search(query_embedding, k=5)  # Get top 5 relevant paragraphs
    print("7")

    # Extract the relevant paragraphs from the indices
    closest_match = [paragraphs[idx] for idx in indices[0]]
    context = "\n\n".join(closest_match)
    print("8")

    # Generate the prompt for Gemini
    chat_prompt = (
        f"Here are 5 most relevant paragraphs:\n\n{context}\n\n"
        f"Answer the following question based on this context: {query}"
    )
    print("10")

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
    email = data.get('email')    
    query = data.get('query', '')
    api_key = data.get('key','')
    print(email)
    if not is_user_paidsubscribed(email):
        return jsonify({'error':'subscribe to access this'})

    if not query:
        return jsonify({"error": "Query not provided"}), 400

    if not email:
        return jsonify({"error": "Email not provided"}), 400
    
    if not api_key:
        return jsonify({"error": "Email not provided"}), 400

    user_record = collectionpaid.find_one({"email": email})
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
    print("7")

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
