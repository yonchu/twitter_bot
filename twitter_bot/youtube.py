#!/usr/bin/env python
# -*- coding: utf-8 -*-

from apiclient.discovery import build
import datetime
import logging

logger = logging.getLogger(__name__)


class YoutubeVideo(object):
    VIDEO_URL = 'http://www.youtube.com/watch?v='

    def __init__(self, video_id, channel_id, description, published_at,
                 thumbnails, title):
        self.vide_id = video_id
        self.channel_id = channel_id
        self.description = description
        self.published_at = published_at
        self.thumbnails = thumbnails
        self.title = title

    def __str__(self):
        return 'vide_id={}, title={}, published_at={}'.format(self.title,
                                                              self.id,
                                                              self.nico_comments)

    def __repr__(self):
        return 'NicoVideo<{}, {}, {}>'.format(self.title, self.id,
                                              self.nico_comments)

    def get_url(self):
        return YoutubeVideo.VIDEO_URL + self.vide_id

    @classmethod
    def fromResponse(self, response):
        video_id = response['id']['videoId']
        title = response['snippet']['title'].encode('utf-8')
        channel_id = response['snippet']['channelId']
        description = response['snippet']['description']
        thumbnails = response['snippet']['thumbnails']

        published_at = response['snippet']['publishedAt']
        if published_at.endswith('Z'):
            published_at = published_at[:-5]
        published_at = datetime.datetime.strptime(published_at,
                                                  '%Y-%m-%dT%H:%M:%S')
        yv = YoutubeVideo(video_id, channel_id, description, published_at,
                          thumbnails, title)
        return yv

    @classmethod
    def is_video(cls, response):
        if response['id']['kind'] == 'youtube#video':
            return True
        return False


class YoutubeSearch(object):
    API_SERVICE_NAME = 'youtube'
    API_VERSION = 'v3'

    # (title, published_at, url)
    TW_TWEET_FORMAT = 'YouTube - {} [{}] | {}'

    def __init__(self, developer_key):
        self.developer_key = developer_key

    def tweet_msgs_for_latest_videos(self, keyword, from_datetime):
        videos = self.search_videos(keyword, from_datetime)

        # Make tweet message.
        tweet_msgs = []
        for video in reversed(videos):
            str_published_at = video.published_at.strftime('%y/%m/%d %H:%M')
            tweet_msg = YoutubeSearch.TW_TWEET_FORMAT.format(video.title,
                                                             str_published_at,
                                                             video.get_url())
            tweet_msgs.append(tweet_msg)

        return tweet_msgs

    def search_videos(self, keyword, from_datetime=None):
        from_datetime = from_datetime or datetime.datetime.fromtimestamp(0)

        youtube = build(YoutubeSearch.API_SERVICE_NAME,
                        YoutubeSearch.API_VERSION,
                        developerKey=self.developer_key)

        search_response = youtube.search().list(
            q=keyword.encode('utf-8'),
            part='id,snippet',
            maxResults=32,
            type='video',
            order='date',
        ).execute()

        videos = []
        for video in search_response.get('items', []):
            if YoutubeVideo.is_video(video):
                youtube_video = YoutubeVideo.fromResponse(video)
                if youtube_video.published_at < from_datetime:
                    break
                videos.append(youtube_video)

        return videos
