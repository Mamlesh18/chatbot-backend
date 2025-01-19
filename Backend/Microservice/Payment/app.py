from flask import Flask, jsonify, request, send_file
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from flask_cors import CORS
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import razorpay
from datetime import datetime, timedelta
import hmac
import time
import hashlib

app = Flask(__name__)
# Initialize Prometheus metrics
metrics = PrometheusMetrics(app, defaults_prefix='my_app')

# Enable CORS for all routes
CORS(app)

uri = "mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth"
client = MongoClient(uri, server_api=ServerApi('1'))

dbpay = client['Payment']
collectionpay = dbpay['accepted']
dbrest = client['Restaurant']
collectionrest = dbrest['payment-details']
collectionorders = dbrest['orders']


@app.route('/metrics')
def metrics_route():

    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

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


if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5000)
