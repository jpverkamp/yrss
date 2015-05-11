#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit()

import dateutil.parser
import feedgen.feed
import flask
import os
import pprint
import re
import requests
import time

API_KEY = os.getenv('API_KEY', None)
CACHE_TIME = int(os.getenv('CACHE_TIME', 60 * 60)) # default = 1 hour

if not API_KEY:
    print('Must specify API_KEY')
    sys.exit(-1)

app = flask.Flask(__name__)

try:
    os.makedirs('.cache')
except:
    pass

@app.route('/<user>.xml')
@app.route('/<user>/atom.xml')
def generatefeed(user):
    # Validate that it's a valid user id
    # https://support.google.com/a/answer/33386?hl=en
    if not re.match('^[a-z0-9_\'.-]{6,20}$', user):
        flask.abort(400, 'Invalid username format')

    # Try the cache first, unless it's old
    cache_file = os.path.join('.cache', user)
    if os.path.exists(cache_file):
        creation_time = os.path.getmtime(cache_file)
        if time.time() - creation_time < CACHE_TIME:
            with open(cache_file) as fin:
                return fin.read()

    # Use the channel to get the 'uploads' playlist id
    response = requests.get(
        'https://www.googleapis.com/youtube/v3/channels',
        params = {
            'part': 'contentDetails',
            'forUsername': user,
            'key': API_KEY,
        }
    )
    if response.status_code != 200:
        flask.abort(400, 'YouTube API error')
    if not response.json()['items']:
        flask.abort(400, 'User not found')

    playlistId = response.json()['items'][0]['contentDetails']['relatedPlaylists']['uploads']

    # Get the most recent 20 videos on the 'uploads' playlist
    response = requests.get(
        'https://www.googleapis.com/youtube/v3/playlistItems',
        params = {
            'part': 'snippet',
            'maxResults': 20,
            'playlistId': playlistId,
            'key': API_KEY
        }
    )

    # Generate a list of results that can be used as feed items
    feed = feedgen.feed.FeedGenerator()
    feed.title(user + ' (YRSS)')
    feed.author({'name': user + ' (YRSS)'})
    feed.id('YRSS:' + user)

    for item in response.json()['items']:
        title = item['snippet']['title']
        video_id = item['snippet']['resourceId']['videoId']
        published = item['snippet']['publishedAt']
        thumbnail = item['snippet']['thumbnails']['high']['url']
        video_url = 'https://www.youtube.com/watch?v=' + video_id

        item = feed.add_entry()
        item.title(title)
        item.link(href = video_url)
        item.published(dateutil.parser.parse(published))
        item.updated(dateutil.parser.parse(published))
        item.id(video_id)
        item.content('''
<a href="{url}"><img src="{img}" /></a>
<a href="{url}">{title}</a>
'''.format(
            url = video_url,
            img = thumbnail,
            title = title,
        ))

    # Cache to disk
    feed_txt = feed.atom_str()
    with open(cache_file, 'w') as fout:
        fout.write(feed_txt)

    return feed_txt

if __name__ == '__main__':
    app.run(host = '0.0.0.0', port = 9777, debug = '--debug' in sys.argv)
