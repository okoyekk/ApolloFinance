import os
import sqlite3
import sys
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from flask import Flask, render_template, redirect, session, request, flash
from flask_session import Session
from tempfile import mkdtemp
from helpers import error, login_required


# configure application
app = Flask(__name__)
# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response
# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True
# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


@app.route("/")
@login_required
def index():
   # connect the finance database and set the cursor as "db"
    with sqlite3.connect("finance.db", check_same_thread=False) as con:
        user_id = session["user_id"]
        db = con.cursor()
        db.execute("SELECT task, due_date FROM tasks WHERE user_id = :user_id AND completed = 'NO'", dict(user_id = user_id))
        tasks = db.fetchall()
        db.execute("SELECT cash, name FROM users WHERE id = :user_id", dict(user_id = user_id))
        cash = db.fetchall()
        task_list = []
        date_list = []
        num_list = []
        n = 0
        for _ in tasks:
            task_list.append(tasks[n][0])
            date_list.append(tasks[n][1])
            num_list.append(n)
            n += 1
        cash_val = cash[0][0]
        name = cash[0][1]
        return render_template("index.html", tasks = task_list, dates = date_list, cash = cash_val, name = name, num = num_list, len = len(num_list))

@app.route("/register", methods=['GET', 'POST'])
def register():
    # loads register page if the method is get
    if request.method == "GET":
        return render_template("register.html")
    else:
        # connect the finance database and set the cursor as "db"
        with sqlite3.connect("finance.db", check_same_thread=False) as con:
            db = con.cursor()
            username = request.form.get("username")
            name = request.form.get("name")
            email = request.form.get("email")
            if not username:
                return error("You must provide a username", 403)
            elif not name:
                return error("You must provide your Name", 403)
            elif not email:
                return error("You must provide your email", 403)
            db.execute("SELECT username FROM users WHERE username = :username", dict(username = username))
            if db.fetchall() == username:
                return error("Username is taken, select another", 403)
            else:
                hash = generate_password_hash(request.form.get("password"))
                db.execute("INSERT INTO users (username, name, email, hash) VALUES (?, ?, ?, ?)", (username, name, email, hash))
                con.commit()
                return redirect("/login")


@app.route("/login", methods=['GET', 'POST'])
def login():
    # Forget any user_id
    session.clear()
    with sqlite3.connect("finance.db", check_same_thread=False) as con:
        db = con.cursor()
        if request.method == "POST":
            # Ensure username was submitted
            if not request.form.get("username"):
                return error("must provide username", 403)
            # Ensure password was submitted
            elif not request.form.get("password"):
                return error("must provide password", 403)
            # Query database for username
            db.execute("SELECT * FROM users WHERE username = :username", dict(username=request.form.get("username")))
            rows = db.fetchall()
            # Ensure username exists and password is correct
            if len(rows) != 1 or not check_password_hash(rows[0][5], request.form.get("password")):
                return error("invalid username or password", 403)
            # Remember which user has logged in
            session["user_id"] = rows[0][0]
            # Redirect user to index page
            return redirect("/")
        else:
            return render_template("login.html")


@app.route("/add_task", methods=['GET', 'POST'])
@login_required
def add_task():
    with sqlite3.connect("finance.db", check_same_thread=False) as con:
        db = con.cursor()
        if request.method == "POST":
            user_id = session["user_id"]
            task = request.form.get("task")
            due_date = request.form.get("due_date")
            db.execute("INSERT INTO tasks (user_id, task, due_date) VALUES (?, ?, ?)", (user_id, task, due_date))
            con.commit()
            return redirect("/")
        else:
            return render_template("add_tasks.html")


@app.route("/complete_task", methods=['GET', 'POST'])
@login_required
def complete_task():
    
        if request.method == "POST":
            with sqlite3.connect("finance.db", check_same_thread=False) as con:
                db = con.cursor()
                user_id = session["user_id"]
                task = request.form.get("tasks")
                yes = "YES"
                db.execute("UPDATE tasks SET completed = ? WHERE id = ?", (yes, task))
                con.commit()
                return redirect("/")
        else:
            with sqlite3.connect("finance.db", check_same_thread=False) as con:
                user_id = session["user_id"]
                db = con.cursor()
                db.execute("SELECT task, id FROM tasks WHERE user_id = :user_id AND completed = 'NO'", dict(user_id = user_id))
                tasks = db.fetchall()
                task_list = []
                id_list = []
                num_list = []
                n = 0
                for _ in tasks:
                    task_list.append(tasks[n][0])
                    id_list.append(tasks[n][1])
                    num_list.append(n)
                    n += 1
                return render_template("complete_tasks.html", tasks = task_list, id = id_list, num = num_list, len = len(num_list))


@app.route("/transaction", methods=['GET'])
@login_required
def transaction():
    return render_template("transaction.html")
    

@app.route('/purchase', methods=['POST'])
@login_required
def purchase():
    with sqlite3.connect("finance.db", check_same_thread=False) as con:
        db = con.cursor()
        user_id = session["user_id"]
        title = request.form.get("title")
        cost = int(request.form.get("cost"))
        db.execute("SELECT cash FROM users WHERE id = :user_id", dict(user_id = user_id))
        cash_old = db.fetchall()
        cash = cash_old[0][0]
        if cash < cost:
            return error("Funds not sufficient for purchase, Try adding funds to Account", 402)
        else:
            cash_updated = cash - cost
            db.execute("INSERT INTO transactions (user_id, title, value) VALUES (?, ?, ?)", (user_id, title, cost))
            db.execute("UPDATE users SET cash = ? WHERE id = ?", (cash_updated, user_id))
            return redirect("/")


