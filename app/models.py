from app import db, app
from hashlib import md5
import uuid
import hashlib
import re
from flask import url_for
from PIL import Image
import os, glob, copy
from config import UPLOAD_IMG_DIR, basedir

import sys
if sys.version_info >= (3, 0): # pragma: no cover
    enable_search = False
else:
    enable_search = True
    import flask.ext.whooshalchemy as whooshalchemy

ROLE_USER = 0
ROLE_ADMIN = 1
ROLE_MISSIONARY = 2

followers = db.Table('followers',
                    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
                    db.Column('followed_id', db.Integer, db.ForeignKey('user.id')))

groupFollowers = db.Table('groupFollowers',
                    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
                    db.Column('group_id', db.Integer, db.ForeignKey('group.id')))

members = db.Table('members',
                    db.Column('member_id', db.Integer, db.ForeignKey('user.id')),
                    db.Column('group_id', db.Integer, db.ForeignKey('group.id')))

postGroup = db.Table('postGroup',
                     db.Column('post_id', db.Integer, db.ForeignKey('post.id')),
                     db.Column('group_id', db.Integer, db.ForeignKey('group.id')))

invitations = db.Table('invitations',
                       db.Column('invited_id', db.Integer, db.ForeignKey('user.id')),
                       db.Column('group_id', db.Integer, db.ForeignKey('group.id')))

            

class Group(db.Model):    
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(64), index = True, unique = True)
    about = db.Column(db.String(140))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    posts = db.relationship('Post', backref = 'group', lazy = 'dynamic')
    avatar_photo = db.Column(db.Integer)

    def __init__(self, *args, **kwargs):
        db.Model.__init__(self, *args, **kwargs)
        self.creator.join_group(self)

    def set_avatar(self, photo):
        self.avatar_photo = photo.id

    def avatar(self, size):
        if self.avatar_photo:
            db_image = Photo.query.get(self.avatar_photo)
            thumb_path = os.path.join(UPLOAD_IMG_DIR, db_image.fname.split(".")[0]+ "_thumb_"+str(size)+".jpg")
            if not os.path.isfile(thumb_path):
                db_image.make_thumb(size)
            return url_for('.static', filename='img/userImages/'+db_image.fname.split(".")[0]+ "_thumb_"+str(size)+".jpg")
        else:
            return  url_for('.static', filename='img/default_profile.jpg')

    def onlyFollowers(self):
        memAlias = db.aliased(User, self.members.subquery())
        return self.followers.outerjoin(memAlias, User.id==memAlias.id).filter(memAlias.id == None).order_by(User.nickname.asc())

    ############################
    # invite/uninvite users
    ############################
    def invite_user(self, user):
        if not self.is_invited(user):
            self.invited.append(user)
            return self

    def unfollow_user(self, user):
        if self.is_invited(user):
            self.invited.remove(user)
            return self

    def is_invited(self, user):
        return self.invited.filter(invitations.c.invited_id == user.id).count()>0

    ############################

    def __repr__(self): # pragma: no cover
        return '<Group %r>' % (self.name)
    
    @staticmethod
    def make_valid_name(name):
        return re.sub('[^a-zA-Z0-9_\.]', '', name)

