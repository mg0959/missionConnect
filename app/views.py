from flask import render_template, flash, redirect, session, url_for, request, g, send_from_directory, jsonify
from flask.ext.login import login_user, logout_user, current_user, login_required
from datetime import datetime
from app import app, db, lm, oid
from forms import LoginForm, EditForm, PostForm, SearchForm, OpenidLoginForm, SignupForm, CreateGroupForm, EditGroupForm
from models import User, ROLE_USER, ROLE_ADMIN, Post, GENERAL_POST, PRAYER_POST, Photo, Group
from config import POSTS_PER_PAGE, MAX_SEARCH_RESULTS, DATABASE_QUERY_TIMEOUT, SQLALCHEMY_RECORD_QUERIES
from config import UPLOAD_IMG_DIR, ALLOWED_EXTENSIONS
from emails import follower_notification, signup_notification
from flask.ext.sqlalchemy import get_debug_queries
from werkzeug import secure_filename
import os


@app.route('/')
@app.route('/index')
@app.route('/mc')
def atMC():
    return render_template('atMC.html',
        title = '@MC',
        page = 'atMC')

@app.route('/home')
@app.route('/home/<int:page>')
@app.route('/home/<int:page>/<theme>')
@login_required
def home(page=1, theme=None):    
    #only followed posts
    posts = g.user.followed_posts().paginate(page, POSTS_PER_PAGE, False)
    
    return render_template('home.html', title = 'Home', posts = posts, page = 'home', theme=theme)

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
    if email is None or email == "":
        flash('Invalid login. Please try again.', 'error')
        return redirect(url_for('login'))
    user = User.query.filter_by(email = email).first()
    if user is None:
        flash('Invalid email. Please try again', 'error')
        return redirect(url_for('login'))
    if not user.check_password(password):
        flash('Invalid password. Please try again', 'error')
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
    return redirect(url_for('atMC'))

@app.route('/register', methods =['GET', 'POST'])
def register():
    if g.user is not None and g.user.is_authenticated():
        flash('Please logout before registering a new user.', 'warning')
        return redirect(url_for('home'))
    form = SignupForm()
    if form.validate_on_submit():
        # check if email in use
        if User.query.filter_by(email = form.email.data).first() is not None:
            flash('Email already in use.  Please use another.', 'error')
            form.email.errors.append('Invalid Email')
            return redirect(url_for('register'))
        # check nickname
        if User.query.filter_by(nickname = form.nickname.data).first() is not None:
            flash('Nickname already in use.  Please use another.', 'error')
            form.nickname.errors.append('Invalid Nickname')
            return redirect(url_for('register'))
        # check passwords
        if form.password.data != form.password_confirm.data:
            flash('Passwords do not match!', 'error')
            form.password_confirm.errors.append('Password does not match')
            return redirect(url_for('register'))

        #Sign up user
        u = User(nickname=form.nickname.data, email=form.email.data)
        u.set_password(form.password.data)
        db.session.add(u)
        db.session.commit()
        db.session.add(u.follow(u))
        db.session.commit()        
        flash('You are now signed up!', 'success')
        #send emaiil
        signup_notification(u)
        #redirect to login
        return redirect(url_for('login'))
    return render_template('signup.html', 
        title = 'Register',
        form = form,
        page = 'signup')
    
    

@app.route('/user/<nickname>', methods=['GET', 'POST'])
@app.route('/user/<nickname>/<int:page>', methods=['GET', 'POST'])
@login_required
def user(nickname, page=1):    
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname + ' not found.', 'error')
        return redirect(url_for('home'))

    form = PostForm()
    form.postType.choices = [(GENERAL_POST, "Post"), (PRAYER_POST, "Prayer")]
    if form.validate_on_submit():
        post = Post(body = form.post.data, timestamp = datetime.utcnow(), author = g.user, postType=form.postType.data)
        db.session.add(post)
        db.session.commit()
        if form.postType.data == PRAYER_POST:    
            flash('Your prayer post is now live!', 'info')
        else:
            flash('Your post is now live!', 'info')
        return redirect(url_for('user', nickname=nickname))

    form.postType.data = GENERAL_POST
    
    posts = user.posts.order_by(Post.timestamp.desc()).paginate(page, POSTS_PER_PAGE, False)
    return render_template('user.html',
        user = user,
        form=form,
        posts = posts,
        page='user')

