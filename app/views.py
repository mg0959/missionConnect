from flask import render_template, flash, redirect, session, url_for, request, g, send_from_directory, jsonify
from flask.ext.login import login_user, logout_user, current_user, login_required
from datetime import datetime
from app import app, db, lm, oid
from forms import LoginForm, EditForm, PostForm, SearchForm, SignupForm, CreateGroupForm, EditGroupForm, InvitationGroupForm
from models import User, ROLE_USER, ROLE_ADMIN, Post, GENERAL_POST, PRAYER_POST, Photo, Group
from config import POSTS_PER_PAGE, MAX_SEARCH_RESULTS, DATABASE_QUERY_TIMEOUT, SQLALCHEMY_RECORD_QUERIES
from config import UPLOAD_IMG_DIR, ALLOWED_EXTENSIONS
from emails import follower_notification, signup_notification
from flask.ext.sqlalchemy import get_debug_queries
from werkzeug import secure_filename
import json
import os, base64


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
    posts = g.user.all_followed_posts().paginate(page, POSTS_PER_PAGE, False)
    prayerListPosts = g.user.get_prayerListEntries().limit(POSTS_PER_PAGE)
    
    return render_template('home.html', title = 'Home', posts = posts, page = 'home', theme=theme, prayerListPosts=prayerListPosts)

@app.route('/myprayerList')
@app.route('/myprayerList/<int:page>')
@login_required
def myPrayerList(page=1):
    prayerListPosts = g.user.get_prayerListEntries().paginate(page, POSTS_PER_PAGE, False)
    return render_template('my_prayer_table.html', prayerListPosts=prayerListPosts, user=user, page = 'user')

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
        db.session.add(u.follow_user(u))
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
@app.route('/user/<nickname>/posts/<int:page>', methods=['GET', 'POST'])
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
    prayerListPosts = user.get_prayers().limit(POSTS_PER_PAGE)
    return render_template('user.html',
                           user = user,
                           form=form,
                           posts = posts,
                           prayerListPosts = prayerListPosts,
                           page='user')

@app.route('/user/<nickname>/photos', methods=['GET', 'POST'])
@app.route('/user/<nickname>/photos/<int:page>', methods=['GET'])
@login_required
def userPhotos(nickname, page=1):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname + ' not found.', 'error')
        return redirect(url_for('home'))

    photos = user.photos.order_by(Photo.timestamp.desc()).paginate(page, POSTS_PER_PAGE, False)
    return render_template('userPhotos.html',
                           user = user,
                           photos=photos,
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
            f = request.files[form.avatar_img.name]
            pic = Photo(fname = "", timestamp = datetime.utcnow(), owner = g.user)
            db.session.add(pic)
            db.session.commit()
            #try:
            pic.fname = (str(pic.id)+"."+f.filename.split(".")[-1])
            f.save(os.path.join(UPLOAD_IMG_DIR, pic.fname))
            g.user.set_avatar(pic)
            db.session.add(pic)
            db.session.add(g.user)
            db.session.commit()
                
        flash('Your changes have been saved.', 'info')
        return redirect(url_for('user', nickname=g.user.nickname))
    else:
        form.nickname.data = g.user.nickname
        form.about_me.data = g.user.about_me
    return render_template('edit.html',
        form = form,
        user = g.user)

@app.route('/followUser/<nickname>')
@login_required
def followUser(nickname):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname + ' not found.', 'error')
        return redirect(url_for('home'))
    if user == g.user:
        flash('You can\'t follow yourself!', 'error')
        return redirect(url_for('user', nickname = nickname))
    u = g.user.follow_user(user)
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
def unfollowUser(nickname):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname + ' not found.', 'error')
        return redirect(url_for('home'))
    if user == g.user:
        flash('You can\'t unfollow yourself!', 'error')
        return redirect(url_for('user', nickname = nickname))
    u = g.user.unfollow_user(user)
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

