import smtplib
import random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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

if __name__ == "__main__":
    app.run(debug=True)
