import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
#if not os.environ.get("API_KEY"):
#    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    stocks=db.execute("select symbol,number from stocks where user=?",session.get("user_id"))
    cash=db.execute("select cash from users where id=?",session.get("user_id"))[0]["cash"]
    TOTAL=cash
    for s in stocks:
        s["name"]=lookup(s["symbol"])["name"]
        s["price"]=lookup(s["symbol"])["price"]
        s["total"]=float(s["price"])*float(s["number"])
        TOTAL=TOTAL+s["total"]
    return render_template("index.html",stocks=stocks,cash=cash,TOTAL=TOTAL)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method=="POST":
        try:
            float(request.form.get("shares")).is_integer()
        except:
            return apology("Invalid Input")
        if not (lookup(request.form.get("symbol")) and (float(request.form.get("shares")).is_integer()) and float(request.form.get("shares"))>0):
            return apology("Invalid Input")
        price=lookup(request.form.get('symbol'))['price']
        num=int(request.form.get("shares"))
        cost=price*num
        cash=db.execute("SELECT cash FROM users WHERE id IS ?",session.get("user_id"))[0]["cash"]
        if cost>cash:
            return apology("Too Expensive")
        db.execute("UPDATE users SET cash=? WHERE id=?",cash-cost, session.get("user_id"))
        cshares=db.execute("SELECT number FROM stocks WHERE user=? AND symbol=?",session.get("user_id"),request.form.get("symbol"))
        try:
            cshares=cshares[0]["number"]
            db.execute("UPDATE stocks SET number=? WHERE user=? AND symbol=?",float(cshares)+float(request.form.get("shares")),session.get("user_id"),request.form.get("symbol"))
        except:
            cshares=0
            db.execute("INSERT INTO stocks (user,symbol,number) VALUES(?,?,?)",session.get("user_id"),request.form.get("symbol"),float(request.form.get("shares")))
        db.execute("INSERT INTO history (user, symbol, shares, price, time) VALUES (?, ?, ?, ?, date('now') ||'T'|| time('now'))",session.get("user_id"),request.form.get("symbol"),float(request.form.get("shares")),price)
        return redirect("/")
    else:
        return render_template("buy.html") #todo

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method=="POST":
        if not request.form.get("symbol"):
            return apology("No Input")
        data=lookup(request.form.get("symbol"))
        if not data:
            return apology("No Such Symbol")
        return render_template("quoted.html", name=data["name"],symbol=data["symbol"],price=data["price"])
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method=="POST":
        name=request.form.get("username")
        password=request.form.get("password")
        confirmation=request.form.get("confirmation")
        if password!=confirmation:
            return apology("Passwords do not match")
        if not (name and password and confirmation):
            return apology("Input missing")
        if (db.execute("SELECT * FROM users WHERE username=?",name)):
            return apology("Duplicate Username")
        db.execute("INSERT INTO users (username,hash) VALUES(?,?)",name,generate_password_hash(password))
        return redirect("/")
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method=="POST":
        if not (lookup(request.form.get("symbol")) and (float(request.form.get("shares")).is_integer())):
            return apology("Invalid Input")
        cshares=db.execute("SELECT number FROM stocks WHERE user=? AND symbol=?",session.get("user_id"),request.form.get("symbol"))
        cshares=cshares[0]["number"]
        if not cshares:
            return apology("No Shares Owned.")
        price=lookup(request.form.get('symbol'))['price']
        num=int(request.form.get("shares"))
        if num>cshares:
            return apology("Not Enough Shares")
        cost=price*num
        cash=db.execute("SELECT cash FROM users WHERE id IS ?",session.get("user_id"))[0]["cash"]
        db.execute("UPDATE users SET cash=? WHERE id=?",cash+cost, session.get("user_id"))
        db.execute("UPDATE stocks SET number=? WHERE user=? AND symbol=?",float(cshares)-float(request.form.get("shares")),session.get("user_id"),request.form.get("symbol"))
        db.execute("INSERT INTO history (user, symbol, shares, price, time) VALUES (?, ?, ?, ?, date('now') ||'T'|| time('now'))",session.get("user_id"),request.form.get("symbol"),0-float(request.form.get("shares")),price)
        return redirect("/")
    else:
        symbols=db.execute("SELECT symbol FROM stocks WHERE user=?",session.get("user_id"))
        return render_template("sell.html",symbols=symbols)