@app.route('/user/<nickname>/prayerList')
@app.route('/user/<nickname>/prayerList/<int:page>')
@login_required
def userPrayerList(nickname, page=1):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User' + nickname + ' not found.', 'error')
        redirect(url_for('home'))
    prayerListPosts = user.get_prayers().paginate(page, POSTS_PER_PAGE, False)
    return render_template('user_prayer_table.html', prayerListPosts=prayerListPosts, user=user, page = 'user')

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
    profiles = gr.onlyFollowers().paginate(page, POSTS_PER_PAGE, False)
    return render_template('groupFollowers.html',
        group = gr,
        profiles = profiles)


@app.route('/manageGroup/<group_name>', methods=['GET'])
@login_required
def manageGroup(group_name):
    editGroupForm = EditGroupForm(group_name)
    invitationGroupForm = InvitationGroupForm()
    group = Group.query.filter_by(name=group_name).first()
    if not group:
        flash("'"+group_name+"' does not exist!", 'error')
        redirect(url_for('home'))
        
    if g.user != group.creator:
        flash("You are not authorized to manage the group '"+group_name+"'!", 'error')
        redirect(url_for('group', name=group_name))

    editGroupForm.name.data = group.name
    editGroupForm.about.data = group.about

    return render_template('manageGroup.html',
        editGroupForm = editGroupForm,
        invitationGroupForm = invitationGroupForm,
        group = group)


@app.route('/submitGroupEdits/<group_name>', methods=['POST'])
@login_required
def submitGroupEdits(group_name):
    editGroupForm = EditGroupForm(group_name)
    group = Group.query.filter_by(name=group_name).first()
    if not group:
        flash("'"+group_name+"' does not exist!", 'error')
        redirect(url_for('home'))

    if g.user != group.creator:
        flash("You are not authorized to manage the group '"+group_name+"'!", 'error')
        redirect(url_for('group', name=group_name))

    avatar_img_file = request.files[editGroupForm.avatar_img.name]

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

        flash('Your changes have been saved.', 'info')
        return redirect(url_for('group', group_name=group_name))
    else:
        return redirect(url_for('manageGroup', group_name=group_name))

@app.route('/submitGroupInvites/<group_name>', methods=['POST'])
@login_required
def submitGroupInvites(group_name):
    invitationGroupForm = InvitationGroupForm()
    group = Group.query.filter_by(name=group_name).first()
    if not group:
        flash("'"+group_name+"' does not exist!", 'error')
        redirect(url_for('home'))

    if g.user != group.creator:
        flash("You are not authorized to manage the group '"+group_name+"'!", 'error')
        redirect(url_for('group', name=group_name))

    invited_nicknames_str = invitationGroupForm.invite_field.data
    invited_names = invited_nicknames_str.split(",")
    for name in invited_names:
        name = name.strip()
        u = User.query.filter_by(nickname=name).first()
        if not u:
            flash("Unable to invite '"+name+"'; User does not exist", "error")
        elif group.is_invited(u):
            flash("'"+name+"' has already been invited to join "+group_name, "warning")
        else:
            u1 = group.invite_user(u)
            if u1:
                flash("'"+name+"' has been invited to join "+group_name, "info")
                db.session.add(u1)
                db.session.commit()
            else:
                flash("Unable to invite '"+name+"'", "error")
    return redirect(url_for('manageGroup', group_name=group_name))

@app.route('/acceptGroupInvite/<group_name>')
@login_required
def acceptGroupInvite(group_name):
    gr = Group.query.filter_by(name=group_name).first()
    if not gr:
        flash(group_name+" does not exist!", "error")
        return redirect(url_for('home'))

    if not gr.is_invited(g.user):
        flash("You have not been invited to join "+group_name+"!", "error")
        return redirect(url_for('group', group_name=group_name))

    u = g.user.join_group(gr)
    u = gr.uninvite_user(u)
    if not u:
        flash("Unable to join "+group_name+"!", "error")
        return redirect(url_for('group', group_name=group_name))

    db.session.add(u)
    db.session.add(gr)
    db.session.commit()
    flash("You have joined "+group_name+"!", "info")
    return redirect(url_for('group', group_name=group_name))

