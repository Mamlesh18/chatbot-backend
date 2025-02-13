import uuid
import random
import string
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from flask import Flask, jsonify, request, redirect, url_for, session, jsonify
from datetime import datetime, timedelta
from flask_cors import CORS
import jwt
from functools import wraps
import random
from flask_oauthlib.client import OAuth
import os



app = Flask(__name__)
app.secret_key = os.urandom(24)

CORS(app, supports_credentials=True, origins=["http://localhost:3001"])
uri = "mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth"
app.config['SECRET_KEY'] = 'efa8f62542204fb7a09e081699481658'  
client = MongoClient(uri, server_api=ServerApi('1'))

db = client['ChatterPy']
collection = db['auth']
complaints_collection = db['complain']


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




def generate_random_key(length=64):

    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


@app.route('/v1/auth/signup', methods=['POST'])
def auth():
    try:
        data = request.json
        if not data:
            raise ValueError("No JSON data provided")
        email = data.get('email')
        password = data.get('password')

        if  not email or not password:
            return jsonify({"error": " email, and password are required"}), 400

        existing_user = collection.find_one({"email": email})
        if existing_user:
            return jsonify({"error": "Email already exists"}), 409 

        document = {
            "uuid": str(uuid.uuid4()),  
            "email": email,  
            "password": password,  
            "key": generate_random_key(),  
            "create_at": datetime.now()
            
        }

        collection.insert_one(document)

        token_payload = {
            "email": email,
            "exp": datetime.utcnow() + timedelta(days=365)  
        }
        token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm="HS256")

        return jsonify({"message": "Login successful", "token": token}), 200


    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/v1/auth/login', methods=['POST'])
def login():
    try:
       
        data = request.json
        if not data:
            raise ValueError("No JSON data provided")

        identifier = data.get('email')  
        password = data.get('password')

        if not identifier or not password:
            return jsonify({"error": "Username/email and password are required"}), 400

        query = {"$or": [ {"email": identifier}]}
        user = collection.find_one(query)

        if not user:
            return jsonify({"error": "Invalid username/email or password"}), 401

        if user['password'] != password:
            return jsonify({"error": "Invalid username/email or password"}), 401

        token_payload = {
            "uuid": user['uuid'],
            "email": user['email'],
            "exp": datetime.utcnow() + timedelta(days=365)  
        }
        token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm="HS256")

        return jsonify({"message": "Login successful", "token": token}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


oauth = OAuth(app)
google = oauth.remote_app(
    'google',
    consumer_key="756748936250-2c2e4cl2j03gaipkj16ejr6rnbolsuck.apps.googleusercontent.com",
    consumer_secret="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",
    request_token_params={
        'scope': 'email profile',
    },
    base_url='https://www.googleapis.com/oauth2/v1/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://oauth2.googleapis.com/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
)

@app.route('/login/google')
def logins():
    return google.authorize(callback=url_for('authorized', _external=True))
@app.route('/authorize/google')
def authorized():
    response = google.authorized_response()
    if response is None or response.get('access_token') is None:
        return jsonify({"error": "Access denied"}), 400

    session['google_token'] = (response['access_token'], '')
    user_info = google.get('userinfo').data

    # Check if user already exists in the database
    existing_user = collection.find_one({"email": user_info["email"]})
    if not existing_user:
        # If user does not exist, create a new document
        document = {
            "uuid": str(uuid.uuid4()),
            "email": user_info["email"],
            "name": user_info["name"],
            "type": "Google",
            "create_at": datetime.now()
        }
        collection.insert_one(document)
    else:
        # If user exists, update the document with Google type
        collection.update_one({"email": user_info["email"]}, {"$set": {"type": "Google"}})

    # Generate JWT token
    token_payload = {
        "email": user_info["email"],
        "exp": datetime.utcnow() + timedelta(days=365)
    }
    token = jwt.encode(token_payload, app.config['SECRET_KEY'], algorithm="HS256")

    # Redirect to the React frontend with the token and email as query parameters
    return redirect(f'http://localhost:3001/auth/callback?token={token}&email={user_info["email"]}')
@google.tokengetter
def get_google_oauth_token():
    return session.get('google_token')


@app.route('/api/contact', methods=['POST'])
def submit_complaint():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    message = data.get('message')

    if not name or not email or not message:
        return jsonify({'error': 'Missing data'}), 400

    complaint = {
        'name': name,
        'email': email,
        'message': message
    }

    complaints_collection.insert_one(complaint)
    return jsonify({'message': 'Complaint submitted successfully'}), 201

@app.route('/api/complains', methods=['GET'])
def get_complaints():
    complaints = list(complaints_collection.find({}, {'_id': 0}))
    return jsonify(complaints), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5000)
