import os
from cs50 import SQL
from flask import Flask, redirect, render_template, request, session, flash
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import date, timedelta, datetime

from functions import check, login_required, end_of_month, check_plan

app = Flask(__name__)

# Add Jinja2 loopcontrols for continue function
app.jinja_options['extensions'].append('jinja2.ext.loopcontrols')

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Session is not permanent, i.e. user has to relog
# Store session info into filesystem, rather than cookie
# Allow sessions for this app
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQL('sqlite:///finances.db')
main_categories = ["food", "drink", "utilities", "leisure", "hobby", "clothes", "sports"]


@app.route("/modify", methods=["GET", "POST"])
@login_required
def modify():

    if request.method == "GET":

        categories = db.execute("SELECT category FROM categories WHERE user_id IS NULL OR user_id = :user_id", user_id=session["user_id"])
        return render_template("modify.html", categories=categories)

    else:

        # Check whether user pressed delete button
        if "delete" in request.form:

            # Check whether user selected a personal category
            category = request.form.get("delcat")

            if category in main_categories:
                flash("Cannot delete a pre-built category.")
                return redirect("/modify")

            else:

                # Delete personal category
                db.execute("DELETE FROM categories WHERE user_id = :user_id AND category = :category",
                           user_id=session["user_id"], category=category)

                flash("Category deleted!")
                return redirect("/")

        # User is try to add a category
        else:

            # Add a category to that user's categories
            db.execute("INSERT INTO categories (category, user_id) VALUES (:category, :user_id)",
                       category=request.form.get("category"), user_id=session["user_id"])

            # Flash function take as input an message
            # And passes it on to an html at next request
            # function "get_flashed_messages()" called at layout page
            # Which passes queued messages to variable 'messages'
            # Which are the displayed
            flash("Category added!")
            return redirect("/")


@app.route("/", methods=["GET", "POST"])
@login_required
def index():

        # Compute today's date, first of month, and last of month
        today = date.today()
        last_day = end_of_month(today)
        first_day = today.replace(day=1)

        if request.method == "GET":

            # Query db for all user's categories in order to allow them to choose one when adding a purchase
            categories = db.execute("SELECT category FROM categories WHERE user_id IS NULL OR user_id = :user_id",
                                    user_id=session["user_id"])

            # Query db for this month's plan
            plan = db.execute("SELECT * FROM plans WHERE user_id = :user_id AND end = :end",
                               user_id=session["user_id"], end=last_day)

            if len(plan) != 0:

                # Query db for user's monthly spendings per category
                stats = db.execute("SELECT category, SUM(price) AS sum, ROUND(SUM(price) * 100 / (SELECT SUM(price) FROM purchases WHERE user_id = :user_id AND (date BETWEEN :start AND :end))) AS percentage FROM purchases WHERE user_id = :user_id AND (date BETWEEN :start AND :end) GROUP BY category",
                                       user_id=session["user_id"], start=plan[0]["start"], end=plan[0]["end"])

                total_sum = sum(item["sum"] for item in stats)

                return render_template("index.html", stats=stats, total_sum=total_sum, plan=plan, categories=categories, today=today, last_day=last_day, days=last_day.day - today.day)

            # If user doesn't have a plan, render index page without quering for purchases during monthly plan
            return render_template("index.html", plan=plan, categories=categories, today=today, last_day=last_day, days=last_day.day - today.day)

        else:

            # Check which form was submitted
            if "income" in request.form:

                # Create a new plan for this month
                db.execute("INSERT INTO plans (income, disposable, start, end, user_id) VALUES (:income, :disposable, :start, :end, :user_id)",
                           income=request.form.get("income"), disposable=request.form.get("income"), start=today, end=last_day, user_id=session["user_id"])

                # Notify user passing message onto next request
                flash("Plan created!")
                return redirect("/")

            else:

                # Make sure user's input a numeric value
                try:
                    price = round(float(request.form.get("price")), 2)
                except ValueError:
                    return "Must enter a numeric value."

                # If user did not enter a name, insert purchases without it
                if not request.form.get("product"):
                    db.execute("INSERT INTO purchases(category, price, date, user_id) VALUES (:category, :price, :date, :user_id)",
                               category=request.form.get("category"), price=price, date=date.today(), user_id=session["user_id"])

                else:
                    db.execute("INSERT INTO purchases(name, category, price, date, user_id) VALUES (:name, :category, :price, :date, :user_id)",
                               name=request.form.get("product"), category=request.form.get("category"), price=price, date=date.today(), user_id=session["user_id"])

                # Notify user through flash message passed onto next request
                flash("Purchase added!")

                # Query db for this month's user's disposable sum
                disposable_old = db.execute("SELECT disposable FROM plans WHERE user_id = :user_id AND end = :end",
                                            user_id=session["user_id"], end=last_day)

                if len(disposable_old) != 0:
                    # Deduct current purchase's price
                    disposable_new = disposable_old[0]["disposable"] - price

                    # Update db with new disposable sum
                    db.execute("UPDATE plans SET disposable = :disposable WHERE user_id = :user_id AND end = :end",
                               disposable=disposable_new, user_id=session["user_id"], end=last_day)

                return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():

    message = None

    if request.method == "GET":
        return render_template("register.html")

    else:
        # Store user input
        username = request.form.get("username")
        password = request.form.get("password")
        passconfirm = request.form.get("passconfirm")

        # Check if username exists
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=username)
        if len(rows) == 1:

            flash("Username already exists.")
            return redirect("/register")

        # Check if password input checks requirements
        elif not check(password):

            flash("Password must contain at least 1 digit, uppercase- and lowercase character.")
            return redirect("/register")

        # Check if password inputs match
        elif password != passconfirm:

            flash("Passwords do not match.")
            return redirect("/register")

        # Generate hash for user's password
        # Store user info into db
        else:
            p_hash = generate_password_hash(password)
            db.execute("INSERT INTO users(username, hash) VALUES (:username, :p_hash)", username=username, p_hash=p_hash)

            message = "Registration successful!"
            return render_template("login.html", message=message)


