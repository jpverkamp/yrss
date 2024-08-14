import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import models
import requests
import time
import datetime

thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=30)

for video in models.Video().select().where(models.Video.published > thirty_days_ago):
    print("Checking", video.youtube_id, end="... ")

    response = requests.head(
        f"https://www.youtube.com/shorts/{video.youtube_id}",
        allow_redirects=False,
    )
    video.short = not (response.status_code >= 300 and response.status_code < 400)
    video.save()

    print("short" if video.short else "not short")

    time.sleep(0.1)
