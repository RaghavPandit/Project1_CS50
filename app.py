import requests

from flask import Flask , render_template , request , session , jsonify
from flask_session import Session
from sqlalchemy import create_engine , text
from sqlalchemy.orm import scoped_session , sessionmaker

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


engine = create_engine("postgres://wqibbgekgcwpoz:cc89d30391e4a2ba0c1ef6fed1c5bd1aaf4b77261fff4ae1e9ddba503104f31b@ec2-54-81-37-115.compute-1.amazonaws.com:5432/d87e1o7lok80dh")
db = scoped_session(sessionmaker(bind=engine))

baseUrl = None

@app.route("/")
def home():
    baseUrl = request.base_url
    if session.get("login") is None:
        session['login']=None

    if session['login'] == True and session.get("userId") is not None:
        return render_template("home.html")
    else:
        return render_template("login.html")

@app.route("/signup",methods=["POST"])
def signup():
    user_name = request.form.get("user_name")
    email = request.form.get("email")
    password = request.form.get("password")

    if(user_name and email and password):

        db.execute(text("INSERT INTO users (user_name , email , password) VALUES (:user_name,:email , :password)"),{"user_name":user_name,"email":email,"password":password})
        db.commit()
        session['login']=True
        if session.get("userId") is None:
            session["userId"] = db.execute("SELECT id from users where email=:email",{"email":email}).fetchone()[0]
        return render_template("home.html")
    else:
        return render_template("error.html")

@app.route("/signin",methods=["POST"])
def signin():

    email = request.form.get("email")
    password = request.form.get("password")

    dbemail = db.execute("SELECT email from users where email=:email",{"email":email}).fetchone()
    dbpassword = db.execute("SELECT password from users where email=:email",{"email":email}).fetchone()

    if(dbemail and dbpassword):
        session['login']=True
        if session.get("userId") is None:
            session["userId"] = db.execute("SELECT id from users where email=:email",{"email":email}).fetchone()[0]
        return render_template("home.html")
    else:
        return render_template("error.html") , 403


@app.route("/logout",methods=["GET"])
def logout():
    session['login']=False
    session['userId'] = None
    return render_template("login.html")




@app.route("/search",methods=['POST'])
def search():
    query = request.form.get("search")
    like_string = "%" + query + "%"
    option = request.form.get("search_option")

    if option == "isbn":
        books = db.execute("SELECT * from books where isbn LIKE :like_string",{"like_string":like_string}).fetchall()
    elif option == "title":
        books = db.execute("SELECT * from books where title LIKE :like_string",{"like_string":like_string}).fetchall()
    elif option == "author":
        books = db.execute("SELECT * from books where author LIKE :like_string",{"like_string":like_string}).fetchall()
    elif option == "year":
        books = db.execute("SELECT * from books where year LIKE :like_string",{"like_string":like_string}).fetchall()


    return render_template("search_result.html",books=books,url=request.base_url.replace('search','review'))


@app.route("/api/<string:isbn>")
def api(isbn):
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "THl0ceyM8qUjB5bfO8KpHw", "isbns": isbn})
    if res:
        title = db.execute("SELECT title from books where isbn LIKE :like_string",{"like_string":isbn}).fetchone()[0]
        author = db.execute("SELECT author from books where isbn LIKE :like_string",{"like_string":isbn}).fetchone()[0]
        year = db.execute("SELECT year from books where isbn LIKE :like_string",{"like_string":isbn}).fetchone()[0]
        review_count = res.json()["books"][0]["reviews_count"]
        average_score = res.json()["books"][0]["average_rating"]


        return jsonify(title=title , author=author , year=year , review_count=review_count,average_score=average_score)
    else:
        return jsonify({"success":False}),404

    return res.json()

@app.route("/review/<string:isbn>",methods=["GET","POST"])
def review(isbn):

    res = requests.get(f"{request.base_url.replace('review','api')}").json()
    reviews = db.execute('SELECT review , users.id , rating,user_name FROM reviews JOIN users ON users.id = reviews.id where isbn = :isbn',{"isbn":isbn}).fetchall()

    if request.method == "GET":
        return render_template("review.html",response_data=res,isbn=isbn,reviews=reviews,avoid_review=False)

    if request.method == "POST":
        rating = request.form.get("rating")
        review = request.form.get("review")

        check_id = db.execute('SELECT  * FROM reviews where id = :id and isbn=:isbn',{"id":session["userId"],"isbn":isbn}).fetchall()
        if len(check_id) == 0:
            db.execute("INSERT INTO reviews(id,review,rating,isbn) VALUES(:id,:review,:rating,:isbn)",{"id":session["userId"],"review":review,"rating":rating,"isbn":isbn})
            db.commit()
            allReviews = db.execute('SELECT review , users.id , rating,user_name FROM reviews JOIN users ON users.id = reviews.id where isbn = :isbn',{"isbn":isbn}).fetchall()
            return render_template("review.html",response_data=res,isbn=isbn,reviews=allReviews,avoid_review=False)
        else:
            return render_template("review.html",response_data=res,isbn=isbn,reviews=reviews,avoid_review=True)

@app.route("/submit_review/<string:isbn>")
def submitReview(isbn):
    rating = request.form.get("rating")
    review = request.form.get("review")

    db.execute("INSERT INOT reviews(id,review,rating,isbn) VALUES(:id,:review,:rating,:isbn)",{"id":session["userId"],"review":review,"rating":rating,"isbn":isbn})
    db.commit()
    res = requests.get(f"{request.base_url.replace('submit_review','api')}").json()
    return render_template("review.html",response_data=res,isbn=isbn)
