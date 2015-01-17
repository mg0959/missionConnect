#!flask/bin/python
import os
import unittest
from coverage import coverage
cov = coverage(branch=True, omit=['flask/*', 'tests.py'])
cov.start()

from config import basedir
from app import app, db
from app.models import User, Post, Group
from datetime import datetime, timedelta

class TestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'test.db')
        self.app = app.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_user(self):
        # make valid nicknames
        n = User.make_valid_nickname('John_123')
        assert n == 'John_123'
        n = User.make_valid_nickname('John_[123]\n')
        assert n == 'John_123'
        # create a user
        u = User(nickname='john', email='john@example.com')
        db.session.add(u)
        db.session.commit()
        assert u.is_authenticated() is True
        assert u.is_active() is True
        assert u.is_anonymous() is False
        assert u.id == int(u.get_id())

    def test_make_unique_nickname(self):
        # create a user and write it to the database
        u = User(nickname='john', email='john@example.com')
        db.session.add(u)
        db.session.commit()
        nickname = User.make_unique_nickname('susan')
        assert nickname == 'susan'
        nickname = User.make_unique_nickname('john')
        assert nickname != 'john'

##    def test_avatar(self):
##        u = User(nickname = 'john', email = 'john@example.com')
##        avatar = u.avatar(128)
##        expected = 'http://www.gravatar.com/avatar/d4c74594d841139328695756648b6bd6'
##        assert avatar[0:len(expected)] == expected

    def test_make_unique_nickname(self):
        u = User(nickname = 'john', email = 'john@example.com')
        db.session.add(u)
        db.session.commit()
        nickname = User.make_unique_nickname('john')
        assert nickname != 'john'
        u = User(nickname = nickname, email = 'susan@example.com')
        db.session.add(u)
        db.session.commit()
        nickname2 = User.make_unique_nickname('john')
        assert nickname2 != 'john'
        assert nickname2 != nickname

    def test_follow(self):
        u1 = User(nickname = 'john', email = 'john@example.com')
        u2 = User(nickname = 'susan', email = 'susan@example.com')
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()
        assert u1.unfollow(u2) == None
        u = u1.follow(u2)
        db.session.add(u)
        db.session.commit()
        assert u1.follow(u2) == None
        assert u1.is_following(u2)
        assert u1.followed.count() == 1
        assert u1.followed.first().nickname == 'susan'
        assert u2.followers.count() == 1
        assert u2.followers.first().nickname == 'john'
        u = u1.unfollow(u2)
        assert u != None
        db.session.add(u)
        db.session.commit()
        assert u1.is_following(u2) == False
        assert u1.followed.count() == 0
        assert u2.followers.count() == 0

    def test_delete_post(self):
        # create a user and a post
        u = User(nickname='john', email='john@example.com')
        p = Post(body='test post', author=u, timestamp=datetime.utcnow())
        db.session.add(u)
        db.session.add(p)
        db.session.commit()
        # query the post and destroy the session
        p = Post.query.get(1)
        db.session.remove()
        # delete the post using a new session
        db.session = db.create_scoped_session()
        db.session.delete(p)
        db.session.commit()

    def test_follow_posts(self):
        # make four users
        u1 = User(nickname='john', email='john@example.com')
        u2 = User(nickname='susan', email='susan@example.com')
        u3 = User(nickname='mary', email='mary@example.com')
        u4 = User(nickname='david', email='david@example.com')
        db.session.add(u1)
        db.session.add(u2)
        db.session.add(u3)
        db.session.add(u4)
        # make four posts
        utcnow = datetime.utcnow()
        p1 = Post(body="post from john", author=u1, timestamp=utcnow + timedelta(seconds=1))
        p2 = Post(body="post from susan", author=u2, timestamp=utcnow + timedelta(seconds=2))
        p3 = Post(body="post from mary", author=u3, timestamp=utcnow + timedelta(seconds=3))
        p4 = Post(body="post from david", author=u4, timestamp=utcnow + timedelta(seconds=4))
        db.session.add(p1)
        db.session.add(p2)
        db.session.add(p3)
        db.session.add(p4)
        db.session.commit()
        # setup the followers
        u1.follow(u1)  # john follows himself
        u1.follow(u2)  # john follows susan
        u1.follow(u4)  # john follows david
        u2.follow(u2)  # susan follows herself
        u2.follow(u3)  # susan follows mary
        u3.follow(u3)  # mary follows herself
        u3.follow(u4)  # mary follows david
        u4.follow(u4)  # david follows himself
        db.session.add(u1)
        db.session.add(u2)
        db.session.add(u3)
        db.session.add(u4)
        db.session.commit()
        # check the followed posts of each user
        f1 = u1.followed_posts().all()
        f2 = u2.followed_posts().all()
        f3 = u3.followed_posts().all()
        f4 = u4.followed_posts().all()
        assert len(f1) == 3
        assert len(f2) == 2
        assert len(f3) == 2
        assert len(f4) == 1
        assert f1 == [p4, p2, p1]
        assert f2 == [p3, p2]
        assert f3 == [p4, p3]
        assert f4 == [p4]

    def test_unfollowed_posts(self):
        # make four users
        u1 = User(nickname='john', email='john@example.com')
        u2 = User(nickname='susan', email='susan@example.com')
        u3 = User(nickname='mary', email='mary@example.com')
        u4 = User(nickname='david', email='david@example.com')
        db.session.add(u1)
        db.session.add(u2)
        db.session.add(u3)
        db.session.add(u4)
        # make four posts
        utcnow = datetime.utcnow()
        p1 = Post(body="post from john", author=u1, timestamp=utcnow + timedelta(seconds=1))
        p2 = Post(body="post from susan", author=u2, timestamp=utcnow + timedelta(seconds=2))
        p3 = Post(body="post from mary", author=u3, timestamp=utcnow + timedelta(seconds=3))
        p4 = Post(body="post from david", author=u4, timestamp=utcnow + timedelta(seconds=4))
        db.session.add(p1)
        db.session.add(p2)
        db.session.add(p3)
        db.session.add(p4)
        db.session.commit()
        # setup the followers
        u1.follow(u1)  # john follows himself
        u1.follow(u2)  # john follows susan
        u1.follow(u4)  # john follows david
        u2.follow(u2)  # susan follows herself
        u2.follow(u3)  # susan follows mary
        u3.follow(u3)  # mary follows herself
        u3.follow(u4)  # mary follows david
        u4.follow(u4)  # david follows himself
        db.session.add(u1)
        db.session.add(u2)
        db.session.add(u3)
        db.session.add(u4)
        db.session.commit()
        # check the followed posts of each user
        f1 = u1.unfollowed_posts().all()
        f2 = u2.unfollowed_posts().all()
        f3 = u3.unfollowed_posts().all()
        f4 = u4.unfollowed_posts().all()
        
        assert len(f1) == 1
        assert len(f2) == 2
        assert len(f3) == 2
        assert len(f4) == 3
        assert f1 == [p3]
        assert f2 == [p4, p1]
        assert f3 == [p2, p1]
        assert f4 == [p3, p2, p1]

    def test_group(self):
        # make 4 users
        u1 = User(nickname='john', email='john@example.com')
        u2 = User(nickname='susan', email='susan@example.com')
        u3 = User(nickname='mary', email='mary@example.com')
        u4 = User(nickname='david', email='david@example.com')
        db.session.add(u1)
        db.session.add(u2)
        db.session.add(u3)
        db.session.add(u4)
        db.session.commit()

        # create 3 groups        
        g1 = Group(name='group1', about='test group 1', creator=u1)
        g2 = Group(name='group2', about='test group 2', creator=u3)
        g3 = Group(name='group3', about='test group 3', creator=u1)
        db.session.add(g1)
        db.session.add(g2)
        db.session.add(g3)
        db.session.commit()

        # make 4 posts
        utcnow = datetime.utcnow()
        p1 = Post(body="post from john", author=u1, timestamp=utcnow + timedelta(seconds=1), group = g1)
        p2 = Post(body="post from susan", author=u2, timestamp=utcnow + timedelta(seconds=2), group = g1)
        p3 = Post(body="post from mary", author=u3, timestamp=utcnow + timedelta(seconds=3), group = g2)
        p4 = Post(body="post from david", author=u4, timestamp=utcnow + timedelta(seconds=4))
        db.session.add(p1)
        db.session.add(p2)
        db.session.add(p3)
        db.session.add(p4)
        db.session.commit()

        #check group creation
        u1_groups = u1.groups.all()
        u2_groups = u2.groups.all()
        u3_groups = u3.groups.all()
        u4_groups = u4.groups.all()

        assert len(u1_groups) == 2
        assert len(u2_groups) == 0
        assert len(u3_groups) == 1
        assert len(u4_groups) == 0
        assert u1_groups == [g1, g3]
        assert u3_groups == [g2]

        # check post group assosciation
        g1_posts = g1.posts.all()
        g2_posts = g2.posts.all()
        g3_posts = g3.posts.all()
        independentPosts = Post.query.filter(Post.group == None).all()


        assert len(g1_posts) == 2
        assert len(g2_posts) == 1
        assert len(g3_posts) == 0
        assert len(independentPosts) == 1
        assert g1_posts == [p1, p2]
        assert g2_posts == [p3]
        assert g3_posts == []
        assert independentPosts == [p4]

        # add meberships and follow groups
        u1.join_group(g1)
        u1.join_group(g2)
        u1.join_group(g3)
        u2.join_group(g1)
        u2.join_group(g2)
        u3.join_group(g1)

        u4.follow_group(g1)
        u4.follow_group(g2)
        u4.follow_group(g3)
        u3.follow_group(g2)
        u3.follow_group(g1)
        u2.follow_group(g2)
        u1.follow_group(g3)

        db.session.add(u1)
        db.session.add(u2)
        db.session.add(u3)
        db.session.add(u4)
        db.session.commit()

        # check memberships
        u1_memberships = u1.groupMemberships.all()
        u2_memberships = u2.groupMemberships.all()
        u3_memberships = u3.groupMemberships.all()
        u4_memberships = u4.groupMemberships.all()

        assert len(u1_memberships) == 3
        assert len(u2_memberships) == 2
        assert len(u3_memberships) == 1
        assert len(u4_memberships) == 0
        assert u1_memberships == [g1, g2, g3]
        assert u2_memberships == [g1, g2]
        assert u3_memberships == [g1]
        assert u4_memberships == []

        #check following
        u1_following = u1.followedGroups.all()
        u2_following = u2.followedGroups.all()
        u3_following = u3.followedGroups.all()
        u4_following = u4.followedGroups.all()

        assert len(u1_following) == 1
        assert len(u2_following) == 1
        assert len(u3_following) == 2
        assert len(u4_following) == 3
        assert u1_following == [g3]
        assert u2_following == [g2]
        assert u3_following == [g2, g1]
        assert u4_following == [g1, g2, g3]
        
        

        # remove membership and following
        u1.unjoin_group(g2)
        u2.unfollow_group(g2)
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()

        u1_memberships = u1.groupMemberships.all()
        u2_following = u2.followedGroups.all()
        
        assert len(u1_memberships) == 2
        assert u1_memberships == [g1, g3]
        assert len(u2_following) == 0
        assert u2_following == []     
        
    def test_password(self):
        u1 = User(nickname = 'john', email = 'john@example.com', password=User.hash_password('secret'))
        db.session.add(u1)
        db.session.commit()
        assert u1.password != User.hash_password('secret')
        assert u1.check_password('secret') == True
        assert u1.check_password('easyPassword') == False
        
        u1.set_password('new_password_SoLongWithStrangeChars!2#$@:')
        assert u1.password != User.hash_password('new_password_SoLongWithStrangeChars!2#$@:')
        assert u1.check_password('new_password_SoLongWithStrangeChars!2#$@:') == True
        assert u1.check_password('secret') == False 

if __name__ == '__main__':
    try:
        unittest.main()
    except:
        pass
    cov.stop()
    cov.save()
    print "\n\nCoverage Report:\n"
    cov.report()
    print "HTML version: " + os.path.join(basedir, "tmp/coverage/index.html")
    cov.html_report(directory='tmp/coverage')
    cov.erase()
