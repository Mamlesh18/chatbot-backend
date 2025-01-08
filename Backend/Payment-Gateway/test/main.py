import razorpay
import json
from flask import Flask, render_template, request

app = Flask(__name__, static_folder='static', static_url_path='')

@app.route('/')
def app_create():
    return render_template('app.html')

@app.route('/pay', methods=['POST'])
def pay():
    name = request.form.get('username')
    client = razorpay.Client(auth=("rzp_test_ls8UyEU66pm1Y6", "nATjdwiqiKuKDqJLxMluczid"))

    # Create the Razorpay order (amount is in paise, so 39900 paise = ₹399.00)
    data = {"amount": 39900, "currency": "INR", "receipt": "#11"}
    
    try:
        payment = client.order.create(data=data)
    except Exception as e:
        return f"An error occurred: {str(e)}"

    return render_template('pay.html', payment=payment)

if __name__ == "__main__":
    app.debug = True
    app.run()
