import dateutil.parser
import flask
import functools
import logging
import re
import urllib

import youtube
from models import *

app = flask.Flask(__name__)
app.secret_key = 'tAPi7MV9bnhqQyv-k1nfoQ' # TODO: Config this

@app.before_request
def set_user():
    flask.g.user = User.get_or_none(email = flask.session.get('email'))

@app.template_filter('urlencode')
def urlencode(s):
    return urllib.parse.quote_plus(s)

def require_user(f):
    @functools.wraps(require_user)
    def wrapped(*args, **kwargs):
        if flask.g.user:
            return f(*args, **kwargs)
        else:
            flask.session['return_to'] = flask.request.full_path
            flask.flash('You must be logged in to access that content')
            return flask.redirect('/')

    wrapped.__name__ = f.__name__
    return wrapped

@app.route('/')
def home():
    if flask.g.user:
        return flask.render_template('home.html')
    else:
        return flask.render_template('login.html')

@app.route('/profile', methods = ['GET', 'POST'])
@require_user
def profile():
    user = User.get(email = flask.session.get('email'))

    if flask.request.method == 'GET':
        return flask.render_template('profile.html', user = user)

    elif flask.request.method == 'POST' and 'confirm-new-password' in flask.request.form:
        if not user.password.check_password(flask.request.form.get('old-password')):
            flask.flash('Incorrect password')

        elif not flask.request.form.get('new-password') == flask.request.form.get('confirm-new-password'):
            flask.flash('Passwords do not match')

        else:
            user.password = flask.request.form.get('new-password')
            user.save()
            flask.flash('Password changed')

        return flask.redirect('/profile')

    # Importing an opml file
    elif flask.request.method == 'POST' and 'opml' in flask.request.files:
        file = flask.request.files['opml']

        user = User.get(email = flask.session.get('email'))
        for youtube_id in re.findall(r'xmlUrl="https://www.youtube.com/feeds/videos.xml\?channel_id=(.*?)"', file.read().decode()):
            feed = Feed.get_or_create(youtube_id = youtube_id)[0]
            Subscription.get_or_create(user = user, feed = feed)
        
        return flask.redirect('/subscriptions')

@app.route('/subscriptions', methods = ['GET', 'POST'])
@require_user
def get_subscriptions():
    if flask.request.method == 'GET':
        return flask.render_template('subscriptions.html', subscriptions = flask.g.user.subscriptions)

    # Adding a new subscription
    elif flask.request.method == 'POST' and 'id_or_title' in flask.request.form:
        try:
            youtube_id = youtube.get_id(flask.request.form['id_or_title'])
        except Exception as ex:
            flask.flash(f'Unable to add {flask.request.form["id_or_title"]}, could not find subscription')
            return flask.redirect('/subscriptions')

        feed = Feed.get_or_none(youtube_id = youtube_id)

        if not feed:
            feed = Feed.create(youtube_id = youtube_id)
        
        feed.refresh()
        
        Subscription.create(
            user = User.get(email = flask.session.get('email')),
            feed = feed
        )
        
        return flask.redirect('/subscriptions')

    # Importing an opml file
    elif flask.request.method == 'POST' and 'opml' in flask.request.files:
        file = flask.request.files['opml']

        user = User.get(email = flask.session.get('email'))
        for youtube_id in re.findall(r'xmlUrl="https://www.youtube.com/feeds/videos.xml\?channel_id=(.*?)"', file.read().decode()):
            feed = Feed.get_or_create(youtube_id = youtube_id)[0]
            Subscription.get_or_create(user = user, feed = feed)
        
        return flask.redirect('/subscriptions')

@app.route('/subscriptions/<youtube_id>', methods = ['GET', 'POST', 'DELETE'])
@require_user
def get_single_subscription(youtube_id):
    # Display a single subscription
    if flask.request.method == 'GET':
        # Subscription request
        if flask.request.method == 'GET' and 'confirm' in flask.request.args:
            id = youtube.get_id(youtube_id)
            feed = Feed.get_or_none(youtube_id = id)
            if not feed:
                feed = Feed.create(youtube_id = id)

            return flask.render_template('confirm.html', feed = feed)

        else:
            raise Exception('Not implemented')

    # Delete a subscription
    elif flask.request.method == 'DELETE' or (flask.request.method == 'POST' or 'delete' in flask.request.args):
        user = User.get(email = flask.session.get('email'))
        feed = Feed.get(youtube_id = youtube_id)
        Subscription.get(user = user, feed = feed).delete_instance()

        return flask.redirect('/subscriptions')