@app.route('/sale', methods=['POST'])
@login_required
def sale():
    with sqlite3.connect("finance.db", check_same_thread=False) as con:
        db = con.cursor()
        user_id = session["user_id"]
        title = request.form.get("title")
        price = int(request.form.get("price"))
        db.execute("SELECT cash FROM users WHERE id = :user_id", dict(user_id = user_id))
        cash_old = db.fetchall()
        cash = cash_old[0][0]
        cash_updated = cash + price
        db.execute("INSERT INTO transactions (user_id, title, value) VALUES (?, ?, ?)", (user_id, title, price))
        db.execute("UPDATE users SET cash = ? WHERE id = ?", (cash_updated, user_id))
        return redirect("/")


@app.route('/add', methods=['POST'])
@login_required
def add():
    with sqlite3.connect("finance.db", check_same_thread=False) as con:
        db = con.cursor()
        user_id = session["user_id"]
        title = "MONEY ADDED"
        amount = int(request.form.get("amount"))
        db.execute("SELECT cash FROM users WHERE id = :user_id", dict(user_id = user_id))
        cash_old = db.fetchall()
        cash = cash_old[0][0]
        cash_updated = cash + amount
        db.execute("INSERT INTO transactions (user_id, title, value) VALUES (?, ?, ?)", (user_id, title, amount))
        db.execute("UPDATE users SET cash = ? WHERE id = ?", (cash_updated, user_id))
        return redirect("/")


@app.route('/withdraw', methods=['POST'])
@login_required
def withdraw():
    with sqlite3.connect("finance.db", check_same_thread=False) as con:
        db = con.cursor()
        user_id = session["user_id"]
        title = "MONEY WITHDRAWN"
        amount = int(request.form.get("amount"))
        db.execute("SELECT cash FROM users WHERE id = :user_id", dict(user_id = user_id))
        cash_old = db.fetchall()
        cash = cash_old[0][0]
        cash_updated = cash - amount
        db.execute("INSERT INTO transactions (user_id, title, value) VALUES (?, ?, ?)", (user_id, title, amount))
        db.execute("UPDATE users SET cash = ? WHERE id = ?", (cash_updated, user_id))
        return redirect("/")


@app.route("/calculator", methods=['GET'])
@login_required
def calculator():
    return render_template("calculator.html", title = "Calculator")

@app.route("/simple_interest", methods=['POST'])
@login_required
def simple_interest():
    principle = float(request.form.get("principle"))
    rate = float(request.form.get("rate"))
    time = float(request.form.get("time"))
    simple_interest = (principle * rate * time) / 100
    amount = simple_interest + principle
    return render_template("calculator.html", title = "Simple interest", principle = principle, rate = rate, time = time, simple_interest = simple_interest, amount = amount)


@app.route("/compound_interest", methods=['POST'])
@login_required
def compound_interest():
    principle = float(request.form.get("principle"))
    rate = float(request.form.get("rate"))
    time = float(request.form.get("time"))
    compound_interest = (principle * (1 + ((rate/100) ** time)))
    amount = compound_interest + principle
    return render_template("calculator.html", title = "Compound interest", principle = principle, rate = rate, time = time, compound_interest = compound_interest, amount = amount)


@app.route("/profitability", methods=['POST'])
@login_required
def profitability():
    initial_value = float(request.form.get("initial_value"))
    final_value = float(request.form.get("final_value"))
    profitability = ((final_value - initial_value)/initial_value)*100
    return render_template("calculator.html", title = "Profitability", profitability = profitability, initial_value = initial_value, final_value = final_value)


@app.route("/profit_margin", methods=['POST'])
@login_required
def profit_margin():
    # PM = net income/revenue * 100
    net_income = float(request.form.get("net_income"))
    revenue = float(request.form.get("revenue"))
    profit_margin = (net_income / revenue) * 100
    return render_template("calculator.html", title = "Profit margin", net_income = net_income, revenue = revenue, profit_margin = profit_margin)
    

@app.route("/history", methods=['GET'])
@login_required
def history():
    with sqlite3.connect("finance.db", check_same_thread=False) as con:
        db = con.cursor()
        user_id = session["user_id"]
        db.execute("SELECT title, value, date FROM transactions WHERE user_id = :user_id", dict(user_id = user_id))
        rows = db.fetchall()
        title_list = []
        value_list = []
        date_list = []
        num_list = []
        n = 0
        for _ in rows:
            title_list.append(rows[n][0])
            value_list.append(rows[n][1])
            date_list.append(rows[n][2])
            num_list.append(n)
            n += 1
        return render_template("history.html", titles = title_list, values = value_list, dates = date_list, num = num_list, len = len(num_list))


@app.route("/password_change", methods=['GET', 'POST'])
def password_change():
    if request.method == "GET":
        return render_template("password_change.html")
    else:
        with sqlite3.connect("finance.db", check_same_thread=False) as con:
            db = con.cursor()
            username = request.form.get("username")
            old_password = request.form.get("old_password")
            new_password = request.form.get("new_password")
            if not username:
                return error("You must provide your username", 403)
            db.execute("SELECT * FROM users WHERE username = :username", dict(username=request.form.get("username")))
            rows = db.fetchall()
            if len(rows) != 1 or not check_password_hash(rows[0][5], old_password):
                return error("invalid username and/or password", 403)
            else:
                new_hash = generate_password_hash(new_password)
                db.execute("UPDATE users SET hash = ? WHERE username = ?", (new_hash, username))
                con.commit()
                return redirect("/login")

@app.route("/logout")
def logout():
    return redirect("/login")


if __name__ == "__main__":
  app.run(debug=True)



def errorhandler(e):
    # Handle error
    if not isinstance(e, HTTPException):
        e = InternalServerError()
        return error(e.name, e.code)
  # Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)