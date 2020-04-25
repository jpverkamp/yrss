import datetime
import functools
import logging
import os
import requests

API_KEY = os.getenv('API_KEY', None)

def _all(endpoint, **params):
    url = 'https://www.googleapis.com/youtube/v3/' + endpoint.strip('/')
    logging.debug(url, params)

    params.setdefault('key', API_KEY)
    try:
        result = requests.get(url, params = params).json()

        if result['pageInfo']['totalResults'] > result['pageInfo']['resultsPerPage']:
            logging.debug('TODO: implement paging')

        for item in result['items']:
            yield item
    except Exception as ex:
        logging.error(ex)
        logging.error(result)
        raise ex


def _one(endpoint, **params):
    for result in _all(endpoint, **params):
        return result

@functools.lru_cache()
def get_id(id):
    print(id)
    if len(id) == 24:
        return id
    else:
        return get_channel_id_for_username(id)

@functools.lru_cache()
def get_channel_id_for_username(username):
    return _one('/channels', part = 'snippet', forUsername = username)['id']

def get_channel(id):
    data = _one('/channels', part = 'snippet,contentDetails', id = id)

    return {
        'youtube_id': id,
        'title': data['snippet']['title'],
        'updated': datetime.datetime.now(),
        'logo': data['snippet']['thumbnails']['default']['url'],
        'description': data['snippet']['description'],
        'uploads_id': data['contentDetails']['relatedPlaylists']['uploads'],
    }

def get_videos(id):
    for video in _all('/playlistItems', part = 'snippet', maxResults = 20, playlistId = id):
        yield {
            'youtube_id': video['snippet']['resourceId']['videoId'],
            'title': video['snippet']['title'],
            'published': video['snippet']['publishedAt'],
            'updated': datetime.datetime.now(),
            'description': video['snippet']['description'],
            'thumbnail': video['snippet']['thumbnails']['high']['url'],
        }
