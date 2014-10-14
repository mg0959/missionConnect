from flask import render_template, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from datetime import datetime
from app import app, db, lm, oid
from forms import LoginForm, EditForm, PostForm, SearchForm, OpenidLoginForm, SignupForm
from models import User, ROLE_USER, ROLE_ADMIN, Post
from config import POSTS_PER_PAGE, MAX_SEARCH_RESULTS
from emails import follower_notification, signup_notification


@app.route('/')
@app.route('/index')
@app.route('/mc')
def atMC():
    return render_template('atMC.html',
        title = '@MC',
        page = 'atMC')

@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
@app.route('/home/<int:page>', methods=['GET', 'POST'])
@login_required
def home(page=1):
    form = PostForm()
    if form.validate_on_submit():
        post = Post(body = form.post.data, timestamp = datetime.utcnow(), author = g.user)
        db.session.add(post)
        db.session.commit()
        flash('Your post is now live!')
        return redirect(url_for('home'))
    #only followed posts
    posts = g.user.followed_posts().paginate(page, POSTS_PER_PAGE, False)
    #all posts
    #posts = Post.query.order_by(Post.timestamp.desc()).paginate(page, POSTS_PER_PAGE, False)
    return render_template('home.html',
        title = 'Home',
        form=form,
        posts = posts,
        page = 'home')

@app.route('/login', methods = ['GET', 'POST'])
def login():
    if g.user is not None and g.user.is_authenticated():
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        session['remember_me'] = form.remember_me.data
        #return oid.try_login(form.openid.data, ask_for = ['nickname', 'email'])
        return validateLogin(form.email.data, form.password.data)
    return render_template('login.html', 
        title = 'Sign In',
        form = form,
        page = 'login')

def validateLogin(email, password):
    print "after login"
    if email is None or email == "":
        flash('Invalid login. Please try again.')
        return redirect(url_for('login'))
    user = User.query.filter_by(email = email).first()
    if user is None:
        flash('Invalid email. Please try again')
        return redirect(url_for('login'))
    if not user.check_password(password):
        flash('Invalid password. Please try again')
        return redirect(url_for('login'))
    remember_me = False
    if 'remember_me' in session:
        remember_me = session['remember_me']
        session.pop('remember_me', None)
    login_user(user, remember = remember_me)
    return redirect(request.args.get('next') or url_for('home'))


@app.route('/loginOpenID', methods = ['GET', 'POST'])
@oid.loginhandler
def oid_login():
    if g.user is not None and g.user.is_authenticated():
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        session['remember_me'] = form.remember_me.data
        return oid.try_login(form.openid.data, ask_for = ['nickname', 'email'])
    return render_template('login.html', 
        title = 'Sign In',
        form = form,
        providers = app.config['OPENID_PROVIDERS'])

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/register', methods =['GET', 'POST'])
def register():
    if g.user is not None and g.user.is_authenticated():
        flash('Please logout before registering a new user.')
        return redirect(url_for('home'))
    form = SignupForm()
    if form.validate_on_submit():
        # check if email in use
        if User.query.filter_by(email = form.email.data).first() is not None:
            flash('Email already in use.  Please use another.')
            form.email.errors.append('Invalid Email')
            return redirect(url_for('register'))
        # check nickname
        if User.query.filter_by(nickname = form.nickname.data).first() is not None:
            flash('Nickname already in use.  Please use another.')
            form.nickname.errors.append('Invalid Nickname')
            return redirect(url_for('register'))
        # check passwords
        if form.password.data != form.password_confirm.data:
            flash('Passwords do not match!')
            form.password_confirm.errors.append('Password does not match')
            return redirect(url_for('register'))

        #Sign up user
        u = User(nickname=form.nickname.data, email=form.email.data)
        u.set_password(form.password.data)
        db.session.add(u)
        db.session.commit()
        db.session.add(u.follow(u))
        db.session.commit()        
        flash('You are now signed up!')
        #send emaiil
        signup_notification(u)
        #redirect to login
        return redirect(url_for('login'))
    return render_template('signup.html', 
        title = 'Register',
        form = form)
    
    

