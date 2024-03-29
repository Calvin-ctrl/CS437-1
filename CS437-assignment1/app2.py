# Import required modules
from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    flash,
    session,
    send_file,
    request,
    jsonify,
)
from flask_pymongo import PyMongo
from bson import ObjectId
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length
from flask_mail import Mail, Message
from PIL import Image, ImageDraw, ImageFont
import io
import random
import requests
from pymongo import MongoClient
from twilio.rest import Client
from email_validator import validate_email, EmailNotValidError
from datetime import datetime, timedelta, timezone
from wtforms.validators import EqualTo
import logging
from logging.handlers import RotatingFileHandler



app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
app.logger.setLevel(logging.INFO)

handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=10)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)


def classify_attack(log_entry):
    # Implement attack classification logic based on log entries
    if "Invalid code" in log_entry:
        return "Brute Force Attempt"
    elif "Invalid password" in log_entry:
        return "Invalid Password Attempt"
    else:
        return "Unclassified"
    
# Monitoring route
@app.route("/monitoring")
def monitoring():
    # Check if the user is an admin
    if "user_role" in session and session["user_role"] == "admin":
        # Read log entries
        with open('app.log', 'r') as log_file:
            log_entries = log_file.readlines()
        print("Log Entries:", log_entries) 
        # Classify attacks
        attack_classifications = [classify_attack(log_entry) for log_entry in log_entries]

        # Combine log entries and attack classifications using zip
        combined_data = zip(log_entries, attack_classifications)

        # Render the monitoring template with the combined data
        return render_template("monitoring.html", combined_data=combined_data)
    else:
        flash("You are not authorized to access the monitoring page.", "danger")
        return redirect(url_for('home'))


#Twilio credentials
account_sid = 'AC4c75b9ab6c8f8070098883783f24eade'##You yan enter your own credentials
auth_token = '9d480bd0ef09816d4d9181594e8535bc'
twilio_phone_number = '+15162438196'

# Twilio client initialization
client1 = Client(account_sid, auth_token)


# function to send a password reset code via SMS
def send_reset_code_sms(phone_number, code):
    print("here")
    message = client1.messages.create(
        body=f"Your admin password reset code is: {code}. Enter this code to reset your password.",
        from_=twilio_phone_number,
        to=phone_number
    )

    
class ForgetPasswordSmsCodeForm(FlaskForm):
    code = StringField("Code", validators=[DataRequired(), Length(min=2, max=2)])
    submit = SubmitField("Verify Code")


class ForgetPasswordSmsForm(FlaskForm):
    phone = StringField("phone", validators=[DataRequired(), Length(min=10, max=15)])
    submit = SubmitField("Continue")

# Forgot password sms validation for admin.
@app.route("/forget_password_sms", methods=["POST","GET"])
def forget_password_sms():
    form=ForgetPasswordSmsForm()
    
    if form.validate_on_submit():
        phone_number = form.phone.data
        # Check if the phone_number exists in the dataset
        if mongo.db.admins.find_one({"phone": phone_number}):
            reset_code, expiration_time = generate_reset_code() # Generate a reset code
           
            # Send the reset code via SMS
            send_reset_code_sms(phone_number, reset_code)
            session["reset_code"] = reset_code
            session["expiration_time"] = expiration_time
            session["reset_phone_number"] = phone_number
            
            return redirect(url_for("admin_reset_password"))
        else:
            flash("Phone number not found. Please enter a registered phone number.", "danger")
            return redirect(url_for("forget_password_sms"))
    # Ensure a valid response is returned for all cases
    return render_template("admin_forget_password_sms.html", form = form)



class AdminResetPasswordForm(FlaskForm):
    reset_code = StringField("Reset Code", validators=[DataRequired(), Length(min=2, max=2)])
    new_password = PasswordField("New Password", validators=[DataRequired()])
    confirm_password = PasswordField("Confirm New Password", validators=[DataRequired(), EqualTo('new_password', message='Passwords must match')])
    submit = SubmitField("Reset Password")

