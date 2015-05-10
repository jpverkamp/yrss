import dateutil.parser # python-dateutil
import feedformatter # feedformatter
import flask 
import os
import pprint
import requests
import sys
import time

API_KEY = 'AIzaSyAa6hkKfQR9BY8JtFoDT9OEojMrZyWZRqs'
CACHE_TIME = os.getenv('CACHE_TIME', 60 * 60) # default = 1 hour

app = flask.Flask(__name__)

try:
    os.makedirs('.cache')
except:
    pass

@app.route('/<user>.xml')
@app.route('/<user>/atom.xml')
def generatefeed(user):
    # Try the cache first, unless it's old
    cache_file = os.path.join('.cache', user)
    if os.path.exists(cache_file):
        creation_time = os.path.getmtime(cache_file)
	if time.time() - creation_time < CACHE_TIME:
	    print 'Loading {user} from cache ({age} seconds old)'.format(
		user = user,
		age = time.time() - creation_time
	    )
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
    try:
        playlistId = response.json()['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    except:
        return 'unknown user id: {user}'.format(user = user)

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
    feed = feedformatter.Feed()
    feed.feed['title'] = user + ' (YRSS)'
    feed.feed['author'] = user + ' (YRSS)'
    
    for item in response.json()['items']:
        title = item['snippet']['title']
        description = item['snippet']['description']
        video_id = item['snippet']['resourceId']['videoId']
        published = item['snippet']['publishedAt']
        thumbnail = item['snippet']['thumbnails']['high']['url']
	video_url = 'https://www.youtube.com/watch?v=' + video_id

        feed.items.append({
            'title': title,
            'link': video_url,
            'pubDate': dateutil.parser.parse(published).timetuple(),
            'guid': video_id,
	    'description': '''
<a href="{url}"><img src="{img}" /></a>
<a href="{url}">{title}</a>
'''.format(
    url = video_url,
    img = thumbnail,
    title = title,
        )})

    # Cache to disk
    feed_txt = feed.format_atom_string()
    with open(cache_file, 'w') as fout:
        fout.write(feed_txt)

    return feed_txt

if __name__ == '__main__':
    app.run(host = '0.0.0.0', port = 9777, debug = '--debug' in sys.argv)
