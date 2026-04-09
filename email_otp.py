import smtplib
import random
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import session

# ================= CONFIG =================
EMAIL_SENDER = "smart7mfa@gmail.com"
EMAIL_PASSWORD = "bfwtqjbamttbbhod"  # ⚠ Replace with Gmail App Password

# ================= GENERATE OTP =================
def generate_otp():
    """Generate a 6-digit numeric OTP"""
    return str(random.randint(100000, 999999))

# ================= SEND OTP =================
def send_otp_email(email, password, receiver_email, otp):
    """Send OTP via Gmail SMTP over SSL"""
    try:
        # Create email message
        message = MIMEMultipart()
        message["From"] = email
        message["To"] = receiver_email
        message["Subject"] = "Your OTP Code"
        body = f"Your OTP is: {otp}"
        message.attach(MIMEText(body, "plain"))

        # SSL context
        context = ssl.create_default_context()

        # Connect using SMTP_SSL (port 465)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(email, password)
            server.send_message(message)

        print(f"✅ OTP sent to {receiver_email}")
        return True

    except Exception as e:
        print(f"❌ Error sending OTP: {e}")
        return False

# ================= CREATE + STORE + SEND =================
def create_and_send_otp(email):
    """Generate OTP, store in session, and send email"""
    otp = generate_otp()

    # Store in Flask session
    session["otp"] = otp
    session["email"] = email

    print("🔐 Generated OTP:", otp)
    return send_otp_email(EMAIL_SENDER, EMAIL_PASSWORD, email, otp)

# ================= VERIFY OTP =================
def verify_otp(user_otp):
    """Check user-entered OTP against session"""
    stored_otp = session.get("otp")
    print("👤 Entered OTP:", user_otp)
    print("🔐 Stored OTP:", stored_otp)

    if user_otp == stored_otp:
        session.pop("otp", None)  # clear OTP after success
        return True
    else:
        return False