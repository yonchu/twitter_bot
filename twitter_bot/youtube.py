#!/usr/bin/env python
# -*- coding: utf-8 -*-

from apiclient.discovery import build
import calendar
import datetime
import logging
import time

logger = logging.getLogger(__name__)


class YoutubeVideo(object):
    VIDEO_URL = 'http://www.youtube.com/watch?v='

    def __init__(self, video_id, channel_id, description, published_at,
                 thumbnails, title):
        self.video_id = video_id
        self.channel_id = channel_id
        self.description = description
        self.published_at = published_at
        self.thumbnails = thumbnails
        self.title = title

        self.utc_published_at = None

    def __str__(self):
        return 'video_id={}, title={}, utc_published_at={}, published_at={}' \
            .format(self.video_id, self.title, self.utc_published_at,
                    self.published_at)

    def __repr__(self):
        return 'NicoVideo<{}, {}, {}, {}>'.format(self.video_id, self.title,
                                                  self.utc_published_at,
                                                  self.published_at)

    @classmethod
    def _utc_str2jst_datetime(cls, utc_str):
        if not utc_str.endswith('Z'):
            raise ValueError('Unknown format: {}'.format(utc_str))
        utc_str = utc_str[:-5]
        utc_time = time.strptime(utc_str, '%Y-%m-%dT%H:%M:%S')
        jst_time = time.localtime(calendar.timegm(utc_time))
        jst_datetime = datetime.datetime(*jst_time[:6])
        return jst_datetime

    def get_url(self):
        return YoutubeVideo.VIDEO_URL + self.video_id

    @classmethod
    def fromResponse(cls, response):
        video_id = response['id']['videoId']
        title = response['snippet']['title'].encode('utf-8')
        channel_id = response['snippet']['channelId']
        description = response['snippet']['description']
        thumbnails = response['snippet']['thumbnails']

        utc_published_at = response['snippet']['publishedAt']
        published_at = cls._utc_str2jst_datetime(utc_published_at)

        yv = YoutubeVideo(video_id, channel_id, description, published_at,
                          thumbnails, title)
        yv.utc_published_at = utc_published_at
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
        logger.debug('Call tweet_msgs_for_latest_videos({}, {})'.format(keyword, from_datetime))
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
                logger.debug('youtube_video={}'.format(youtube_video))
                if youtube_video.published_at < from_datetime:
                    continue
                videos.append(youtube_video)

        return videos