class User(db.Model):
    #__searchable__ = ['nickname']
    
    id = db.Column(db.Integer, primary_key = True)
    nickname = db.Column(db.String(64), index = True, unique = True)
    email = db.Column(db.String(120), index = True, unique = True)
    password = db.Column(db.String(89))
    role = db.Column(db.SmallInteger, default = ROLE_USER)
    about_me = db.Column(db.String(140))
    last_seen = db.Column(db.DateTime)
    
    posts = db.relationship('Post', backref = 'author', lazy = 'dynamic')
    photos = db.relationship('Photo', backref = 'owner', lazy = 'dynamic')
    avatar_photo = db.Column(db.Integer)
    groups = db.relationship('Group', backref = 'creator', lazy = 'dynamic')
    followed = db.relationship('User',
                               secondary = followers,
                               primaryjoin = (followers.c.follower_id == id),
                               secondaryjoin = (followers.c.followed_id == id),
                               backref = db.backref('followers', lazy = 'dynamic'),
                               lazy = 'dynamic')
    groupMemberships = db.relationship('Group',
                                       secondary = members,
                                       primaryjoin = (members.c.member_id == id),
                                       secondaryjoin = (members.c.group_id == Group.id),
                                       backref = db.backref('members', lazy = 'dynamic'),
                                       lazy = 'dynamic')
    followedGroups = db.relationship('Group',
                                     secondary = groupFollowers,
                                     primaryjoin = (groupFollowers.c.follower_id == id),
                                     secondaryjoin = (groupFollowers.c.group_id == Group.id),
                                     backref = db.backref('followers', lazy='dynamic'),
                                     lazy='dynamic')
    groupInvitations = db.relationship('Group',
                               secondary = invitations,
                               primaryjoin = (invitations.c.invited_id == id),
                               secondaryjoin = (invitations.c.group_id == Group.id),
                               backref = db.backref('invited', lazy = 'dynamic'),
                               lazy = 'dynamic')

    # basic User property functions
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.id)

    ############################
    # follow/unfollow users
    ############################
    
    def follow_user(self, user):
        if not self.is_following(user):
            self.followed.append(user)
            return self

    def unfollow_user(self, user):
        if self.is_following(user):
            self.followed.remove(user)
            return self

    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count()>0

    ############################
    # join/unjoin groups
    ############################

    def join_group(self, group):
        if not self.is_group_member(group):
            self.groupMemberships.append(group)
            self.follow_group(group)
            return self

    def unjoin_group(self, group):
        if self.is_group_member(group):
            self.groupMemberships.remove(group)
            self.unfollow_group(group)
            return self

    def is_group_member(self, group):
        return self.groupMemberships.filter(members.c.group_id==group.id).count()>0

    ############################
    # follow/unfollow groups
    ############################

    def follow_group(self, group):
        if not self.is_group_follower(group):
            self.followedGroups.append(group)
            return self

    def unfollow_group(self, group):
        if self.is_group_follower(group):
            self.followedGroups.remove(group)
            return self

    def is_group_follower(self, group):
        return self.followedGroups.filter(groupFollowers.c.group_id==group.id).count()>0

    ############################
    # get Posts
    ############################
    
    def followed_user_posts(self):
        return Post.query.join(followers, followers.c.followed_id == Post.user_id).filter(followers.c.follower_id == self.id).order_by(Post.timestamp.desc())

    def unfollowed_user_posts(self):
        postAlias = db.aliased(Post, self.followed_user_posts().subquery())
        return Post.query.outerjoin(postAlias, Post.user_id==postAlias.user_id).filter(postAlias.id == None).order_by(Post.timestamp.desc())

    def followed_group_posts(self):
        return Post.query.join(groupFollowers, groupFollowers.c.group_id == Post.group_id).filter(groupFollowers.c.follower_id == self.id).order_by(Post.timestamp.desc())

    def unfollowed_group_posts(self):
        fgpAlias = db.aliased(Post, self.followed_group_posts().subquery())
        return Post.query.outerjoin(fgpAlias, Post.group_id==fgpAlias.group_id).filter(fgpAlias.id == None).order_by(Post.timestamp.desc())

    def all_followed_posts(self):
        # followed user posts alias
        fupAlias = db.aliased(Post, self.followed_user_posts().subquery())
        fgpAlias = db.aliased(Post, self.followed_group_posts().subquery())
        return Post.query.outerjoin(fupAlias, Post.id == fupAlias.id).outerjoin(fgpAlias, Post.id == fgpAlias.id).filter(db.or_(fupAlias.id != None, fgpAlias.id != None)).order_by(Post.timestamp.desc())

    def all_unfollowed_posts(self):
        # followed user posts alias
        afpAlias = db.aliased(Post, self.all_followed_posts().subquery())
        return Post.query.outerjoin(afpAlias, Post.id==afpAlias.id).filter(afpAlias.id == None).order_by(Post.timestamp.desc())

    ############################
    # User Profile Settings
    ############################
        
    def avatar(self, size):
        if self.avatar_photo:
            db_image = Photo.query.get(self.avatar_photo)
            thumb_path = os.path.join(UPLOAD_IMG_DIR, db_image.fname.split(".")[0]+ "_thumb_"+str(size)+".jpg")
            if not os.path.isfile(thumb_path):
                db_image.make_thumb(size)
            return url_for('.static', filename='img/userImages/'+db_image.fname.split(".")[0]+ "_thumb_"+str(size)+".jpg")
        else:
            return  url_for('.static', filename='img/default_profile.jpg')
        '''
        db_image = self.photos.filter(Photo.isAvatar == True).first()
        if db_image:
            thumb_path = os.path.join(UPLOAD_IMG_DIR, db_image.fname.split(".")[0]+ "_thumb_"+str(size)+".jpg")
            if not os.path.isfile(thumb_path):
                db_image.make_thumb(size)
            return url_for('.static', filename='img/userImages/'+db_image.fname.split(".")[0]+ "_thumb_"+str(size)+".jpg")
        else:
            return  'http://www.gravatar.com/avatar/'+md5(self.email).hexdigest() +'?d=mm&s='+str(size)
        '''

    def set_avatar(self, photo):
        self.avatar_photo = photo.id

    def set_password(self, password):
        self.password = User.hash_password(password)

    def check_password(self, user_password):
        password, salt = self.password.split(':')
        return password == hashlib.sha224(salt.encode() + user_password.encode()).hexdigest()
 
    def __repr__(self): # pragma: no cover
        return '<User %r>' % (self.nickname)

    @staticmethod
    def make_valid_nickname(nickname):
        return re.sub('[^a-zA-Z0-9_\.]', '', nickname)
    
    @staticmethod
    def make_unique_nickname(nickname):
        if User.query.filter_by(nickname=nickname).first() == None:
            return nickname
        version = 2
        while True:
            new_nickname = nickname + str(version)
            if User.query.filter_by(nickname=new_nickname).first() == None:
                break
            version += 1
        return new_nickname

    @staticmethod
    def hash_password(password):
        # uuid is used to generate a random number
        salt = uuid.uuid4().hex
        return hashlib.sha224(salt.encode() + password.encode()).hexdigest() + ':' + salt
   

