from flask.ext.wtf import Form
from wtforms import TextField, BooleanField, TextAreaField, StringField, RadioField, FileField, HiddenField
from wtforms.validators import Length, DataRequired
from app.models import User, Photo, Group

IMAGE_EXT = ['jpg', 'tif', 'png']

class CreateGroupForm(Form):
    groupName = TextField('groupNameForm', validators=[DataRequired()])
    groupAbout = TextField('groupAboutForm', validators=[Length(min=0, max=140)])

class OpenidLoginForm(Form):
    openid = TextField('openid', validators = [DataRequired()])
    remember_me = BooleanField('remember_me', default = False)

class LoginForm(Form):
    email = TextField('email', validators=[DataRequired()])
    password = TextField('password', validators=[DataRequired()])
    remember_me = BooleanField('remember_me', default = False)

class SignupForm(Form):
    nickname = TextField('nickname', validators=[DataRequired()])
    email = TextField('email', validators=[DataRequired()])
    password = TextField('password', validators=[DataRequired()])
    password_confirm = TextField('password', validators=[DataRequired()])

class EditForm(Form):
    nickname = TextField('nickname', validators = [DataRequired()])
    about_me = TextAreaField('about_me', validators = [Length(min=0, max=140)])
    avatar_img = FileField('avatar_img')

    def __init__(self, original_nickname, *args, **kwargs):
        Form.__init__(self, *args, **kwargs)
        self.original_nickname = original_nickname

    def validate(self, avatar_img_file=None):
        print "Validating!"
        if not Form.validate(self):
            return False
        if self.nickname.data != self.original_nickname:
            user = User.query.filter_by(nickname = self.nickname.data).first()
            if user != None:
                self.nickname.errors.append('This nickname is already in use.  Please choose another one.')
                return False
        print "avatar_img.data", self.avatar_img.data
        if self.avatar_img.data and self.avatar_img.data.filename.split(".")[-1] not in IMAGE_EXT:
            if len(str(self.avatar_img.data.filename)) < 15:
                error_msg = 'The selected file "' + str(self.avatar_img.data.filename)  + '" is not an image.  Please choose another.'
            else: error_msg = 'The selected file "' + str(self.avatar_img.data.filename)[0:10]+' ... ' + str(self.avatar_img.data.filename)[-8:]  + '" is not an image.  Please choose another.'
            self.avatar_img.errors.append(error_msg)
            return False
##        if self.avatar_img.data and (not Photo.check_isImage(avatar_img_file)):
##            self.avatar_img.errors.append('The selected file is not an image.  Please choose another.')
##            return False
        
        return True

    def validate_on_submit(self, avatar_img_file=None):
        """
        Checks if form has been submitted and if so runs validate. This is
        a shortcut, equivalent to ``form.is_submitted() and form.validate()``
        """
        return self.is_submitted() and self.validate(avatar_img_file=avatar_img_file)
    

class PostForm(Form):
    post = TextAreaField('post', validators = [DataRequired()])
    postType = RadioField('postType', coerce=int, validators = [DataRequired()])
    
class SearchForm(Form):
    search = StringField('search', validators=[DataRequired()])
    searchType = HiddenField('searchType', default="Posts", validators = [DataRequired()])

class EditGroupForm(Form):
    name = TextField('name', validators = [DataRequired()])
    about = TextAreaField('about', validators = [Length(min=0, max=140)])
    avatar_img = FileField('avatar_img')

    def __init__(self, original_name, *args, **kwargs):
        Form.__init__(self, *args, **kwargs)
        self.original_name = original_name

    def validate(self, avatar_img_file=None):
        print "Validating!"
        if not Form.validate(self):
            return False
        if self.name.data != self.original_name:
            group = Group.query.filter_by(name = self.name.data).first()
            if group != None:
                self.name.errors.append('This group name is already in use.  Please choose another one.')
                return False
        if self.avatar_img.data and self.avatar_img.data.filename.split(".")[-1] not in IMAGE_EXT:
            if len(str(self.avatar_img.data.filename)) < 15:
                error_msg = 'The selected file "' + str(self.avatar_img.data.filename)  + '" is not an acceptable image type.  Please choose another.'
            else: error_msg = 'The selected file "' + str(self.avatar_img.data.filename)[0:10]+' ... ' + str(self.avatar_img.data.filename)[-8:]  + '" is not an acceptable image type.  Please choose another.'
            self.avatar_img.errors.append(error_msg)
            return False
##        if self.avatar_img.data and (not Photo.check_isImage(avatar_img_file)):
##            self.avatar_img.errors.append('The selected file is not an image.  Please choose another.')
##            return False
        
        return True

    def validate_on_submit(self, avatar_img_file=None):
        """
        Checks if form has been submitted and if so runs validate. This is
        a shortcut, equivalent to ``form.is_submitted() and form.validate()``
        """
        return self.is_submitted() and self.validate(avatar_img_file=avatar_img_file)

class InvitationGroupForm(Form):
    invite_field = TextAreaField('invite_field')
