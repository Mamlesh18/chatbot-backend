from flask import Flask, request, jsonify
from pymongo import MongoClient
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# MongoDB connection
client = MongoClient('mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth')
db = client['complain_db']
complaints_collection = db['complaints']

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
    app.run(debug=True)