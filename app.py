from flask import Flask, request, jsonify, render_template, redirect, session
from email_otp import create_and_send_otp, verify_otp

app = Flask(__name__)
app.secret_key = "secret123"


# ================= ROUTES =================

@app.route("/")
def login():
    return render_template("index.html")


@app.route("/signup")
def signup():
    return render_template("signup.html")


@app.route("/home")
def home():
    return render_template("home.html")


# ================= PREDICT (IMPORTANT FIX) =================
@app.route("/predict", methods=["POST"])
def predict():
    try:
        data = request.json
        print("📊 Received data:", data)

        # 🔥 SIMPLE LOGIC (you can replace with ML later)

        device = str(data.get("device", "")).lower()
        location = str(data.get("location", "")).lower()
        failed_attempts = int(data.get("failedAttempts", 0))

        # Example risk rules
        if failed_attempts > 2:
            return jsonify({"prediction": 1})  # risky

        if "unknown" in location:
            return jsonify({"prediction": 1})

        if "mobile" in device:
            return jsonify({"prediction": 0})  # safe

        # Default risky
        return jsonify({"prediction": 1})

    except Exception as e:
        print("❌ Prediction error:", e)
        return jsonify({"prediction": 1})


# ================= SEND OTP =================
@app.route("/send_otp", methods=["POST"])
def send_otp_route():
    email = request.form.get("email")

    if not email:
        return "❌ Email required"

    print("📧 Sending OTP to:", email)

    success = create_and_send_otp(email)

    if success:
        if request.form.get("redirect") == "false":
            return "OTP sent"
        return redirect("/otp")
    else:
        return "❌ Failed to send OTP"


# ================= VERIFY OTP =================
@app.route("/otp", methods=["GET", "POST"])
def otp():
    if request.method == "POST":
        user_otp = request.form.get("otp")

        if verify_otp(user_otp):
            print("✅ OTP verified")
            return redirect("/home")
        else:
            print("❌ Invalid OTP")
            return "❌ Invalid OTP"

    return render_template("otp.html")


# ================= RUN =================
if __name__ == "__main__":
    print("🔥 Flask app running...")
    app.run(host="0.0.0.0", port=5000, debug=True)