@app.route('/edit', methods = ['GET', 'POST'])
@login_required
def edit():
    form = EditForm(g.user.nickname)
    if request.method == 'POST': avatar_img_file = request.files[form.avatar_img.name]
    else: avatar_img_file = None
    if form.validate_on_submit(avatar_img_file):            
        g.user.nickname = form.nickname.data
        g.user.about_me = form.about_me.data
        db.session.add(g.user)
        db.session.commit()
        if form.avatar_img.data:
            oldPic = g.user.photos.filter(Photo.isAvatar == True).first()
            f = request.files[form.avatar_img.name]
            pic = Photo(fname = "", timestamp = datetime.utcnow(), owner = g.user)
            if oldPic:
                oldPic.isAvatar = False
                db.session.add(oldPic)
            db.session.add(pic)
            db.session.commit()
            #try:
            pic.fname = (str(pic.id)+"."+f.filename.split(".")[-1])
            f.save(os.path.join(UPLOAD_IMG_DIR, pic.fname))
            g.user.set_avatar(pic)
            db.session.add(pic)
            db.session.add(g.user)
            if oldPic: db.session.delete(oldPic)
            db.session.commit()
            if oldPic: oldPic.delete_files()
            '''except:
                db.session.rollback()
                if oldPic:
                    oldPic.isAvatar=True
                    db.session.add(oldPic)
                db.session.delete(pic)
                db.session.commit()
                flash('Unable to update photo.', 'error')'''
                
        flash('Your changes have been saved.', 'info')
        return redirect(url_for('user', nickname=g.user.nickname))
    else:
        form.nickname.data = g.user.nickname
        form.about_me.data = g.user.about_me
    return render_template('edit.html',
        form = form,
        user = g.user)

@app.route('/follow/<nickname>')
@login_required
def follow(nickname):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname + ' not found.', 'error')
        return redirect(url_for('home'))
    if user == g.user:
        flash('You can\'t follow yourself!', 'error')
        return redirect(url_for('user', nickname = nickname))
    u = g.user.follow(user)
    if u is None:
        flash('Cannot follow ' + nickname + '.', 'error')
        return redirect(url_for('user', nickname = nickname))
    db.session.add(u)
    db.session.commit()
    
    follower_notification(user, g.user)
    flash('You are now following ' + nickname + '!', 'info')
    return redirect(url_for('user', nickname = nickname))

@app.route('/unfollow/<nickname>')
@login_required
def unfollow(nickname):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname + ' not found.', 'error')
        return redirect(url_for('home'))
    if user == g.user:
        flash('You can\'t unfollow yourself!', 'error')
        return redirect(url_for('user', nickname = nickname))
    u = g.user.unfollow(user)
    if u is None:
        flash('Cannot unfollow ' + nickname + '.', 'error')
        return redirect(url_for('user', nickname = nickname))
    db.session.add(u)
    db.session.commit()
    flash('You have stopped following ' + nickname + '.', 'info')
    return redirect(url_for('user', nickname = nickname))

@app.route('/user/<nickname>/followers')
@app.route('/user/<nickname>/followers/<int:page>')
@login_required
def followers(nickname, page=1):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname + ' not found.', 'error')
        return redirect(url_for('home'))
    profiles = user.followers.filter(User.nickname != user.nickname).order_by(User.nickname.asc()).paginate(page, POSTS_PER_PAGE, False)
    return render_template('followers.html',
        user = user,
        profiles = profiles)

@app.route('/user/<nickname>/following')
@app.route('/user/<nickname>/following/<int:page>')
@login_required
def following(nickname, page=1):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname + ' not found.', 'error')
        return redirect(url_for('home'))
    profiles = user.followed.filter(User.nickname != user.nickname).order_by(User.nickname.asc()).paginate(page, POSTS_PER_PAGE, False)
    return render_template('following.html',
        user = user,
        profiles = profiles)

########################################
# Group Function Views
########################################