# Forgot password sms validation for admin.
@app.route("/admin_reset_password", methods=["GET", "POST"])
def admin_reset_password():
    form = AdminResetPasswordForm()

    if "reset_phone_number" not in session or "reset_code" not in session or "expiration_time" not in session:
        flash("Invalid request. Please start the password reset process again.", "danger")
        return redirect(url_for("admin_login"))

    if is_code_expired(session["expiration_time"]):
        flash("The reset code has expired. Please start the process again.", "danger")
        return redirect(url_for("admin_login"))

    if form.validate_on_submit(): 
        entered_code = form.reset_code.data
      
        if entered_code == session["reset_code"]:
            # Retrieve admin based on the phone number
            admin = mongo.db.admins.find_one({"phone": session["reset_phone_number"]})
           
            if admin:
                # Update the admin's password in the database
                new_password = form.new_password.data
                mongo.db.admins.update_one({"_id": admin["_id"]}, {"$set": {"password": new_password}})
                flash("Password updated successfully.", "success")

            else:
                flash("Admin not found. Password update failed.", "danger")

            return redirect(url_for("admin_login"))
        else:
            flash("Invalid code. Please enter the correct code.", "danger")
           
    return render_template("admin_reset_password.html", form=form)


# Flask-Mail configuration for SendGrid
app.config['MAIL_SERVER']='sandbox.smtp.mailtrap.io'
app.config['MAIL_PORT'] = 2525
app.config['MAIL_USERNAME'] = '26dea73969a40d'
app.config['MAIL_PASSWORD'] = '843fb4a3f8cc3c'
app.config["MAIL_DEFAULT_SENDER"] = "cs437@yandex.com"
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
mail = Mail(app)


mongo_uri = "mongodb+srv://aycelen:aycelen123@cluster0.6ofoijn.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(mongo_uri)
db = client.task4
users_collection = db.users

app.config[
     "MONGO_URI"
 ] = "mongodb+srv://aycelen:aycelen123@cluster0.6ofoijn.mongodb.net/task4?retryWrites=true&w=majority"
mongo = PyMongo(app)


# class for user login
class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    captcha = StringField("Captcha", validators=[DataRequired()])
    submit = SubmitField("Login")


# class for admin login
class AdminLoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    captcha = StringField("Captcha", validators=[DataRequired()])
    submit = SubmitField("Login")


# class to send email for forget password
class ForgetPasswordEmailForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Continue")


# class to enter the code sent by email to froget password
class ForgetPasswordCodeForm(FlaskForm):
    code = StringField("Code", validators=[DataRequired(), Length(min=2, max=2)])
    submit = SubmitField("Verify Code")


#############################################################
# CAPTCHA CREATION (static 2digit number for user, 4 digit changin number based for admin)


@app.route("/captcha")
def serve_captcha():
    image_io = generate_captcha_image()
    return send_file(image_io, mimetype="image/png")

@app.route("/admin_captcha")
def serve_admin_captcha():
    image_io = generate_admin_captcha_image()
    return send_file(image_io, mimetype="image/png")

