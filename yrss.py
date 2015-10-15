#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
if sys.version_info[0] != 3:
    print('This script requires Python 3')
    exit()

import dateutil.parser
import feedgen.feed
import flask
import os
import pprint
import re
import requests
import time
from enum import Enum
import logging

API_KEY = os.getenv('API_KEY', None)
CACHE_TIME = int(os.getenv('CACHE_TIME', 60 * 60)) # default = 1 hour

if not API_KEY:
    print('Must specify API_KEY')
    sys.exit(-1)

logging.basicConfig(format='[%(levelname)s] %(funcName)s: %(message)s', level = logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

app = flask.Flask(__name__)

try:
    os.makedirs('.cache')
except:
    pass

class input_type(Enum):
    '''Currently supported channel types'''

    user = 1
    channel = 2

def generate_feed(channel):
    '''
    Turn a channel into an rss feed.

    @param channel The channel resource (see https://developers.google.com/youtube/v3/docs/channels#resource)
    @return string An atom feed for that channel
    '''

    channel_url = 'https://www.youtube.com/channel/' + channel['id']
    channel_snippet = channel['snippet']
    channel_title = channel_snippet['title']
    channel_description = channel_snippet['description']
    channel_logo = channel_snippet['thumbnails']['default']['url']
    playlist_id = channel['contentDetails']['relatedPlaylists']['uploads']

    # Get the most recent 20 videos on the 'uploads' playlist
    response = requests.get(
        'https://www.googleapis.com/youtube/v3/playlistItems',
        params = {
            'part': 'snippet',
            'maxResults': 20,
            'playlistId': playlist_id,
            'key': API_KEY
        }
    )

    # Generate a list of results that can be used as feed items
    feed = feedgen.feed.FeedGenerator()
    feed.title(channel_title)
    feed.author({'name': channel_title})
    feed.link(href=channel_url)
    feed.description(channel_description)
    feed.icon('https://www.youtube.com/favicon.ico')
    feed.logo(channel_logo)
    feed.id(channel_url)

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
        item.id(video_url)

        item.content('''
<a href='{url}'><img src='{img}' /></a><br />
<a href='{url}'>{title}</a>
'''.format(
            url = video_url,
            img = thumbnail,
            title = title,
        ), None, 'html')

    return feed.atom_str()

def get_channel(type, name):
    '''
    Fetch a channel from the YouTube API.

    @param type The type of channel to fetch, see input_type enum
    @param name The name of the channel to fetch (a username / channel id / etc)
    @return json The channel items
    '''

    logger.debug('get_channel: fetching {name} ({type})'.format(type = type.name, name = name))
    parameters = {
        'part': 'contentDetails,snippet',
        'key': API_KEY,
    }

    if type is input_type.user:
        parameters['forUsername'] = name
    elif type is input_type.channel:
        parameters['id'] = name
    else:
        logger.error('unknown channel type: {type}'.format(type = type.name))
        sys.exit(-1)

    response = requests.get('https://www.googleapis.com/youtube/v3/channels', params=parameters)
    if response.status_code != 200:
        logger.warning('YouTube error: {error}'.format(error = response.text))
        flask.abort(400, 'YouTube API error')

    if not response.json()['items']:
        logger.info('resource not found: {name} ({type})'.format(type = type.name, name = name))
        flask.abort(400, 'Resource not found')

    return response.json()['items'][0]

def get_cache_filename(type, name):
    '''
    Determine what filename would be used to cache a specific file.

    @param type The type of channel to fetch, see input_type enum
    @param name The name of the channel to fetch (a username / channel id / etc)
    @return string A filename on the local filesystem to cache results
    '''

    return os.path.join('.cache', '{type}-{name}.xml'.format(type = type.name, name = name))

def check_cache(type, name):
    '''
    Check if given file is in the cache.

    @param type The type of channel to fetch, see input_type enum
    @param name The name of the channel to fetch (a username / channel id / etc)
    @return string The cached XML if it exists (and hasn't expired), otherwise None
    '''

    cache_file = get_cache_filename(type, name)
    logger.debug('is {filename} cached?'.format(filename = cache_file))

    if os.path.exists(cache_file):
        creation_time = os.path.getmtime(cache_file)
        if time.time() - creation_time >= CACHE_TIME:
            logger.debug('{filename} is cached, but the cache has expired'.format(filename = cache_file))
        else:
            logger.debug('loading {filename} from cache'.format(filename = cache_file))
            with open(cache_file) as fin:
                return fin.read()

def cache_to_disk(type, name, data):
    '''
    Write a file to a cache on disk.

    @param type The type of channel to fetch, see input_type enum
    @param name The name of the channel to fetch (a username / channel id / etc)
    @param data The data to write to disk
    '''

    cache_file = get_cache_filename(type, name)
    logger.debug('saving {filename} to cache'.format(filename = cache_file))

    with open(cache_file, 'w') as fout:
        fout.write(data)

def generate_feed_with_cache(type, name):
    '''
    Either load a previously existing feed from cache or generate (and cache) a new one.

    @param type The type of channel to fetch, see input_type enum
    @param name The name of the channel to fetch (a username / channel id / etc)
    @return string The atom XML for the given resource
    '''

    # Exists in cache, return directly
    cached = check_cache(type, name)
    if cached:
        return cached

    # Wasn't cached (or expired), generate a new feed, save, then return
    channel_data = get_channel(type, name)
    feed = generate_feed(channel_data)
    cache_to_disk(type, name, feed)

    return feed

@app.route('/<user>.xml')
@app.route('/<user>/atom.xml')
@app.route('/user/<user>.xml')
@app.route('/user/<user>/atom.xml')
def generate_feed_from_user(user):
    '''
    Generate a user specific RSS feed.

    /<user>.xml is used for backwards compatibility
    '''

    return generate_feed_with_cache(input_type.user, user)

@app.route('/channel/<channel>.xml')
@app.route('/channel/<channel>/atom.xml')
def generate_feed_from_channel(channel):
    '''
    Generate a feed from a YouTube channel.
    '''

    return generate_feed_with_cache(input_type.channel, channel)

if __name__ == '__main__':
    app.run(host = '0.0.0.0', port = 9777, debug = '--debug' in sys.argv)
