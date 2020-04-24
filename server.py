import dateutil.parser
import flask
import functools
import logging
import re
import urllib

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
            flask.flash('You must be logged in to access that content')
            return flask.redirect('/')
    return wrapped

@app.route('/')
def home():
    if flask.g.user:
        return flask.render_template('home.html')
    else:
        return flask.render_template('login.html')

@require_user
@app.route('/subscriptions', methods = ['GET', 'POST'])
def get_subscriptions():
    if flask.request.method == 'GET':
        return flask.render_template('subscriptions.html', subscriptions = flask.g.user.subscriptions)

    # Adding a new subscription
    elif flask.request.method == 'POST' and 'id_or_title' in flask.request.form:
        id_or_title = flask.request.form['id_or_title']

        if len(id_or_title) == 24:
            youtube_id = id_or_title
        else:
            youtube_id = youtube.get_channel_id_for_username(id_or_title)

        feed = Feed.get_or_none(youtube_id = youtube_id)
        if not feed:
            feed = Feed.create(youtube_id = youtube_id)
        feed.refresh()
        
        Subscription.create(
            user = User.get(email = flask.session.get('email')),
            feed = feed
        )
        
        return flask.redirect('/')

    # Importing an opml file
    elif flask.request.method == 'POST' and 'opml' in flask.request.files:
        file = flask.request.files['opml']

        user = User.get(email = flask.session.get('email'))
        for youtube_id in re.findall(r'xmlUrl="https://www.youtube.com/feeds/videos.xml\?channel_id=(.*?)"', file.read().decode()):
            feed = Feed.get_or_create(youtube_id = youtube_id)[0]
            Subscription.get_or_create(user = user, feed = feed)
        
        return flask.redirect('/subscriptions')

@app.route('/subscriptions/<youtube_id>', methods = ['GET', 'POST', 'DELETE'])
def get_single_subscription(youtube_id):
    # Display a single subscription
    if flask.request.method == 'GET':
        raise Exception('Not implemented')

    # Delete a subscription
    elif flask.request.method == 'DELETE' or (flask.request.method == 'POST' or 'delete' in flask.request.args):
        user = User.get(email = flask.session.get('email'))
        feed = Feed.get(youtube_id = youtube_id)
        Subscription.get(user = user, feed = feed).delete_instance()

        return flask.redirect('/subscriptions')

@require_user
@app.route('/filters', methods =['GET', 'POST'])
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
def get_single_filters(id):
    # Display a single filter
    if flask.request.method == 'GET':
        raise Exception('Not implemented')

    # Delete a filter
    elif flask.request.method == 'DELETE' or (flask.request.method == 'POST' or 'delete' in flask.request.args):
        filter = Filter.get(id = id)

        if filter.user != User.get(email = flask.session.get('email')):
            flask.abort(403)

        filter.delete_instance()

        return flask.redirect('/filters')

@require_user
@app.route('/videos', methods = ['GET'])
def get_videos():
    # Display current most recent videos
    if flask.request.method == 'GET':
        return flask.render_template('videos.html', title = 'Your Videos', videos = flask.g.user.get_videos())

@app.route('/videos/<youtube_id>', methods = ['GET'])
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
        flask.render_template('feed.xml', user = user, videos = user.get_videos(), updated = updated),
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
        return flask.redirect('/')
