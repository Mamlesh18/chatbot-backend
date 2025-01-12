import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def submit_data(email, message):
    sender_email = "mamleshsurya6@gmail.com"  # Replace with your email
    receiver_email = email  # The email of the recipient
    password = "iffc dxur pbkt fsir"

    # Create the email content
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = "Demo Email"  # Subject of the email
    msg.attach(MIMEText(message, 'plain'))  # Attach the message content

    try:
        # Send the email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Start TLS encryption
        server.login(sender_email, password)  # Log in to the server
        server.send_message(msg)  # Send the email
        server.quit()  # Close the server connection

        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

# Example usage
submit_data("mamlesh.va06@gmail.com", "This is a demo email from Python.")
