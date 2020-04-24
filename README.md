# yrss

RSS feeds for YouTube

Google recently discontinued YouTube RSS feeds for individual user uploads. This will act as a replacement.

To run it, specify your YouTube API key as `API_KEY` in your environment (or use an environment file like `env.conf.default`). Then visit the landing page, create a user, and submit feeds. 

For legacy (v1) compatility, you can directly turn a YouTube user into a feed with:

* `/user/{username}.xml`
* `/user/{username}/atom.xml`
* `/channel/{channelid}.xml`
* `/channel/{channelid}/atom.xml`

Feeds will be cached for `CACHE_TIME` (default is one hour).
