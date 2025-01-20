import uuid
import random
import string
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from flask import Flask, jsonify, request
from datetime import datetime, timedelta
from flask_cors import CORS
from prometheus_flask_exporter import PrometheusMetrics
import jwt
from functools import wraps
import smtplib
import random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST


app = Flask(__name__)
# Initialize Prometheus metrics
metrics = PrometheusMetrics(app, defaults_prefix='my_app')

# Enable CORS for all routes
CORS(app)
uri = "mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth"
app.config['SECRET_KEY'] = 'efa8f62542204fb7a09e081699481658'  # Replace with your own secret key
# Create the client
client = MongoClient(uri, server_api=ServerApi('1'))

# Connect to the database and collection
db = client['auth']
collection = db['authenticator']
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


@app.route('/metrics')
def metrics_route():

    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
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
            "exp": datetime.utcnow() + timedelta(hours=100)  # Token expires in 1 hour
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
    
if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5000)
