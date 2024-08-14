import cachetools
import datetime
import logging
import os
import random
import re
import requests
import string
import sqlite3
import uuid

from peewee import Model, SqliteDatabase, TextField, DateTimeField, ForeignKeyField, CompositeKey, BooleanField, UUIDField
from peewee_extra_fields import PasswordField

import youtube

YRSS_CACHE_TIME = int(os.getenv("YRSS_CACHE_TIME", 60 * 60))  # default = 1 hour
YRSS_RSS_COUNT = int(os.getenv("YRSS_CACHE_TIME", 100))
VIDEOS_PER_PAGE = 100

db = SqliteDatabase("yrss2.db")

class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel):
    email = TextField(unique = True)
    password = PasswordField()
    updated = DateTimeField(default = datetime.datetime.now)
    feed_uuid = UUIDField(default = uuid.uuid4, unique = True)

    def get_videos(self, n=YRSS_RSS_COUNT):
        """Get the n most recent videos, skipping any that don"t match filters."""

        page = 0
        count = 0

        while True:
            page += 1
            empty_page = True

            videos = (
                Video.select()
                .join(Feed)
                .join(Subscription)
                .join(User)
                .where(User.id == self.id)
                .order_by(Video.published.desc())
                .paginate(page, VIDEOS_PER_PAGE)
            )

            for video in videos:
                empty_page = False

                if self.filtered(video):
                    continue

                yield video
                count += 1

                if count == n:
                    return

            if empty_page:
                return

    @cachetools.cached(cache = cachetools.TTLCache(1024, 10))
    def filters_for(self, feed_id):
        filters = (
            Filter.select()
            .join(Feed)
            .switch(Filter).join(User)
            .where(User.id == self.id and Feed.id == feed_id)
        )

        return [
            (re.compile(filter.filter, flags = re.IGNORECASE), filter.whitelist)
            for filter in filters
        ]

    def filtered(self, video):
        for regex, whitelist in self.filters_for(video.feed.id):
            m = regex.search(video.title)

            if not m and whitelist:
                return True

            if m and not whitelist:
                return True

        return False

    def __str__(self):
        return f"User<{self.email}>"

class Feed(BaseModel):
    youtube_id = TextField(unique = True)
    title = TextField()
    updated = DateTimeField(default = datetime.datetime.now)
    logo = TextField()
    description = TextField()
    uploads_id = TextField()

    @classmethod
    def create(cls, **kwargs):
        data = youtube.get_channel(kwargs["youtube_id"])
        data.update(kwargs)

        feed = super(Feed, cls).create(**data)
        feed.refresh(force = True)
        return feed

    def refresh(self, force = False):
        since_last_update = (datetime.datetime.now() - self.updated).total_seconds()
        if since_last_update < YRSS_CACHE_TIME:
            if force:
                logging.info(f"Force updating {self}")
            else:
                return
        else:
            logging.info(f"Refreshing {self}")

        updated_something = False

        # Update channel metdata
        self.update(**youtube.get_channel(self.youtube_id))
        if self.dirty_fields:
            updated_something = True
        self.updated = datetime.datetime.now()
        self.save()

        # Fetch feed and store/update the most recent videos
        for video_data in youtube.get_videos(self.uploads_id):
            try:
                # Newly created videos should also check if they're shorts
                # https://stackoverflow.com/questions/71192605/how-do-i-get-youtube-shorts-from-youtube-api-data-v3
                youtube_id = video_data["youtube_id"]
                response = requests.head(
                    f"https://www.youtube.com/shorts/{youtube_id}",
                    allow_redirects=False,
                )
                video.short = not (
                    response.status_code >= 300 and response.status_code < 400
                )

                updated_something = True
                video.save()

                video = Video.create(feed = self, **video_data)
                updated_something = True
                logging.info(f"Created new video: {video}")
            except:
                video = Video.get(feed = self)
                video.update(**video_data)
                if video.dirty_fields:
                    logging.info(f"Updated video with new information: {video}")
                    updated_something = True
                    video.save()

        return updated_something

    def get_videos(self, n=YRSS_RSS_COUNT):
        """Get the n most recent videos"""

        videos = (
            Video.select()
            .join(Feed)
            .where(Feed.id == self.id)
            .where(Video.short == False)
            .order_by(Video.published.desc())
            .paginate(1, YRSS_RSS_COUNT)
        )

        for video in videos:
            yield video

    def __str__(self):
        return f"Feed<{self.title}, {self.youtube_id}>"

class Video(BaseModel):
    youtube_id = TextField(unique = True)
    feed = ForeignKeyField(Feed, backref = "videos")
    title = TextField()
    published = DateTimeField()
    updated = DateTimeField()
    description = TextField()
    thumbnail = TextField()
    short = BooleanField()

    def __str__(self):
        return f"Video<{self.title}, {self.youtube_id}, {self.feed}>"

    def __lt__(self, other):
        return self.published < other.published

class Subscription(BaseModel):
    user = ForeignKeyField(User, backref = "subscriptions")
    feed = ForeignKeyField(Feed)

    class Meta:
        primary_key = CompositeKey("user", "feed")
    
    def __str__(self):
        return f"Subscription<{self.user}, {self.feed}>"

    def __lt__(self, other):
        return self.feed.title.lower() < other.feed.title.lower()

class Filter(BaseModel):
    user = ForeignKeyField(User, backref = "filters")
    feed = ForeignKeyField(Feed)
    filter = TextField()
    whitelist = BooleanField()

    def __str__(self):
        return f"Feed<{self.user}, {self.feed}, {self.whitelist}, {self.filter}>"

    def __lt__(self, other):
        return self.feed.title.lower() < other.feed.title.lower()

db.connect()
db.create_tables([User, Feed, Video, Subscription, Filter])