@app.route('/declineGroupInvite/<group_name>')
@login_required
def declineGroupInvite(group_name):
    gr = Group.query.filter_by(name=group_name).first()
    if not gr:
        flash(group_name+" does not exist!", "error")
        return redirect(url_for('home'))

    if not gr.is_invited(g.user):
        flash("You have not been invited to join "+group_name+"!", "error")
        return redirect(url_for('group', group_name=group_name))

    u = gr.uninvite_user(g.user)
    if not u:
        flash("Unable to decline invite to "+group_name+"!", "error")
        return redirect(url_for('group', group_name=group_name))

    db.session.add(u)
    db.session.add(gr)
    db.session.commit()
    flash("You have declined to join "+group_name+"!", "info")
    return redirect(url_for('group', group_name=group_name))

@app.route('/unjoinGroup/<group_name>')
@login_required
def unjoinGroup(group_name):
    gr = Group.query.filter_by(name=group_name).first()
    if not gr:
        flash(group_name+" does not exist!", "error")
        return redirect(url_for('home'))

    if not g.user.is_group_member(gr):
        flash("You are not a member of "+group_name+"!", "error")
        return redirect(url_for('group', group_name=group_name))

    u = g.user.unjoin_group(gr)
    if not u:
        flash("Unable to unjoin "+group_name+"!", "error")
        return redirect(url_for('group', group_name=group_name))

    db.session.add(u)
    db.session.add(gr)
    db.session.commit()
    flash("You have unjoined "+group_name+"!", "info")
    return redirect(url_for('group', group_name=group_name))

@app.route('/requestJoinGroup/<group_name>')
@login_required
def requestJoinGroup(group_name):
    gr = Group.query.filter_by(name=group_name).first()
    if not gr:
        flash('Cannot request to join; '+group_name+' does not exist!', 'error')
        return redirect(url_for('home'))

    if g.user.is_group_member(gr):
        flash('You are already a member of '+group_name+'!', "error")
        return redirect(url_for('group', group_name=group_name))

    if gr.is_invited(g.user):
        u = gr.uninvite_user(g.user)
        if not u:
            flash('You were previously invited... but something went wrong.', "error")
            return redirect(url_for('group', group_name=group_name))
        u = u.join_group(gr)
        if not u:
            flash('You were previously invited... but unable to join group.', "error")
            return redirect(url_for('group', group_name=group_name))

        db.session.add(u)
        db.session.add(gr)
        db.session.commit()
        flash('You were previously invited. Invitation accepted!', "success")
        return redirect(url_for('group', group_name=group_name))

    if g.user.has_requested_join(gr):
        flash('You have already requested to join '+group_name+'!', 'error')
        return redirect(url_for('group', group_name=group_name))

    u = g.user.request_join(gr)
    if not u:
        flash("Unable to request to join group.", "error")
        return redirect(url_for('group', group_name=group_name))
    db.session.add(u)
    db.session.add(gr)
    db.session.commit()
    flash("You have requested to join "+group_name+"!", "info")
    return redirect(url_for('group', group_name=group_name))


@app.route('/acceptGroupJoinRequest/<group_name>/<user_name>')
@login_required
def acceptGroupJoinRequest(group_name, user_name):
    gr = Group.query.filter_by(name=group_name).first()
    if not gr:
        flash("Unable to accept join request; the group "+group_name+" does not exist!", "error")
        return redirect(url_for('home'))

    u_requested = User.query.filter_by(nickname=user_name).first()
    if not u_requested:
        flash("Unable to accept join request; the user "+user_name+" does not exist!", "error")
        return redirect(url_for('group', group_name=group_name))

    if not u_requested.has_requested_join(gr):
        flash("Unable to accept join request; "+user_name+" has not requested to join the group!", "error")
        return redirect(url_for('group', group_name=group_name))

    if gr.creator != g.user:
        flash("You are not authorized to accept join requests for this group!", "error")
        return redirect(url_for('group', group_name=group_name))

    u1 = u_requested.join_group(gr)
    if not u1:
        flash('Unable to join '+u_requested.nickname+' to '+group_name+'!', "error")
        return redirect(url_for('group', group_name=group_name))
    if gr.is_invited(u1):
        u1 = gr.uninvite_user(u1)
        if not u1:
            flash('Unable to join '+u_requested.nickname+' to '+group_name+'! Group invite could not be cleared.', "error")
            return redirect(url_for('group', group_name=group_name))
    u2 = u1.remove_join_request(gr)
    if not u2:
        flash("Unable to remove join request", "error")
        return redirect(url_for('group', group_name=group_name))

    db.session.add(u2)
    db.session.add(gr)
    db.session.commit()
    flash(user_name+"'s join request has been accepted!", "info")
    return redirect(url_for('group', group_name=group_name))

