from flask import Flask, redirect, url_for, session, request, jsonify, Markup, flash, render_template
from flask_oauthlib.client import OAuth
from flask_socketio import SocketIO, emit, join_room, leave_room, \
    close_room, rooms, disconnect
from threading import Lock

import pymongo
import pprint
import os
import json

os.system("echo '[]'>" + 'forum.json')

# '''TAKE THIS OUT BEFORE RUNNING ON HEROKU'''
# os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
socketio = SocketIO(app, async_mode=None)
thread = None
thread_lock = Lock()

app.debug = True #Change this to False for production

app.secret_key = os.environ['SECRET_KEY'] #used to sign session cookies
oauth = OAuth(app)

url = 'mongodb://{}:{}@{}:{}/{}'.format(
    os.environ["MONGO_USERNAME"],
    os.environ["MONGO_PASSWORD"],
    os.environ["MONGO_HOST"],
    os.environ["MONGO_PORT"],
    os.environ["MONGO_DBNAME"])

client = pymongo.MongoClient(url)
db = client[os.environ["MONGO_DBNAME"]]
collection = db["posts"]

#Set up GitHub as OAuth provider
github = oauth.remote_app(
    'github',
    consumer_key=os.environ['GITHUB_CLIENT_ID'], #your web app's "username" for github's OAuth
    consumer_secret=os.environ['GITHUB_CLIENT_SECRET'],#your dfweb app's "password" for github's OAuth
    request_token_params={'scope': 'user:email'}, #request read-only access to the user's email.  For a list of possible scopes, see developer.github.com/apps/building-oauth-apps/scopes-for-oauth-apps
    base_url='https://api.github.com/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://github.com/login/oauth/access_token',
    authorize_url='https://github.com/login/oauth/authorize' #URL for github's OAuth login
)

#use a JSON file to store the past posts.  A global list variable doesn't work when handling multiple requests coming in and being handled on different threads
#Create and set a global variable for the name of you JSON file here.  The file will be created on Heroku, so you don't need to make it in GitHub


@app.context_processor
def inject_logged_in():
    return {"logged_in":('github_token' in session)}
    # return {"logged_in": True}

@app.route('/')
def home():
    return render_template('home.html', past_posts=posts_to_html("SB"))

def posts_to_html(hometownval):
    print(hometownval)
    forum_table = Markup("<table class='table table-bordered'> <tr> <th> Username </th> <th> Message </th> </tr>")
    for post in collection.find({"location": hometownval}):
        try:
            forum_table += Markup("<tr> <td>" + post["username"] + "</td> <td>" + post["message"] + "</td> </tr>")
        except Exception as e:
            print(e)
    forum_table += Markup("</table>")
    return forum_table

#Use this method to delete messages
# @app.route('/delete', methods=['POST'])
# def delete():
#     print("In delete method" + request.form["delete"])
#
#     docid = request.form["delete"]
#
#     collection.delete_one({'_id': ObjectId(docid)})
#
#     return render_template('home.html', past_posts = posts_to_html())


@app.route('/posted', methods=['POST'])
def post():
    print("posted")
    username_local = session['user_data']['login']
    message_local = request.form['message']
    user_location = "SB"
    try:
        collection.insert( { "username": username_local, "message": message_local, "location": user_location } )
    except Exception as e:
        print("Unable to post :(")
        print(e)

    return render_template('home.html', past_posts = posts_to_html("SB"))


#redirect to GitHub's OAuth page and confirm callback URL
@app.route('/login')
def login():
    print("login")
    return github.authorize(callback=url_for('authorized', _external=True, _scheme='https')) #callback URL must match the pre-configured callback URL

@app.route('/logout')
def logout():
    print("---------logout")
    session.clear()
    return render_template('message.html', message='You were logged out')

@app.route('/login/authorized')
def authorized():
    print("login authorized")
    resp = github.authorized_response()
    if resp is None:
        session.clear()
        message = 'Access denied: reason=' + request.args['error'] + ' error=' + request.args['error_description'] + ' full=' + pprint.pformat(request.args)
    else:
        try:
            session['github_token'] = (resp['access_token'], '') #save the token to prove that the user logged in
            session['user_data']=github.get('user').data
            flash('You were successfully logged in as ' + session['user_data']['login'])
            flash('logged in')
            # message='You were successfully logged in as ' + session['user_data']['login']
        except Exception as inst:
            session.clear()
            print(inst)
            flash('unable to login')
            # message='Unable to login, please try again.  '

    return render_template('home.html') #, past_posts = posts_to_html(get_user_location()))

#the tokengetter is automatically called to check who is logged in.
@github.tokengetter
def get_github_oauth_token():
    return session.get('github_token')

def get_user_location():
    return session['user_data']['location']


if __name__ == '__main__':
    app.run()