def generate_captcha_image():
    # Use a static 4-digit number as CAPTCHA text
    captcha_text = "31"

    # Save the CAPTCHA text in the session
    session["captcha"] = captcha_text

    # Generate an image with the CAPTCHA text
    image = Image.new("RGB", (120, 40), color="white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((10, 10), captcha_text, font=font, fill="black")

    # Save the image to a BytesIO object
    image_io = io.BytesIO()
    image.save(image_io, "PNG")
    image_io.seek(0)

    return image_io

def generate_admin_captcha_image():
    # Generate a random 4-digit number for the CAPTCHA text for admin login
    captcha_text = str(random.randint(1000, 9999))

    # Save the CAPTCHA text in the session
    session["admin_captcha"] = captcha_text

    # Generate an image with the CAPTCHA text
    image = Image.new("RGB", (120, 40), color="white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((10, 10), captcha_text, font=font, fill="black")

    # Save the image to a BytesIO object
    image_io = io.BytesIO()
    image.save(image_io, "PNG")
    image_io.seek(0)

    return image_io

##############################################################3
# FORGET PASSWORD (2 mins expiration duration, 2 digit code, send by email for user only): DONE

# function to generate a reset code along with timestamp
def generate_reset_code():
    reset_code = str(random.randint(10, 99))
    timestamp = datetime.utcnow().replace(tzinfo=timezone.utc)
    expiration_time = timestamp + timedelta(minutes=2)
    return reset_code, expiration_time

# function to check if the reset code has expired
def is_code_expired(expiration_time):
    return datetime.utcnow().replace(tzinfo=timezone.utc) > expiration_time


# function to send a message to email
def send_reset_code_email(email, code):
    subject = "Password Reset Code"
    body = (
        f"Your password reset code is: {code}. Enter this code to reset your password."
    )
    message = Message(subject, recipients=[email], body=body)
    mail.send(message)

# fucntion to send email code

@app.route("/forget_password_email", methods=["GET", "POST"])
def forget_password_email():
    form = ForgetPasswordEmailForm()

    if form.validate_on_submit():
        email = form.email.data
        # Check if the email exists in the dataset
        if mongo.db.users.find_one({"email": email}):
            reset_code, expiration_time = generate_reset_code()
            session["reset_email"] = email
            session["reset_code"] = reset_code
            session["reset_code_expiration"] = expiration_time
            send_reset_code_email(email, reset_code)
            return redirect(url_for("forget_password_code"))

        else:
            flash("Email not found. Please enter a registered email address.", "danger")

    return render_template("forget_password_email.html", form=form)

# function to verify code

@app.route("/forget_password_code", methods=["GET", "POST"])
def forget_password_code():
    form = ForgetPasswordCodeForm()

    if "reset_email" not in session or "reset_code" not in session or "reset_code_expiration" not in session:
        flash(
            "Invalid request. Please start the password reset process again.", "danger"
        )
        return redirect(url_for("login"))

    if is_code_expired(session["reset_code_expiration"]):
        flash("The reset code has expired. Please start the process again.", "danger")
        return redirect(url_for("login"))

    if form.validate_on_submit():
        entered_code = form.code.data
        if entered_code == session["reset_code"]:
            # Code is valid, allow the user to reset the password
            flash("Code verified. You can now reset your password.", "success")
           
            return redirect(url_for("login"))

        else:
            flash("Invalid code. Please enter the correct code.", "danger")

    return render_template("forget_password_code.html", form=form)

########################################################################################################################################
# User router
@app.route("/users", methods=["GET", "POST"])
def users():
    if request.method == "GET":
        users = mongo.db.users.find()
        users = [user for user in users]
        for user in users:
            user["_id"] = str(user["_id"])  # Convert ObjectId to string
        return jsonify({"users": users})

    elif request.method == "POST":
        user = {"username": request.json["user"], "password": request.json["password"]}
        mongo.db.users.insert_one(user)
        user["_id"] = str(user["_id"])  # Convert ObjectId to string
        return jsonify({"user": user})



# Admin router
@app.route("/admins", methods=["GET", "POST"])
def admins():
    if request.method == "GET":
        admins = mongo.db.admins.find()
        admins = [admin for admin in admins]
        for admin in admins:
            admin["_id"] = str(admin["_id"])  # Convert ObjectId to string
        return jsonify({"admins": admins})

    elif request.method == "POST":
        admin = {"username": request.json["user"], "password": request.json["password"]}
        mongo.db.admins.insert_one(admin)
        admin["_id"] = str(admin["_id"])  # Convert ObjectId to string
        return jsonify({"admin": admin})


# Login page
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        captcha = form.captcha.data
        user_ip = request.remote_addr
        if captcha != session["captcha"]:
            flash("CAPTCHA is incorrect.", "danger")
            log_entry = f"User login attempt - Username: {username}, Password: {password}, CAPTCHA: {captcha},  IP: {user_ip},Time: {datetime.now()}, status: Unsuccessfull, wrong captcha"
            app.logger.info(log_entry)
            return redirect(url_for("login"))

       
        user = mongo.db.users.find_one({"username": username, "password": password})

        if user:
            flash("Login successful!", "success")
            session["user_role"] = "user"  # Set the session variable for the admin role
            # Log successful login
            log_entry = f"User login attempt - Username: {username}, Password: {password}, CAPTCHA: {captcha}, IP: {user_ip}, Time: {datetime.now()}, status: Successfull"
            app.logger.info(log_entry)
            return redirect(url_for("home"))
        else:
            flash("Login unsuccessful. Check username and password.", "danger")

            log_entry = f"User login attempt - Username: {username}, Password: {password}, CAPTCHA: {captcha}, IP: {user_ip},Time: {datetime.now()}, status: Unsuccessfull, wrong password"
            app.logger.info(log_entry)


    generate_captcha_image()
    return render_template("login.html", form=form)


# Admin login page
@app.route("/admins/login", methods=["GET", "POST"])
def admin_login():
    form = AdminLoginForm()

    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        captcha = form.captcha.data

        user_ip = request.remote_addr

        if captcha != session["admin_captcha"]:
            flash("CAPTCHA is incorrect.", "danger")
            log_entry = f"Admin login attempt - Username: {username}, Password: {password}, CAPTCHA: {captcha}, IP: {user_ip}, Time: {datetime.now()}, status: Unsuccessfull, wrong captcha,"
            app.logger.info(log_entry)
            return redirect(url_for("admin_login"))

        
        admin = mongo.db.admins.find_one({"username": username, "password": password})

        if admin:
            flash("Admin Login successful!", "success")
            session["user_role"] = "admin"  # Set the session variable for the admin role
            # Log successful login
            log_entry = f"Admin login attempt - Username: {username}, Password: {password}, CAPTCHA: {captcha}, IP: {user_ip},Time: {datetime.now()}, status: Successfull,"
            app.logger.info(log_entry)
            return redirect(url_for("home"))
        else:
            flash("Admin Login unsuccessful. Check username and password.", "danger")
    
            # Log the attack classification
            log_entry = f"Admin login attempt - Username: {username}, Password: {password}, CAPTCHA: {captcha}, IP: {user_ip}, Time: {datetime.now()}, status: Unsuccessfull, wrong password,"
            app.logger.info(log_entry)

    generate_admin_captcha_image()
    return render_template("admin_login.html", form=form)


################################################################################
# Fetch Data
def fetch_api_data():
    # Fetch the data from the API
    api_url = "https://www.travel-advisory.info/api"

    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            return None
    except requests.RequestException:
        return None


###################################################################################


# JUST RENDERING HTML PAGES (home page for now)
# home page
@app.route("/home")
def home():
    # Fetch the data from the API
    api_response = fetch_api_data()

    # Extract the information
    if api_response and "data" in api_response:
        countries_data = api_response["data"]
        countries_info = []

        # Iterate through all the countries
        for country_code, country_data in countries_data.items():
            country_info = {
                "code": country_code,
                "name": country_data.get("name"),
                "continent": country_data.get("continent"),
                "advisory_score": country_data.get("advisory", {}).get("score"),
                "advisory_sources_active": country_data.get("advisory", {}).get(
                    "sources_active"
                ),
                "advisory_message": country_data.get("advisory", {}).get("message"),
                "advisory_updated": country_data.get("advisory", {}).get("updated"),
                "advisory_source": country_data.get("advisory", {}).get("source"),
            }
            countries_info.append(country_info)

        # Send the data
        return render_template("home_page.html", countries_info=countries_info)
    else:
        return render_template(
            "home_page.html", error_message="Failed to fetch or parse data"
        )


@app.route("/all_countries")
def all_countries():
    # Fetch data from the API
    api_response = fetch_api_data()

    # Extract information
    if api_response and "data" in api_response:
        countries_data = api_response["data"]
        countries_info = []

        # Iterate through all countries
        for country_code, country_data in countries_data.items():
            country_info = {
                "code": country_code,
                "name": country_data.get("name"),
                "continent": country_data.get("continent"),
                "advisory_score": country_data.get("advisory", {}).get("score"),
                "advisory_sources_active": country_data.get("advisory", {}).get(
                    "sources_active"
                ),
                "advisory_message": country_data.get("advisory", {}).get("message"),
                "advisory_updated": country_data.get("advisory", {}).get("updated"),
                "advisory_source": country_data.get("advisory", {}).get("source"),
            }
            countries_info.append(country_info)

        # Send the data
        return render_template("all_countries.html", countries_info=countries_info)
    else:
        return render_template(
            "all_countries.html", error_message="Failed to fetch or parse data"
        )



@app.route("/search", methods=["GET"])
def search():
    query = request.args.get(
        "query"
    )  # Retrieve the query parameter from the request URL
    api_response = fetch_api_data()
    # Check if the query parameter is present and the API response exists
    if query and "data" in api_response:
        search_results = []
        for country_code, country_data in api_response["data"].items():
            country_name = country_data.get("name", "").lower()
            # Check if the query matches the country name
            if query.lower() in country_name:
                search_results.append(
                    {
                        "code": country_code,
                        "name": country_data.get("name"),
                        "continent": country_data.get("continent"),
                        "advisory_score": country_data.get("advisory", {}).get("score"),
                        "advisory_sources_active": country_data.get("advisory", {}).get(
                            "sources_active"
                        ),
                        "advisory_message": country_data.get("advisory", {}).get(
                            "message"
                        ),
                        "advisory_updated": country_data.get("advisory", {}).get(
                            "updated"
                        ),
                        "advisory_source": country_data.get("advisory", {}).get(
                            "source"
                        ),
                    }
                )

        # Render the search results template with the filtered data
        return render_template(
            "search_results.html", query=query, search_results=search_results
        )

    return render_template("search_results.html", query=query, search_results=None)

    
    
# comment    
@app.route("/comment", methods=["GET", "POST"])  
def comment():
    if request.method == "GET":
        comments = mongo.db.comments.find()
        comments = [comment for comment in comments]
        for comment in comments:
            comment["_id"] = str(comment["_id"])  
        return jsonify({"comments": comments})

    elif request.method == "POST":
        comment = {
            "content": request.json["content"],
            "username": request.json["username"],
        }
        mongo.db.comments.insert_one(comment)
        comment["_id"] = str(comment["_id"])  
        return jsonify({"comment": comment})


import requests

@app.route("/comments")
def get_comments():
    # Fetch comments from the API
    response = requests.get("http://127.0.0.1:3000/comment")
    if response.status_code == 200:
        comments = response.json()["comments"]
        return render_template("comments.html", comments=comments)
    else:
        return render_template("comments.html", comments=None)

# Route to render the comment form
@app.route("/comment_form", methods=["GET"])
def comment_form():
    return render_template("comments.html")

# Add comment route
@app.route("/add_comment", methods=["POST"])
def add_comment():
    if request.method == "POST":
        content = request.form.get("content")
        username = request.form.get("username")

        if content and username:
            comment = {
                "content": content,
                "username": username
            }

            # Save the comment to the MongoDB collection
            mongo.db.comments.insert_one(comment)
            
            return redirect(url_for("get_comments")) 
        else:
            return "Invalid comment data", 400 
    else:
        return "Method not allowed", 405 

# Delete comment route, accessible only to admins
@app.route("/delete_comment/<comment_id>", methods=["GET"])
def delete_comment(comment_id):
    if "user_role" in session and session["user_role"] == "admin":
        mongo.db.comments.delete_one({"_id": ObjectId(comment_id)})
        return redirect(url_for("get_comments"))
    else:
        flash("You are not authorized to perform this action.", "danger")
        return redirect(url_for("get_comments"))


@app.route("/admin_panel")
def admin_panel():
    # Check if the user is logged in and is an admin
    if "user_role" in session and session["user_role"] == "admin":
        # Fetch users from the API
        users_response = requests.get("http://127.0.0.1:3000/users")
        if users_response.status_code == 200:
            users = users_response.json()["users"]
        else:
            users = None

        # Fetch comments from the API
        comments_response = requests.get("http://127.0.0.1:3000/comment")
        if comments_response.status_code == 200:
            comments = comments_response.json()["comments"]
        else:
            comments = None

        return render_template("admin_panel.html", users=users, comments=comments)
        
    else:
        # Redirect to the login page or show an error message
        flash("You don't have permission to access this page.", "danger")
        return redirect(url_for("admin_login"))  # Adjust the route to your login page


@app.route('/delete_user/<string:user_id>', methods=['POST'])
def delete_user(user_id):
    # Check if the user is an admin
    if "user_role" in session and session["user_role"] == "admin":
        mongo.db.users.delete_one({"_id": ObjectId(user_id)})
        flash("User deleted successfully.", "success")
    else:
        flash("You are not authorized to perform this action.", "danger")
    
    return redirect(url_for('admin_panel'))


@app.route('/delete_comment/<string:comment_id>', methods=['POST'])
def delete_comment_admin_panel(comment_id):
    # Check if the user is an admin
    if "user_role" in session and session["user_role"] == "admin":
        
        mongo.db.comments.delete_one({"_id": ObjectId(comment_id)})

        flash("Comment deleted successfully.", "success")
    else:
        flash("You are not authorized to perform this action.", "danger")
    
    return redirect(url_for('admin_panel'))
if __name__ == "__main__":
    app.run(debug=True, port=3000)