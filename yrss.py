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
from enum import Enum
import logging

API_KEY = os.getenv('API_KEY', None)
CACHE_TIME = int(os.getenv('CACHE_TIME', 60 * 60)) # default = 1 hour

if not API_KEY:
    print('Must specify API_KEY')
    sys.exit(-1)

logging.basicConfig(format='%(levelname)s: \t%(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

app = flask.Flask(__name__)

try:
    os.makedirs('.cache')
except:
    pass

class InputType(Enum):
    user = 1
    channel = 2


def generatefeed(channel):
    """
    channel :   channels resource
                see https://developers.google.com/youtube/v3/docs/channels#resource
    """
    channel_url = 'https://www.youtube.com/channel/' + channel['id']
    channel_snippet = channel['snippet']
    channel_title = channel_snippet['title']
    channel_description = channel_snippet['description']
    channel_logo = channel_snippet['thumbnails']['default']['url']
    playlistId = channel['contentDetails']['relatedPlaylists']['uploads']

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
    feed.title(channel_title)
    feed.author({'name': channel_title})
    feed.link(href=channel_url)
    feed.description(channel_description)
    feed.icon("https://www.youtube.com/favicon.ico")
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
<a href="{url}"><img src="{img}" /></a><br />
<a href="{url}">{title}</a>
'''.format(
            url = video_url,
            img = thumbnail,
            title = title,
        ), None, 'html')

    return feed.atom_str()


def getChannel(inputType, name):
    """
    inputType : InputType
                Specifies if the name is a username or channelid
    name :  String
            Username or channelid
    """
    logger.debug("getChannel: Type: " + inputType.name + " id/user: " + name)
    parameters = {
        'part': 'contentDetails,snippet',
        'key': API_KEY,
    }
    if inputType is InputType.user:
        parameters['forUsername'] = name
    elif inputType is InputType.channel:
        parameters['id'] = name
    else:
        logger.error('getChannel: argument inputType is invalid.')
        sys.exit(-1)

    response = requests.get('https://www.googleapis.com/youtube/v3/channels', params=parameters)
    if response.status_code != 200:
        flask.abort(400, 'YouTube API error')
        logger.warning("YouTube API error: " + response.text)
    if not response.json()['items']:
        flask.abort(400, 'User or Channel not found')
        logger.info("User or Channel (" + name + ") not found")

    return response.json()['items'][0]

def getCacheFile(inputType, name):
    """
    inputType : InputType
                Specifies if the name is a username or channelid
    name :  String
            Username or channelid

    Returns the path to the cache file of the given username/channelid
    """
    cache_file = os.path.join('.cache', inputType.name + '_' + name + '.xml')
    return cache_file

def checkCache(inputType, name):
    """
    inputType : InputType
                Specifies if the name is a username or channelid
    name :  String
            Username or channelid

    Returns the cached feed for the given username/channelid.
    If there is no cache or the cache is invalid this function returns False
    """
    cache_file = getCacheFile(inputType, name)
    logger.debug("checkCache: " + cache_file)
    if os.path.exists(cache_file):
        creation_time = os.path.getmtime(cache_file)
        if time.time() - creation_time < CACHE_TIME:
            with open(cache_file) as fin:
                return fin.read()
    return False

def cacheToDisk(inputType, name, feed_txt):
    """
    inputType : InputType
                Specifies if the name is a username or channelid
    name :  String
            Username or channelid
    feed_txt :  String
                Feed to be cached
    Saves the Feed to the username/channelids cache file
    """
    cache_file = getCacheFile(inputType, name)
    logger.debug("cacheToDisk: " + cache_file)
    with open(cache_file, 'w') as fout:
        fout.write(feed_txt)


# Old URLs
@app.route('/<user>.xml')
@app.route('/<user>/atom.xml')
# New URLs
@app.route('/user/<user>.xml')
@app.route('/user/<user>/atom.xml')
def generatefeedFromUser(user):
    cached = checkCache(InputType.user, user)
    if cached:
        return cached
    channeldata = getChannel(InputType.user, user)
    feed_txt = generatefeed(channeldata)
    cacheToDisk(InputType.user, user, feed_txt)
    return feed_txt

@app.route('/channel/<channel>.xml')
@app.route('/channel/<channel>/atom.xml')
def generatefeedFromChannel(channel):
    cached = checkCache(InputType.channel, channel)
    if cached:
        return cached
    channeldata = getChannel(InputType.channel, channel)
    feed_txt = generatefeed(channeldata)
    cacheToDisk(InputType.channel, channel, feed_txt)
    return feed_txt

if __name__ == '__main__':
    app.run(host = '0.0.0.0', port = 9777, debug = '--debug' in sys.argv)
