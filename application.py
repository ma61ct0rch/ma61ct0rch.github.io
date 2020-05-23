import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
# @ is a decorator, indicates that user must be logged in to see this page
@login_required
def index():
    """Show portfolio of stocks"""
    # need to populate a variable to send to index.html
    # ideally a dictionary with fields stock, qty, price, total called session ["transactions"]
    # sql query to determine holdings of current user,
    session["transactions"]=db.execute("SELECT stock, sum(qty) FROM transactions WHERE username = :username GROUP BY stock HAVING sum(qty)>0.01",
    username=session["user_id"])
    # this is a dict with row rows, each row holding a key-value pair called "stock"-value and "sum(qty)"-value
    # populate this dict with current price and current value of holding
    runningtotal = 0
    for row in session["transactions"]:
        quote = lookup(row['stock'])
        row['name'] = quote['name']
        row['price'] = usd(quote['price'])
        row['total'] = usd(quote['price'] * row['sum(qty)'])
        # the dict items seem to be strings so cannot just add the values.....
        runningtotal = runningtotal + quote['price'] * row['sum(qty)']

    # extract and add leftover cash
    session["cash"] = usd(db.execute("SELECT cash FROM users WHERE id = :username", username=session["user_id"])[0]['cash'])
    session["patrimony"] = usd(db.execute("SELECT cash FROM users WHERE id = :username", username=session["user_id"])[0]['cash'] + runningtotal)

    return render_template("index.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # form like quote but also need to ask number of shares
    # query db to see if cash >= price of stock * number of shares
    # need to add 1 or more tables to db
    # for now only users; this holds id, username, pxword hash, cash
    # will need to CREATE TABLE 'transactions' (stock INT, how_many TEXT, who INT)
    # this will keep a track of stock each user currently owns, will also contain history of transactions
    # but will need to add holdings
    if request.method == "POST":

        symbol = request.form.get("symbol")
        try:
            quantity = float(request.form.get("shares"))
        except:
            return apology("quantity must be a number", 403)
        # Ensure symbol and qty were submitted
        if not symbol:
            return apology("must provide symbol", 403)

        elif not quantity:
            return apology("must provide quantity", 403)

        # check not negatve qty
        elif quantity < 0:
            return apology("quantity must be greater than zero", 403)

        # check only whole shares
        elif not quantity.is_integer():
            return apology("quantity must be whole number", 403)

        # make sure input is a numner, we have taken in text

        # get stock quote (dictionary)
        quote = lookup(symbol)
        # Ensure valid symbol
        if quote == None:
            return apology("invalid Symbol", 403)

        # see how much money user has left
        cash = db.execute("SELECT cash FROM users WHERE id = :username", username=session["user_id"])
        # select returns a list of dicts
        # so need to select the first in the list [0] then the key ["cash"] to get the value
        cashleft = cash[0]["cash"]
        # calculate cost of purchase
        cost = quote["price"] * quantity
        # if not enough, apology
        if cashleft < cost:
            return apology("Not enough cash!", 403)

        # if enough, update both tables: users and transactions
        # first, update cash in users table
        db.execute("UPDATE users SET cash = :cash WHERE id = :username", cash=cashleft-cost, username=session["user_id"])
        # next, record transaction in transactions table
        db.execute("INSERT INTO transactions (username, stock, qty, price) VALUES (:username,:stock,:qty,:price)",
        username=session["user_id"], stock=symbol.upper(), qty=quantity, price=cost)
        # Redirect user to home page
        flash('Purchased!')
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    # need to populate a variable to send to history.html
    # ideally a dictionary with fields stock, qty, price, transacted called session ["history"]
    # sql query to determine holdings of current user,
    session["history"]=db.execute("SELECT stock, qty, price, timestamp FROM transactions WHERE username = :username",username=session["user_id"])
    # this is a dict with row rows, each row holding a key-value pair
    # show price of one share
    for row in session["history"]:
        row["price"] = usd(row["price"]/row["qty"])
        # show positive price for sales

    flash('here is your history!')
    return render_template("history.html")


# this is complete, a good model
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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        # len!=1 means the username is not present in the sql db
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        # row[0] represents first line of db (ie the user) ["id"] is the id key for which we want the value
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        flash('logged in!')
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
    # get = display form
    # post = look up symbol and return price: the lookup function already implemented in helpers.py
    # returns python dictionary, so this will need to be manipulated
    # need to handle lookup return value of NONE
    if request.method == "POST":

        # Ensure stock symbol was submitted
        if not request.form.get("stock"):
            return apology("must provide Symbol", 403)

        # get stock quote (dictionary)
        session["quote"] = lookup(request.form.get("stock"))

        if session["quote"] == None:
            return apology("invalid Symbol", 403)

        # Redirect user to quoted page
        flash('Here is your quote!')
        return render_template("quoted.html")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # do this first
    # similar to login.html except add password confirmation field
    # if post = register user, insert into table AFTER error checking
    # username taken, no username,
    # hash password should be stored
    # login and logout already written
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password1"):
            return apology("must provide password", 403)

        # Ensure password was submitted
        elif not request.form.get("password2"):
            return apology("must confirm password", 403)

        elif request.form.get("password2") != request.form.get("password1"):
            return apology("passwords must match", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        # len=1 means the username is already present in the sql db
        if len(rows) == 1:
            return apology("username already exists", 403)

        # username and password are valid
        # insert new user + hash of password + 10000 cash into users database
        # this 10000 may not be necessary as it is initialized by the SQL table "initial value"
        db.execute("INSERT INTO users (username, hash, cash) VALUES (:username, :hash, 10000)",
                          username=request.form.get("username"), hash=generate_password_hash(request.form.get("password1")))

        # now log the user in
        # pretty ugly syntax but remember sql select returns a list of dicts
        # we want the first dict in the list [0] and the column "id" from this dict
        # might be able to do without the [0] if certain there is only one dict returned (as is the case here)
        session["user_id"] = db.execute("SELECT id FROM users WHERE username = :username",
                          username=request.form.get("username"))[0]["id"]

        # Redirect user to home page, should now be logged in
        flash('You registered!')
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        symbol = request.form.get("stock")
        try:
            quantity = float(request.form.get("shares"))
        except:
            return apology("quantity must be a number", 403)

        # Ensure qty submitted
        if not quantity:
            return apology("must provide quantity", 403)

        # Ensure qty not negative...
        if quantity < 0:
            return apology("quantity must not be less than zero", 403)

        # check only whole shares
        elif not quantity.is_integer():
            return apology("quantity must be whole number", 403)

        # get stock quote (dictionary)
        quote = lookup(symbol)

        # see how much many user owns
        shares = db.execute("SELECT sum(qty) FROM transactions WHERE username = :username AND stock = :stock",
        username=session["user_id"], stock=symbol)
        # select returns a list of dicts
        # so need to select the first in the list [0] then the key ["sum(qty)"] to get the value
        try:
            sharesleft = float(shares[0]["sum(qty)"])
        except:
            return apology("you appear to have no shares!", 403)

        # if not enough, apology
        if sharesleft < quantity:
            return apology("Not enough shares!", 403)

        # if enough, update both tables: users and transactions
        # determine value of sale
        value = quote["price"] * quantity
        # see how much cash user has
        cash = db.execute("SELECT cash FROM users WHERE id = :username", username=session["user_id"])
        # select the first in the list [0] then the key ["cash"] to get the value
        cashleft = cash[0]["cash"]

        # first, update cash in users table
        db.execute("UPDATE users SET cash = :cash WHERE id = :username", cash=cashleft+value, username=session["user_id"])

        # next, record transaction in transactions table
        db.execute("INSERT INTO transactions (username, stock, qty, price) VALUES (:username,:stock,:qty,:price)",
        username=session["user_id"], stock=symbol.upper(), qty=-quantity, price=-value)
        # Redirect user to home page
        flash('Sold!')
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        # need to populate list of shares to sell
        session["stockholdings"]=db.execute("SELECT stock FROM transactions WHERE username = :username GROUP BY stock HAVING sum(qty) > 0.01",
        username=session["user_id"])
        return render_template("sell.html")


# dont need to worry about this part
def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