@app.route('/user/<nickname>')
@app.route('/user/<nickname>/<int:page>')
@login_required
def user(nickname, page=1):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname + ' not found.')
        return redirect(url_for('home'))
    posts = user.posts.paginate(page, POSTS_PER_PAGE, False)
    return render_template('user.html',
        user = user,
        posts = posts,
        page='user')

@app.route('/edit', methods = ['GET', 'POST'])
@login_required
def edit():
    form = EditForm(g.user.nickname)
    if form.validate_on_submit():
        g.user.nickname = form.nickname.data
        g.user.about_me = form.about_me.data
        db.session.add(g.user)
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit'))
    else:
        form.nickname.data = g.user.nickname
        form.about_me.data = g.user.about_me
    return render_template('edit.html',
        form = form)

@app.route('/follow/<nickname>')
@login_required
def follow(nickname):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname + ' not found.')
        return redirect(url_for('home'))
    if user == g.user:
        flash('You can\'t follow yourself!')
        return redirect(url_for('user', nickname = nickname))
    u = g.user.follow(user)
    if u is None:
        flash('Cannot follow ' + nickname + '.')
        return redirect(url_for('user', nickname = nickname))
    db.session.add(u)
    db.session.commit()
    
    follower_notification(user, g.user)
    flash('You are now following ' + nickname + '!')
    return redirect(url_for('user', nickname = nickname))

@app.route('/unfollow/<nickname>')
@login_required
def unfollow(nickname):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname + ' not found.')
        return redirect(url_for('home'))
    if user == g.user:
        flash('You can\'t unfollow yourself!')
        return redirect(url_for('user', nickname = nickname))
    u = g.user.unfollow(user)
    if u is None:
        flash('Cannot unfollow ' + nickname + '.')
        return redirect(url_for('user', nickname = nickname))
    db.session.add(u)
    db.session.commit()
    flash('You have stopped following ' + nickname + '.')
    return redirect(url_for('user', nickname = nickname))


@app.route('/explore')
@app.route('/explore/<int:page>')
@login_required
def explore(page = 1):
    #only unollowed posts
    posts = g.user.unfollowed_posts().paginate(page, POSTS_PER_PAGE, False)
    #all posts
    #posts = Post.query.order_by(Post.timestamp.desc()).paginate(page, POSTS_PER_PAGE, False)
    return render_template('explore.html',
        title = 'Explore',
        posts = posts,
        page = 'explore')

@app.route('/pray')
@login_required
def pray():
    return render_template('pray.html',
        title = 'Pray',
        page = 'pray')


@app.route('/search', methods=['POST'])
@login_required
def search():
    if not g.search_form.validate_on_submit():
        return redirect(url_for('home'))
    return redirect(url_for('search_results', query=g.search_form.search.data))

@app.route('/search_results/<query>')
@login_required
def search_results(query):
    # returns matching posts from followed users
    results = g.user.followed_posts().whoosh_search(query, MAX_SEARCH_RESULTS).all()
    # returns all matching posts
    # Post.query.whoosh_search(query, MAX_SEARCH_RESULTS).all()
    return render_template('search_results.html',
                           query=query,
                           results=results)
@lm.user_loader
def load_user(id):
    return User.query.get(int(id))


@oid.after_login
def after_oidlogin(resp):
    print "after login"
    if resp.email is None or resp.email == "":
        flash('Invalid login. Please try again.')
        return redirect(url_for('login'))
    user = User.query.filter_by(email = resp.email).first()
    if user is None:
        nickname = resp.nickname
        if nickname is None or nickname == "":
            nickname = resp.email.split('@')[0]
        nickname = User.make_unique_nickname(nickname)
        user = User(nickname = nickname, email = resp.email, role = ROLE_USER)
        db.session.add(user)
        db.session.commit()
        # make the user follow him/herself
        db.session.add(user.follow(user))
        db.session.commit()
    remember_me = False
    if 'remember_me' in session:
        remember_me = session['remember_me']
        session.pop('remember_me', None)
    login_user(user, remember = remember_me)
    return redirect(request.args.get('next') or url_for('home'))

@app.before_request
def before_request():
    g.user = current_user
    if g.user.is_authenticated():
        g.user.last_seen = datetime.utcnow()
        db.session.add(g.user)
        db.session.commit()
        g.search_form = SearchForm()

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