@app.route('/declineGroupJoinRequest/<group_name>/<user_name>')
@login_required
def declineGroupJoinRequest(group_name, user_name):
    gr = Group.query.filter_by(name=group_name).first()
    if not gr:
        flash("Unable to decline join request; the group "+group_name+" does not exist!", "error")
        return redirect(url_for('home'))

    u_requested = User.query.filter_by(nickname=user_name).first()
    if not u_requested:
        flash("Unable to decline join request; the user "+user_name+" does not exist!", "error")
        return redirect(url_for('group', group_name=group_name))

    if not u_requested.has_requested_join(gr):
        flash("Unable to decline join request; "+user_name+" has not requested to join the group!", "error")
        return redirect(url_for('group', group_name=group_name))

    if gr.creator != g.user:
        flash("You are not authorized to decline join requests for this group!", "error")
        return redirect(url_for('group', group_name=group_name))

    u1 = u_requested.remove_join_request(gr)
    if not u1:
        flash("Unable to remove join request", "error")
        return redirect(url_for('group', group_name=group_name))

    db.session.add(u1)
    db.session.add(gr)
    db.session.commit()
    flash(user_name+"'s join request has been declined.", "info")
    return redirect(url_for('group', group_name=group_name))


@app.route('/createGroup', methods=['POST'])
@login_required
def createGroup():
    if not g.new_group_form.validate_on_submit():
        flash("Unable to create group", "error")
        return redirect(url_for('home'))

    gr_name = g.new_group_form.name.data.strip()
    if Group.query.filter_by(name=gr_name).first():
        flash("Ubable to create group. Choose another name. "+gr_name+" already exists", "error")
        return redirect(url_for('home'))

    gr = Group(name=gr_name, creator=g.user)
    db.session.add(gr)
    db.session.commit()
    flash("Group successfully created!", "info")
    return redirect(url_for('group', group_name=gr_name))

@app.route('/deleteGroup/<group_name>', methods=['GET'])
@login_required
def delete_group(group_name):
    gr = Group.query.filter_by(name=group_name).first()
    if not gr:
        flash("Unable to delete group. '"+group_name+"' does not exist!", "error")
        return redirect(url_for('home'))

    if g.user != gr.creator:
        flash("You are not authorized to delete this group!", "error")
        return redirect(url_for('group', group_name=group_name))


    db.session.delete(gr)
    db.session.commit()
    flash("Group successfully deleted.", "info")
    return redirect(url_for('home'))

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

@app.route('/unfollowGroup/<group_name>')
@login_required
def unfollowGroup(group_name):
    group = Group.query.filter_by(name = group_name).first()
    if group == None:
        flash("Group '" + group_name + "' not found.", 'error')
        return redirect(url_for('home'))

    u = g.user.unfollow_group(group)
    if u is None:
        flash('Cannot follow ' + group_name + '.', 'error')
        return redirect(url_for('group', group_name=group_name))
    db.session.add(u)
    db.session.commit()

    #follower_notification(group.creator, g.user)
    flash('You have stopped following ' + group_name + '.', 'info')
    return redirect(url_for('group', group_name = group_name))


@app.route('/explore')
@app.route('/explore/<int:page>')
@login_required
def explore(page = 1):
    #only unollowed posts
    posts = g.user.all_unfollowed_posts().paginate(page, POSTS_PER_PAGE, False)
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
        flash('Unable to complete search!', "error")
        return redirect(url_for('home'))
    return redirect(url_for('search_results', searchType=g.search_form.searchType.data, query=g.search_form.search.data))