@app.route('/group/<group_name>', methods=['GET', 'POST'])
@app.route('/group/<group_name>/<int:page>', methods=['GET', 'POST'])
@login_required
def group(group_name, page=1):
    gr = Group.query.filter(Group.name==group_name).first()
    if not gr:
        flash("'"+group_name+"' does not exist!", 'error')
        return redirect(url_for('home'))

    postForm = PostForm()
    postForm.postType.choices = [(GENERAL_POST, "Post"), (PRAYER_POST, "Prayer")]
    if postForm.validate_on_submit():
        post = Post(body = postForm.post.data, timestamp = datetime.utcnow(), author = g.user, group=gr, postType=postForm.postType.data)
        db.session.add(post)
        db.session.commit()
        if postForm.postType.data == PRAYER_POST:    
            flash('Your prayer post is now live!', 'info')
        else:
            flash('Your post is now live!', 'info')
        return redirect(url_for('group', group_name=group_name))

    postForm.postType.data = GENERAL_POST
    posts = Post.query.filter(Post.group_id == gr.id).order_by(Post.timestamp.desc()).paginate(page, POSTS_PER_PAGE, False)
    return render_template('group.html',
                           group=gr,
                           posts=posts,
                           form=postForm,
                           page="group")

@app.route('/group/<group_name>/followers')
@app.route('/group/<group_name>/followers/<int:page>')
@login_required
def groupFollowers(group_name, page=1):
    gr = Group.query.filter_by(name = group_name).first()
    if gr == None:
        flash('group ' + group_name + ' not found.', 'error')
        return redirect(url_for('home'))
    profiles = gr.followers.order_by(User.nickname.asc()).paginate(page, POSTS_PER_PAGE, False)
    return render_template('groupFollowers.html',
        group = gr,
        profiles = profiles)


@app.route('/manageGroup/<group_name>', methods=['GET', 'POST'])
@login_required
def manageGroup(group_name):
    editGroupForm = EditGroupForm(group_name)
    group = Group.query.filter_by(name=group_name).first()
    if not group:
        flash("'"+group_name+"' does not exist!", 'error')
        redirect(url_for('home'))
        
    if g.user != group.creator:
        flash("You are not authorized to manage the group '"+group_name+"'!", 'error')
        redirect(url_for('group', name=group_name))
        
    if request.method == 'POST': avatar_img_file = request.files[editGroupForm.avatar_img.name]
    else: avatar_img_file = None

    if editGroupForm.validate_on_submit(avatar_img_file):
        group.name = editGroupForm.name.data
        group.about = editGroupForm.about.data
        db.session.add(group)
        db.session.commit()
        if editGroupForm.avatar_img.data:
            if group.avatar_photo != None: oldPic = Photo.query.get(group.avatar_photo)
            else: oldPic = None
            f = request.files[editGroupForm.avatar_img.name]
            pic = Photo(fname = "", timestamp = datetime.utcnow(), owner = g.user)
            db.session.add(pic)
            db.session.commit()
            #try:
            pic.fname = (str(pic.id)+"."+f.filename.split(".")[-1])
            f.save(os.path.join(UPLOAD_IMG_DIR, pic.fname))
            group.set_avatar(pic)
            db.session.add(pic)
            db.session.add(group)
            if oldPic: db.session.delete(oldPic)
            db.session.commit()
            if oldPic: oldPic.delete_files()
            '''except:
                db.session.rollback()
                if oldPic:
                    oldPic.isAvatar=True
                    db.session.add(oldPic)
                db.session.delete(pic)
                db.session.commit()
                flash('Unable to update photo.', 'error')'''
                
        flash('Your changes have been saved.', 'info')
        return redirect(url_for('group', group_name=group_name))
    else:
        editGroupForm.name.data = group.name
        editGroupForm.about.data = group.about
        
    return render_template('manageGroup.html',
        editGroupForm = editGroupForm,
        group = group)

##@app.route('/createGroup', methods=['POST'])
##@login_required
##def createGroup():
##    if not g.search_form.validate_on_submit():
##        return redirect(url_for('home'))
##    return redirect(url_for('search_results', searchType=g.search_form.searchType.data, query=g.search_form.search.data))