@app.route("/login", methods=["GET", "POST"])
def login():

    # Forget user_id
    session.clear()
    message = None

    if request.method == "GET":
        return render_template("login.html")

    else:

        # Query db for username = user's input
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # Check whether username exists and password matches hash for that username's password
        if len(rows) == 0 or not check_password_hash(rows[0]["hash"], request.form.get("password")):

            message = "Incorrect username and/or password."

        else:
            # Remember logged user
            session["user_id"] = rows[0]["id"]
            return redirect("/")

        return render_template("login.html", message=message)

@app.route("/logout")
def logout():

    # Clear user session
    session.clear()
    return redirect("/")


@app.route("/delete", methods=["GET", "POST"])
@login_required
def delete():

    # Compute required dates
    today = date.today()
    last_day = end_of_month(today)

    # Query db for all user purchases during this month
    if request.method == "GET":

        purchases = db.execute("SELECT id, category, name, price FROM purchases WHERE user_id = :user_id AND (date BETWEEN :first AND :today) ORDER BY date",
                               user_id=session["user_id"], first=today.replace(day=1), today=today)

        return render_template("delete.html", purchases=purchases)

    else:

        # Retrieve purchase ID
        purchase_id = int(request.form.get("delete"))

        rows = db.execute("SELECT * FROM purchases WHERE id = :purchase_id AND user_id = :user_id",
                          purchase_id=purchase_id, user_id=session["user_id"])

        # Delete purchase from db
        db.execute("DELETE FROM purchases WHERE user_id = :user_id AND id = :purchase_id",
                   user_id=session["user_id"], purchase_id=purchase_id)

        flash("Purchase deleted!")

        # Check if user has a current plan
        plan = db.execute("SELECT * FROM plans WHERE user_id = :user_id AND end = :end",
                          user_id=session["user_id"], end=last_day)

        if len(plan) != 0:

            # Convert str type date into python datetime.date
            p_date = datetime.strptime(rows[0]["date"], '%Y-%m-%d').date()

            # Make sure purchase was bought this month
            if p_date.month == today.month and p_date.year == today.year:
                plan = db.execute("SELECT start, income, disposable FROM plans WHERE user_id = :user_id AND end = :end",
                                            user_id=session["user_id"], end=last_day)

                # Calculate new disposable sum by adding deleted purchase's price to current disposable
                disposable_new = plan[0]["disposable"] + rows[0]["price"]

                # Make sure purchase was made after creating a monthly plan
                # And new disposable sum doesn't exceed initial specified income
                if disposable_new < plan[0]["income"] or rows[0]["date"] < plan[0]["start"]:

                    # Reimburse user's monthly disposable sum
                    db.execute("UPDATE plans SET disposable = :disposable WHERE user_id = :user_id AND end = :end",
                               disposable=disposable_new, user_id=session["user_id"], end=last_day)

        return redirect("/delete")


@app.route("/history", methods=["GET", "POST"])
@login_required
def history():

    # Query all user categories
    categories = db.execute("SELECT category FROM categories WHERE user_id IS NULL OR user_id = :user_id", user_id=session["user_id"])

    # Query user's purchases per category
    stats = db.execute("SELECT category, SUM(price) AS sum, ROUND(SUM(price) * 100 / (SELECT SUM(price) FROM purchases WHERE user_id = :user_id)) AS percentage FROM purchases WHERE user_id = :user_id GROUP BY category", user_id=session["user_id"])

    total_sum = sum(item["sum"] for item in stats)

    if request.method == "GET":

        return render_template("history.html", categories=categories, stats=stats, total_sum=total_sum)

    else:

        # If user requested full history via button named "full"
        if "full" in request.form:

            # Query db for all purchases
            purchases = db.execute("SELECT date, category, name, price FROM purchases WHERE user_id = :user_id", user_id=session["user_id"])

            # Compute sum of spendings
            total = sum([item["price"] for item in purchases])

            return render_template("history.html", categories=categories, purchases=purchases, stats=stats, total=total, total_sum=total_sum)

        # If user input specific dates for history of purchases
        else:

            date_from=request.form.get("from")
            date_to=request.form.get("to")

            if date_from == "" or date_to == "":

                flash("Please enter date constraints.")
                return redirect("/history")

            # If user chose a category
            elif request.form.get("category") != "":

                # Query db for purchases using specified dates and category
                purchases = db.execute("SELECT date, category, name, price FROM purchases WHERE user_id = :user_id AND category = :category AND (date BETWEEN :date_from AND :date_to)",
                                       user_id=session["user_id"], category=request.form.get("category"), date_from=date_from, date_to=date_to)

            else:

                # Query db for all purchases based only on specified time period
                purchases = db.execute("SELECT date, category, name, price FROM purchases WHERE user_id = :user_id AND (date BETWEEN :date_from AND :date_to)",
                                       user_id=session["user_id"], date_from=date_from, date_to=date_to)

            # Compute spendings for specified dates
            total = sum([item["price"] for item in purchases])

            return render_template("history.html", categories=categories, purchases=purchases, stats=stats, total=total, total_sum=total_sum)


@app.route("/about")
@login_required
def about():
    return render_template("about.html")