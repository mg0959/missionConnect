import os
basedir = os.path.abspath(os.path.dirname(__file__))

SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')+'?check_same_thread=False'
SQLALCHEMY_MIGRATE_REPO = os.path.join(basedir, 'db_repository')

CSRF_ENABLED = True
SECRET_KEY = 'hard_to_crack_key'

OPENID_PROVIDERS = [
    { 'name': 'Google', 'url': 'https://accounts.google.com/o/oauth2/auth' },
    { 'name': 'Yahoo', 'url': 'https://me.yahoo.com' },
    { 'name': 'AOL', 'url': 'http://openid.aol.com/<username>' },
    { 'name': 'Flickr', 'url': 'http://www.flickr.com/<username>' },
    { 'name': 'MyOpenID', 'url': 'https://www.myopenid.com' }]

#old google openid: https://www.google.com/accounts/o8/id

# email server
MAIL_SERVER = 'smtp.googlemail.com'
MAIL_PORT = 465
MAIL_USE_TLS = False
MAIL_USE_SSL = True
MAIL_USERNAME = os.environ.get('MAIL_USERNAME') #no.reply.missionconnect@gmail.com
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') #mc2014mc

# administrator list
ADMINS = ['mg0959@gmail.com']


# pagination
POSTS_PER_PAGE = 3

# full text search database
WHOOSH_BASE = os.path.join(basedir, 'search.db')
MAX_SEARCH_RESULTS = 50