#Post types
GENERAL_POST = 1
ENCOURAGEMENT = 2
PRAYER_POST = 3
BLOG_POST = 4

class Post(db.Model):
    __searchable__ = ['body']

    
    id = db.Column(db.Integer, primary_key = True)
    body = db.Column(db.String(140))
    timestamp = db.Column(db.DateTime)
    postType = db.Column(db.SmallInteger, default = GENERAL_POST)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))

    def __repr__(self): # pragma: no cover
        return '<Post %r>' % (self.body)

    @staticmethod
    def getPrayer():
        return Post.query.filter(Post.postType == PRAYER_POST)

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    fname = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime)
    caption =db.Column(db.String(140), default = "")
    isAvatar = db.Column(db.Boolean, default = False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def make_thumb(self, size):
        fpath = os.path.join(UPLOAD_IMG_DIR, self.fname)
        im = Image.open(fpath)
        im.thumbnail((size, size), Image.ANTIALIAS)
        im.save(fpath.split(".")[0]+ "_thumb_"+str(size)+".jpg", "JPEG")

    def delete_files(self):
        fpath = os.path.join(UPLOAD_IMG_DIR, self.fname.split(".")[0])
        for f in glob.glob((fpath+"*")):
            os.remove(f)      
        
    def __repr__(self): # pragma: no cover
        return '<Photo %r>' % (self.fname)


if enable_search:
    whooshalchemy.whoosh_index(app, Post)
    #whooshalchemy.whoosh_index(app, User)