@app.route('/followGroup/<group_name>')
@login_required
def followGroup(group_name):
    group = Group.query.filter_by(name = group_name).first()
    if group == None:
        flash("Group '" + group_name + "' not found.", 'error')
        return redirect(url_for('home'))

    u = g.user.follow_group(group)
    if u is None:
        flash('Cannot follow ' + group_name + '.', 'error')
        return redirect(url_for('group', group_name=group_name))
    db.session.add(u)
    db.session.commit()

    #follower_notification(group.creator, g.user)
    flash('You are now following ' + group_name + '!', 'info')
    return redirect(url_for('group', group_name = group_name))

##@app.route('/unfollow/<nickname>')
##@login_required
##def unfollow(nickname):
##    user = User.query.filter_by(nickname = nickname).first()
##    if user == None:
##        flash('User ' + nickname + ' not found.', 'error')
##        return redirect(url_for('home'))
##    if user == g.user:
##        flash('You can\'t unfollow yourself!', 'error')
##        return redirect(url_for('user', nickname = nickname))
##    u = g.user.unfollow(user)
##    if u is None:
##        flash('Cannot unfollow ' + nickname + '.', 'error')
##        return redirect(url_for('user', nickname = nickname))
##    db.session.add(u)
##    db.session.commit()
##    flash('You have stopped following ' + nickname + '.', 'info')
##    return redirect(url_for('user', nickname = nickname))


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
@app.route('/pray/<int:page>')
@login_required
def pray(page = 1):
    posts = Post.getPrayer().order_by(Post.timestamp.desc()).paginate(page, POSTS_PER_PAGE, False)
    return render_template('pray.html',
        title = 'Pray',
        posts = posts,
        page = 'pray')


@app.route('/search', methods=['POST'])
@login_required
def search():
    if not g.search_form.validate_on_submit():
        return redirect(url_for('home'))
    return redirect(url_for('search_results', searchType=g.search_form.searchType.data, query=g.search_form.search.data))

@app.route('/search_results/<searchType>/<query>')
@login_required
def search_results(searchType, query):
    print "searchType", searchType
    if searchType=="Posts":
        results = g.user.followed_posts().whoosh_search(query, MAX_SEARCH_RESULTS).all()
        # Post.query.whoosh_search(query, MAX_SEARCH_RESULTS).all()
    elif searchType =="Users":
        results = User.query.filter(User.nickname.ilike("%"+str(query)+"%")).all()
    else:
        flash('Invalid search type', 'error')
        results = None
    print "results: '", results, "'"
    return render_template('search_results.html',
                           query=query,
                           searchType=str(searchType),
                           results=results)

@app.route('/ajax/test', methods=['POST'])
def AJAX_test():
    return jsonify({'response':'success'})

@app.route('/ajax/delete', methods=['POST'])
@login_required
def deletePost():
    postID = int(request.form['postObjID'])
    post = Post.query.get(postID)
    db.session.delete(post)
    db.session.commit()    
    return jsonify({'response':'success'})

@app.route('/ajax/updatePost', methods=['POST'])
@login_required
def updatePost():
    app.logger.info('Updating post...')
    postId = int(request.form['postObjId'])
    post = Post.query.get(postId)
    post.body = request.form['postBody']
    post.postType = request.form['postType']
    db.session.add(post)
    db.session.commit()
    app.logger.info('Post updated.')
    return jsonify({'response':'success'})


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        saved_files_urls = []
        for key, f in request.files.iteritems():
            if f and allowed_file(f.filename):
                filename = secure_filename(f.filename)
                f.save(os.path.join(UPLOAD_IMG_DIR, filename))
                saved_files_urls.append(url_for('uploaded_file', filename=filename))
        return saved_files_urls[0]
        #return redirect(url_for('home'))
    return render_template('upload.html',
                           title = 'Upload')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_IMG_DIR, filename)

@lm.user_loader
def load_user(id):
    return User.query.get(int(id))


@oid.after_login
def after_oidlogin(resp):
    if resp.email is None or resp.email == "":
        flash('Invalid login. Please try again.', 'error')
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
        
@app.after_request
def after_request(response):
    if SQLALCHEMY_RECORD_QUERIES:
        for query in get_debug_queries():
            if query.duration >= DATABASE_QUERY_TIMEOUT:
                app.logger.warning("SLOW QUERY: %s\nParameters: %s\nDuration: %fs\nContext: %s\n" % (query.statement, query.parameters, query.duration, query.context))
    return response

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

