import uuid
import random
import string
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from flask import Flask, jsonify, request
from datetime import datetime, timedelta
from flask_cors import CORS
import jwt
from functools import wraps
import random



app = Flask(__name__)

CORS(app)
uri = "mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth"
app.config['SECRET_KEY'] = 'efa8f62542204fb7a09e081699481658'  
client = MongoClient(uri, server_api=ServerApi('1'))

db = client['ChatterPy']
collection = db['auth']

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

    
if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5000)
