#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import cookielib
import datetime
import json
import logging
import traceback
import time
import urllib
import urllib2

import urlparse
import xml.dom.minidom

import pprint

logger = logging.getLogger(__name__)


class NicoVideo(object):
    VIDEO_URL = 'http://www.nicovideo.jp/watch/'

    def __init__(self, title, description_short, length, first_retrieve,
                 mylist_counter, view_counter, thumbnail_url, num_res, id):
        self.title = title
        self.description_short = description_short
        self.length = length
        self.first_retrieve = datetime.datetime.strptime(first_retrieve,
                                                         '%Y-%m-%d %H:%M:%S')
        self.mylist_counter = int(mylist_counter)
        self.view_counter = int(view_counter)
        self.thumbnail_url = thumbnail_url
        self.num_res = int(num_res)
        self.id = id

        self.nico_comments = []

    def __str__(self):
        return 'title={}, id={}, nico_comments={}'.format(self.title, self.id,
                                                          self.nico_comments)

    def __repr__(self):
        return 'NicoVideo<{}, {}, {}>'.format(self.title, self.id,
                                              self.nico_comments)

    def get_url(self):
        return NicoVideo.VIDEO_URL + self.id

    def append_nico_comment(self, nico_comment):
        self.nico_comments.append(nico_comment)

    def get_latest_comments(self, num):
        sorted_ncs = sorted(self.nico_comments, key=lambda x: x.post_datetime)
        return sorted_ncs[-num:]


class NicoComment(object):
    def __init__(self, comment, vpos, post_datetime):
        self.comment = comment
        self.vpos = vpos
        self.post_datetime = post_datetime

    def __str__(self):
        return ('comment={}, ' +
                'vpos={}, ' +
                'post_datetime={}') \
            .format(self.comment, self.vpos, self.post_datetime)

    def __repr__(self):
        return ('NicoComment<{}, {}, {}>') \
            .format(self.comment, self.vpos, self.post_datetime)