@app.route('/filters', methods =['GET', 'POST'])
@require_user
def get_feeds():
    # Display current filters, preload if given that option
    if flask.request.method == 'GET':
        return flask.render_template('filters.html',
            filters = flask.g.user.filters,
            channel = flask.request.args.get('channel'),
            filter = flask.request.args.get('filter')
        )

    # Add a new filter
    elif flask.request.method == 'POST' and 'youtube_id' in flask.request.form:
        youtube_id = flask.request.form['youtube_id']
        filter = flask.request.form['filter']
        whitelist = 'whitelist' in flask.request.form

        # Text that the regexp compiles
        try:
            re.compile(filter, flags = re.IGNORECASE)
        except re.error as ex:
            flask.flash(f'Unable to compile regexp: {ex}')
            flask.redirect('/filters')

        feed = Feed.get(youtube_id = youtube_id)
        
        Filter.create(
            user = User.get(email = flask.session.get('email')),
            feed = feed,
            filter = filter,
            whitelist = whitelist
        )
        
        return flask.redirect('/filters')

@app.route('/filters/<id>', methods = ['GET', 'POST', 'DELETE'])
@require_user
def get_single_filters(id):
    filter = Filter.get(id = id)
    if filter.user != User.get(email = flask.session.get('email')):
        flask.abort(403)

    if flask.request.method == 'GET':
        raise NotImplementedError

    elif flask.request.method == 'POST' and 'action-save' in flask.request.form:
        filter.feed = Feed.get(Feed.youtube_id == flask.request.form.get('youtube_id'))
        filter.filter = flask.request.form.get('filter')
        filter.whitelist = flask.request.form.get('whitelist', 'off').lower() == 'on'
        filter.save()

        flask.flash('Filter saved')


    elif flask.request.method == 'DELETE' or (flask.request.method == 'POST' or 'action-delete' in flask.request.form):
        filter = Filter.get(id = id)

        if filter.user != User.get(email = flask.session.get('email')):
            flask.abort(403)

        filter.delete_instance()
        flask.flash('Filter deleted')

    return flask.redirect('/filters')

@app.route('/videos', methods = ['GET'])
@require_user
def get_videos():
    # Display current most recent videos
    if flask.request.method == 'GET':
        return flask.render_template('videos.html', title = 'Your Videos', videos = flask.g.user.get_videos())

@app.route('/videos/<youtube_id>', methods = ['GET'])
@require_user
def get_single_feed(youtube_id):
    feed = Feed.get(youtube_id = youtube_id)
    videos = Video.select().join(Feed).where(Feed.id == feed.id)

    print(feed)
    print(videos)

    return flask.render_template('videos.html', title = feed.title, videos = videos)

@app.route('/feed/<uuid>.xml', methods = ['GET'])
def get_feed(uuid):
    user = User.get(feed_uuid = uuid)
    videos = user.get_videos()
    updated = user.updated
    for video in videos:
        updated = max(updated, video.updated)

    return flask.Response(
        flask.render_template('feed.xml', 
            title = user.email,
            path = f'/feed/{user.feed_uuid}.xml',
            updated = updated,
            videos = user.get_videos(),
        ),
        mimetype='application/atom+xml'
    )

@app.route('/login', methods = ['POST'])
def login():
    email = flask.request.form['email']
    password = flask.request.form['password']

    user = User.get_or_none(email = email)
    if not user:
        flask.flash('Invalid username or password')
    elif user.password.check_password(password):
        flask.flash('Logged in')
        flask.session['email'] = email

        if 'return_to' in flask.session:
            return_to = flask.session['return_to']
            del flask.session['return_to']
            return flask.redirect(return_to)
    else:
        flask.flash('Invalid username or password')

    return flask.redirect('/')

@app.route('/logout')
def logout():
    del flask.session['email']
    return flask.redirect('/')

@app.route('/register', methods = ['GET', 'POST'])
def register():
    if flask.request.method == 'GET':
        return flask.render_template('register.html')
    else:
        email = flask.request.form['email']
        password = flask.request.form['password']

        if User.get_or_none(email = email):
            flask.flash('Username already taken')
            return flask.redirect('/register')

        user = User.create(email = email, password = password)
        user.save()

        flask.flash('New user created')
        flask.session['email'] = email
        
        if 'return_to' in flask.session:
            return_to = flask.session['return_to']
            del flask.session['return_to']
            return flask.redirect(return_to)
        else:
            return flask.redirect('/')

# Legacy compatibility
@app.route('/user/<id_or_username>.xml')
@app.route('/user/<id_or_username>/atom.xml')
@app.route('/channel/<id_or_username>.xml')
@app.route('/channel/<id_or_username>/atom.xml')
@app.route('/legacy/<id_or_username>.xml')
def legacy(id_or_username):
    youtube_id = youtube.get_id(id_or_username)
    feed = Feed.get_or_create(youtube_id = youtube_id)[0]

    return flask.Response(
        flask.render_template('feed.xml', 
            title = feed.title,
            path = f'/legacy/{feed.youtube_id}.xml',
            updated = feed.updated,
            videos = feed.get_videos(),
        ),
        mimetype='application/atom+xml'
    )