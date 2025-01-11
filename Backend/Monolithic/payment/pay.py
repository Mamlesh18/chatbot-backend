from flask import Flask, request, jsonify
import razorpay

app = Flask(__name__)

# Razorpay client initialization
razorpay_client = razorpay.Client(auth=("YOUR_API_KEY", "YOUR_API_SECRET"))

@app.route('/create-order', methods=['POST'])
def create_order():
    try:
        # Get amount and currency from request
        data = request.json
        amount = data['amount']  # Amount in paise (e.g., 50000 for Rs. 500)
        currency = 'INR'

        # Create a Razorpay order
        order = razorpay_client.order.create({
            'amount': amount,
            'currency': currency,
            'payment_capture': 1  # Automatic capture
        })

        return jsonify({'order_id': order['id'], 'amount': amount})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    try:
        data = request.json
        # Extract Razorpay payment details
        razorpay_order_id = data['razorpay_order_id']
        razorpay_payment_id = data['razorpay_payment_id']
        razorpay_signature = data['razorpay_signature']

        # Verify signature
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }

        result = razorpay_client.utility.verify_payment_signature(params_dict)

        return jsonify({'status': 'success'}) if result else jsonify({'status': 'failure'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
if __name__ == '__main__':
    app.run(debug=True, port=5000)