class NicoSearch(object):
    LOGIN_URL = 'https://secure.nicovideo.jp/secure/login'
    SEARCH_URL = 'http://www.nicovideo.jp/api/search/search/'
    GETFLV_URL = 'http://flapi.nicovideo.jp/api/getflv/'

    POST_XML = '<packet>' + \
        '<thread thread="{thread_id}" version="20090904" user_id="{user_id}"/>' + \
        '<thread_leaves thread="{thread_id}" user_id="{user_id}">0-99:10,1000</thread_leaves>' + \
        '</packet>'

    TW_MAX_TWEET_LENGTH = 140
    TW_URL_LENGTH = 20

    # (title, first_retrieve, url)
    TW_VIDEO_TWEET_FORMAT = 'ニコニコ動画 - {} [{}] | {}'.decode('utf-8')
    # (comment, vpos, post_datetime, title, url)
    TW_COMMENT_TWEET_FORMAT = '[コメント]{} ({})[{}] | {} {}'.decode('utf-8')

    def __init__(self, user_id, pass_word, max_fetch_count=1,
                 fetch_sleep_sec=1, max_retry_count=3, retry_sleep_sec=15,
                 max_fetch_fail_count=2):
        self.user_id = user_id
        self.pass_word = pass_word
        self.max_fetch_count = max_fetch_count
        self.fetch_sleep_sec = fetch_sleep_sec
        self.max_retry_count = max_retry_count
        self.retry_sleep_sec = retry_sleep_sec
        self.max_fetch_fail_count = max_fetch_fail_count

        self.fetch_fail_count = 0

    def login(self):
        opener = urllib2 \
            .build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
        urllib2.install_opener(opener)
        urllib2.urlopen(NicoSearch.LOGIN_URL,
                        urllib.urlencode({'mail': self.user_id,
                                          'password': self.pass_word}))
        return opener

    def tweet_msgs_for_latest_videos(self, keyword, from_datetime):
        tweet_msgs = []
        # Search latest videos by NicoNico.
        videos = self.search_videos(keyword, from_datetime)
        for video in reversed(videos):
            # Make message for twitter.
            str_first_retrieve = video.first_retrieve.strftime('%y/%m/%d %H:%M')
            tweet_msg = NicoSearch.TW_VIDEO_TWEET_FORMAT \
                                  .format(video.title, str_first_retrieve,
                                          video.get_url())
            tweet_msgs.append(tweet_msg)
        return tweet_msgs

    def tweet_msgs_for_latest_comments(self, keyword, from_datetime,
                                       max_comment_num=1500,
                                       max_tweet_num_per_video=3):
        tweet_msgs = []
        # Search latest comments by NicoNico.
        videos = self.search_videos_with_comments(keyword, from_datetime,
                                                  max_comment_num)
        for video in videos:
            for nico_comment in video.get_latest_comments(max_tweet_num_per_video):
                # Make message for twitter.
                tweet_msg = self._make_tweet_msg_for_comments(nico_comment.comment,
                                                              nico_comment.vpos,
                                                              nico_comment.post_datetime,
                                                              video.title,
                                                              video.get_url())
                tweet_msgs.append(tweet_msg)
        return tweet_msgs

    def search_videos(self, keyword, from_datetime=None, results=None, count=1,
                      sort='f', order='d'):
        results = results or []
        # Limit the number of fetching.
        if count > self.max_fetch_count:
            return results

        from_datetime = from_datetime or datetime.datetime.fromtimestamp(0)

        # Fetch videos from NicoNico.
        json_videos = self._fetch(self._fetch_videos, keyword, count, sort,
                                  order)

        for json_video in json_videos:
            video = NicoVideo(**json_video)
            if video.first_retrieve < from_datetime:
                continue
            results.append(video)

        count += 1
        return self.search_videos(keyword, from_datetime, results, count)

    def search_videos_with_comments(self, keyword, from_datetime=None,
                                    max_comment_num=1500, results=None):
        results = results or []
        from_datetime = from_datetime or datetime.datetime.fromtimestamp(0)

        # Search videos with latest comments by NicoNico.
        videos = self.search_videos(keyword, sort='n')

        for video in videos:
            # Exclude too many commnets videos.
            if not (0 < video.num_res <= max_comment_num):
                continue
            # Fetch comments from NicoNico.
            try:
                result = self._fetch(self._fetch_comments, video)
            except:
                if self.fetch_fail_count > self.max_fetch_fail_count:
                    raise Exception("Fetch fail count over({})\n\n{}"
                                    .format(self.fetch_fail_count,
                                            traceback.format_exc()))
                logger.exception('_fetch_comments() failed but continue')
                sleep_sec = self.retry_sleep_sec * self.max_retry_count * 2
                logger.info('Sleep {}sec...'.format(sleep_sec))
                time.sleep(sleep_sec)
                continue

            dom = xml.dom.minidom.parseString(result.read())

            chats = dom.getElementsByTagName('chat')
            for chat in chats:
                # Get datetime posted a comment.
                post_datetime = chat.getAttribute('date')
                post_datetime = datetime.datetime.fromtimestamp(int(post_datetime))
                if post_datetime < from_datetime:
                    continue

                # Get play time posted a comment.
                vpos = int(chat.getAttribute('vpos'))
                vpos = '{:>02d}:{:>02d}'.format((vpos / 100 / 60),
                                                (vpos / 100 % 60))

                # Get a comment text.
                try:
                    chat_node = chat.childNodes[0]
                except IndexError:
                    continue

                if not chat_node.nodeType == chat_node.TEXT_NODE:
                    continue
                comment = chat_node.data

                nico_comment = NicoComment(comment, vpos, post_datetime)
                video.append_nico_comment(nico_comment)

            if video.nico_comments:
                results.append(video)

        return results

    def _make_tweet_msg_for_comments(self, comment, vpos, post_datetime, title,
                                     url):
        str_post_datetime = post_datetime.strftime('%y/%m/%d %H:%M')
        # Make tweet message.
        tweet_msg = NicoSearch.TW_COMMENT_TWEET_FORMAT.format(comment, vpos,
                                                              str_post_datetime,
                                                              title, url)
        tweet_msg_len = len(tweet_msg)
        # Consider URL length specifications of twitter.
        url_len = len(url)
        if url_len > NicoSearch.TW_URL_LENGTH:
            tweet_msg_len -= (url_len - NicoSearch.TW_URL_LENGTH)

        delta_tw_max = tweet_msg_len - NicoSearch.TW_MAX_TWEET_LENGTH
        if delta_tw_max <= 0:
            return tweet_msg

        comment_len = len(comment.decode('utf-8'))
        title_len = len(title.decode('utf-8'))

        # Triming tweet message.
        delta = abs(comment_len - title_len)
        if comment_len > title_len:
            if delta_tw_max <= delta:
                comment = comment[:-delta_tw_max]
            elif delta_tw_max > delta:
                comment = comment[:-delta]
        elif comment_len < title_len:
            if delta_tw_max <= delta:
                title = title[:-delta_tw_max]
            elif delta_tw_max > delta:
                title = title[:-delta]
        else:
            trim_len = delta_tw_max / 2
            comment = comment[:-trim_len]
            title = title[:-trim_len]

        return self._make_tweet_msg_for_comments(comment, vpos, post_datetime,
                                                 title, url)

    def _fetch(self, func, *args, **kwargs):
        """Run func(*args, **kwargs) with retry."""
        logger.debug('Fetch from NicoNico: {}({}, {})'
                     .format(func.__name__, args, kwargs))

        remaining_retry_count = self.max_retry_count
        while(remaining_retry_count >= 0):
            try:
                retry_count = self.max_retry_count - remaining_retry_count
                if retry_count > 0:
                    sleep_sec = self.retry_sleep_sec * retry_count
                    logger.info('Sleep {}sec...'.format(sleep_sec))
                    time.sleep(sleep_sec)
                    logger.info('Retry {}: {}({}, {})'
                                .format(retry_count, func.__name__, args,
                                        kwargs))
                # Run fetch function.
                result = func(*args, **kwargs)
                break
            except Exception:
                if remaining_retry_count <= 0:
                    self.fetch_fail_count += 1
                    raise
                remaining_retry_count -= 1

        # Sleep so that fetching continuously does not at short times.
        time.sleep(self.fetch_sleep_sec)
        return result

    def _fetch_videos(self, keyword, page=1, sort='f', order='d'):
        """Searching by keyward, fetch videos from NicoNico.
        sort:
            f first_retrieve (default)
            n num_res
        order:
            d date (default)
        """
        # Make url to search by keyword.
        url = NicoSearch.SEARCH_URL + keyword.encode('utf-8')
        params = {}
        params['mode'] = 'watch'
        params['sort'] = sort
        params['order'] = order
        params['page'] = page
        url += '?' + urllib.urlencode(params)

        # Get search result.
        j = json.load(urllib2.urlopen(url), encoding='utf8')

        # Check result status.
        status = j['status']
        if not status == 'ok':
            raise Exception('Fetch videos failed\n' + json.dumps(j, indent=4,
                            ensure_ascii=False))

        return j['list']

    def _fetch_comments(self, video):
        """Fetch comments from NicoNico."""
        message_server_url, post_xml = self._fetch(self._fetch_comment_info,
                                                   video.id)

        headers = {'Content-Type': 'text/xml',
                   'Content-Length': "{}".format(len(post_xml))}
        request = urllib2.Request(url=message_server_url, data=post_xml,
                                  headers=headers)
        result = urllib2.urlopen(request)
        return result

    def _fetch_comment_info(self, video_id):
        """Fetch info to get comments."""
        url = NicoSearch.GETFLV_URL + video_id
        result = urllib2.urlopen(url).read()
        result = urlparse.parse_qs(result)

        # Chek result status.
        if 'error' in result:
            raise Exception('Fetch comment info failed ({})'.format(video_id)
                            + pprint.pformat(result))

        # Message server URL.
        ms = result['ms'][0]

        thread_id = result['thread_id'][0]
        user_id = result['user_id'][0]
        fields = {'user_id': user_id, 'thread_id': thread_id}
        post_xml = NicoSearch.POST_XML.format(**fields)

        return ms, post_xml