@app.route('/search_results/<searchType>/<query>')
@login_required
def search_results(searchType, query):
    print "searchType", searchType
    if searchType=="Posts":
        results = g.user.all_followed_posts().whoosh_search(query, MAX_SEARCH_RESULTS).all()
        # Post.query.whoosh_search(query, MAX_SEARCH_RESULTS).all()
    elif searchType =="Users":
        results = User.query.filter(User.nickname.ilike("%"+str(query)+"%")).limit(MAX_SEARCH_RESULTS).all()
    elif searchType == "Groups":
        results = Group.query.filter(Group.name.ilike("%"+str(query)+"%")).limit(MAX_SEARCH_RESULTS).all()
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

@app.route('/ajax/addPrayingUser', methods=['POST'])
@login_required
def addPrayingUser():
    app.logger.info('Adding praying user...')
    postId = int(request.form['postObjId'])
    post = Post.query.get(postId)
    post.addPrayingUser(g.user)
    db.session.add(post)
    db.session.add(g.user)
    db.session.commit()
    app.logger.info(g.user.nickname+" added as a praying user to post #"+str(postId))
    return jsonify({'response':'success'})

@app.route('/ajax/removePrayingUser', methods=['POST'])
@login_required
def removePrayingUser():
    app.logger.info('Removing praying user...')
    postId = int(request.form['postObjId'])
    post = Post.query.get(postId)
    post.removePrayingUser(g.user)
    db.session.add(post)
    db.session.add(g.user)
    db.session.commit()
    app.logger.info(g.user.nickname+" removed as a praying user to post #"+str(postId))
    return jsonify({'response':'success'})



def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


@app.route('/upload_test', methods=['GET'])
@login_required
def upload_test():
    if request.method == 'POST':
        saved_files_urls = []
        for key, f in request.files.iteritems():
            if f and allowed_file(f.filename):
                filename = secure_filename(f.filename)
                f.save(os.path.join(UPLOAD_IMG_DIR, filename))
                saved_files_urls.append(url_for('uploaded_file', filename=filename))
        return saved_files_urls[0]
        #return redirect(url_for('home'))
    return render_template('upload-scratch.html',
                           title = 'Upload'
                           )

@app.route('/uploadImg', methods=['POST'])
@login_required
def uploadImg():
    imgBase64 = request.form['imgDataUrl']
    includePost = request.form['includePost']
    postId = request.form['postId']
    print "Include Post:", includePost
    print "PostId", postId
    img = base64.b64decode(imgBase64.split(",")[-1])

    if includePost == "true":
        print "including post..."
        pic = Photo(fname = "", timestamp = datetime.utcnow(), owner = g.user, post_id=(int(postId)))
    else:
        print "no post... only photo"
        pic = Photo(fname = "", timestamp = datetime.utcnow(), owner = g.user)
    db.session.add(pic)
    db.session.commit()
    pic.fname = (str(pic.id)+".png")
    db.session.add(pic)
    db.session.commit()
    with open(os.path.join(UPLOAD_IMG_DIR, pic.fname), "wb") as f:
        f.write(img)
    return jsonify({'response':'success'})

@app.route('/getImgPost')
@login_required
def getImgPost():
    p = Post(body = "", timestamp = datetime.utcnow(), author = g.user)
    db.session.add(p)
    db.session.commit()
    print "postId:", p.id
    return jsonify({'post_id':p.id})

@app.route('/upload', methods=['POST'])
def upload():
    results = []
    for key, f in request.files.iteritems():
        print "key, f", key, f
        if f and allowed_file(f.filename):
            result = {}
            filename = secure_filename(f.filename)
            f.save(os.path.join(UPLOAD_IMG_DIR, filename))
            find_url = url_for('uploaded_file', filename=filename)
            result['name']=filename
            result['url']=find_url

            results.append(result)
            print 'result', result
    print results
    return jsonify({'files': results})

@app.route('/json_test')
def json_test():
    results = []
    r1 = {}
    r1['name']="bill"
    r1['url']="a_place.com"
    r2 = {}
    r2['name']="Lar"
    results.append(r1)
    results.append(r2)
    return jsonify({'files':results})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_IMG_DIR, filename)

@lm.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.before_request
def before_request():
    g.user = current_user
    if g.user.is_authenticated():
        g.user.last_seen = datetime.utcnow()
        db.session.add(g.user)
        db.session.commit()
        g.search_form = SearchForm()
        g.new_group_form= EditGroupForm(None)
        g.notifications = g.user.get_notifications()
        
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

