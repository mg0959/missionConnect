from flask import render_template
from flask.ext.mail import Message
from app import mail, app
from .decorators import async
from config import ADMINS


@async
def send_async_email(msg):
    with app.app_context():
        mail.send(msg)


def send_email(subject, sender, recipients, text_body, html_body):
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    send_async_email(msg)


def follower_notification(followed, follower):
    send_email("[MissionConnect] %s is now following you!" % follower.nickname,
               ADMINS[0],
               [followed.email],
               render_template("follower_email.txt",
                               user=followed, follower=follower),
               render_template("follower_email.html",
                               user=followed, follower=follower))

def signup_notification(user):
    send_email("[MissionConnect] Welcome to MissionConnect",
               ADMINS[0],
               [user.email],
               render_template("signup_email.txt", user=user),
               render_template("signup_email.html", user=user))
