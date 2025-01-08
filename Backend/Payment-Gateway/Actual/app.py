import razorpay
import hmac
from flask_cors import CORS
import hashlib
from flask import Flask, request, jsonify
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
app = Flask(__name__)
# Enable CORS for all routes
CORS(app)

# Setup Razorpay client
razorpay_client = razorpay.Client(auth=("rzp_test_ls8UyEU66pm1Y6", "nATjdwiqiKuKDqJLxMluczid"))
razorpay_secret = "nATjdwiqiKuKDqJLxMluczid"  # Razorpay key secret

# Setup MongoDB client
uri = "mongodb+srv://Chatbot:developer@auth.hlrq2.mongodb.net/?retryWrites=true&w=majority&appName=auth"
app.config['SECRET_KEY'] = 'efa8f62542204fb7a09e081699481658'  # Replace with your own secret key

# Create the client
client = MongoClient(uri, server_api=ServerApi('1'))
db = client['auth']
collection = db['authenticator']

# Define the subscription plans
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
        collection.insert_one({
            "email": user_email,
            "subscription_type": subscription_type,
            "amount": subscription_plans[subscription_type],
            "payment_id": payment['id'],
            "status": "created"
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
            # Payment is verified
            collection.update_one(
                {"payment_id": razorpay_order_id},
                {"$set": {"status": "successful", "razorpay_payment_id": razorpay_payment_id}}
            )
            return jsonify({'status': 'Payment verified successfully'})
        else:
            # Signature mismatch, payment failed
            return jsonify({'error': 'Signature verification failed'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.debug = True
    app.run()
