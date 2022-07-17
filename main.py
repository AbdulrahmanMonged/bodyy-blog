from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, Register, Login, CommentForm
from flask_gravatar import Gravatar
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", '8BYkEfBA6O6donzWlSihBXox7C0sKR6b')
ckeditor = CKEditor(app)
Bootstrap(app)
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    use_ssl=False,
                    base_url=None)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE", "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)


##CONFIGURE TABLES
class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(1200), nullable=False)
    comment_author = relationship("User", back_populates="comments")
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    parent_post = relationship("BlogPost", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True)
    password = db.Column(db.String(1200))
    name = db.Column(db.String(250))
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


def is_admin():
    if current_user.is_authenticated:
        if current_user.id == 1:
            return True
    else:
        return False


def admin_only(function):
    @wraps(function)
    def wrapper(*arg, **kw):
        if is_admin():
            return function(*arg, **kw)
        else:
            return abort(403)

    return wrapper


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    user_logged = current_user
    admin = is_admin()
    return render_template("index.html", all_posts=posts, logged_in=user_logged.is_authenticated, admin=admin)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = Register()
    if request.method == "POST":
        if form.validate_on_submit():
            data = form.data
            generated_password = generate_password_hash(data["password"], salt_length=8)
            try:
                new_user = User(email=data["email"],
                                password=generated_password,
                                name=data["name"])
                db.session.add(new_user)
                db.session.commit()
            except:
                flash("There's an account with the same email address.")
                return redirect("/login")
            else:
                login_user(new_user)
                return redirect("/")
    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = Login()
    if request.method == "POST":
        if form.validate_on_submit():
            data = form.data
            try:
                search_user = User.query.filter_by(email=data["email"])[0]
                user = load_user(search_user.id)
                if check_password_hash(user.password, data["password"]):
                    login_user(user)
                    return redirect("/")
                else:
                    flash("Password incorrect")
                    return redirect("/login")
            except:
                flash("There's no an account associated with this email.")
                return redirect("/login")
    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    all_comments = Comment.query.filter_by(post_id=post_id).all()
    print(all_comments)
    requested_post = BlogPost.query.get(post_id)
    comment_form = CommentForm()
    if request.method == "POST":
        if comment_form.validate_on_submit():
            if current_user.is_authenticated:
                new_comment = Comment(text=comment_form.text_field.data,
                                      comment_author=current_user,
                                      parent_post=BlogPost.query.get(post_id),
                                      )
                db.session.add(new_comment)
                db.session.commit()
                return redirect(url_for("show_post", post_id=post_id))
            else:
                flash("Please Log in First.")
                return redirect("/login")
    return render_template("post.html", post=requested_post,
                           logged_in=current_user.is_authenticated,
                           form=comment_form,
                           admin=is_admin(),
                           comments=all_comments)


@app.route("/about")
def about():
    return render_template("about.html", logged_in=current_user.is_authenticated)


@app.route("/contact")
def contact():
    return render_template("contact.html", logged_in=current_user.is_authenticated)


@app.route("/new-post", methods=["POST", "GET"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, logged_in=current_user.is_authenticated)


@app.route("/edit-post/<int:post_id>", methods=["POST", "GET"])
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id, logged_in=current_user.is_authenticated))

    return render_template("make-post.html", form=edit_form, logged_in=current_user.is_authenticated)


@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts', logged_in=current_user.is_authenticated))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
