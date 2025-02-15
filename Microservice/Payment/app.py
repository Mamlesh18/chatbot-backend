from flask import Flask, jsonify, request, send_file
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from flask_cors import CORS
import razorpay
from datetime import datetime, timedelta
import hmac
import time
import hashlib

app = Flask(__name__)

CORS(app)

uri = "mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth"
client = MongoClient(uri, server_api=ServerApi('1'))

db = client['ChatterPy']
collectionPayment = db['payment']



razorpay_client = razorpay.Client(auth=("rzp_test_ls8UyEU66pm1Y6", "nATjdwiqiKuKDqJLxMluczid"))
razorpay_secret = "nATjdwiqiKuKDqJLxMluczid"  

subscription_plans = {
    "basic": 10000,   
    "standard": 20000,  
    "premium": 39900   
}

@app.route('/v1/payment/create', methods=['POST'])
def create_order():
    try:
        data = request.json
        user_email = data.get('email')

      
        subscription_type = data.get('subscription_type')

        if subscription_type not in subscription_plans:
            return jsonify({'error': 'Invalid subscription type'}), 400

        order_data = {
            "amount": subscription_plans[subscription_type],  
            "currency": "INR",
            "receipt": f"receipt_{user_email}",
        }
        payment = razorpay_client.order.create(data=order_data)

        collectionPayment.insert_one({
            "email": user_email,
            "subscription_type": subscription_type,
            "amount": subscription_plans[subscription_type],
            "payment_id": payment['id'],
            "status": "created",
            "createAt": int(time.time()),
            "LastDate": 0
        })

        return jsonify(payment)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/v1/payment/verify', methods=['POST'])
def verify_payment():
    try:
        data = request.json
        razorpay_payment_id = data.get('razorpay_payment_id')
        razorpay_order_id = data.get('razorpay_order_id')
        razorpay_signature = data.get('razorpay_signature')

        generated_signature = hmac.new(
            bytes(razorpay_secret, 'utf-8'),
            msg=bytes(razorpay_order_id + "|" + razorpay_payment_id, 'utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()

        if generated_signature == razorpay_signature:
            order = collectionPayment.find_one({"payment_id": razorpay_order_id})
            if order:
                subscription_type = order.get('subscription_type')

                if subscription_type == 'basic':
                    last_date = datetime.now() + timedelta(days=1)
                elif subscription_type == 'standard':
                    last_date = datetime.now() + timedelta(days=7)
                elif subscription_type == 'premium':
                    last_date = datetime.now() + timedelta(days=30)
                else:
                    return jsonify({'error': 'Invalid subscription type'}), 400

                collectionPayment.update_one(
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
            return jsonify({'error': 'Signature verification failed'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5005)
