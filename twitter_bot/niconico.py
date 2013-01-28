#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import calendar
import cookielib
import datetime
import json
import logging
import sqlalchemy
import traceback
import time
import urllib
import urllib2

import urlparse
import xml.dom.minidom

import pprint

from models import PostVideo

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

    def __init__(self, db_manager, user_id, pass_word, fetch_sleep_sec=1, max_retry_count=3,
                 retry_sleep_sec=15, max_fetch_fail_count=2):
        self.db_manager = db_manager
        self.user_id = user_id
        self.pass_word = pass_word
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

    def search_videos(self, keyword, from_datetime=None, sort='f', order='d',
                      page=1, max_count=1, current_count=1, results=None):
        results = results or []

        # Limit the number of fetching.
        if current_count > max_count:
            return results

        from_datetime = from_datetime or datetime.datetime.fromtimestamp(0)

        # Fetch videos from NicoNico.
        json_videos = self._fetch(self._fetch_videos, keyword, sort, order,
                                  page)

        for json_video in json_videos:
            video = NicoVideo(**json_video)
            if video.first_retrieve < from_datetime:
                continue
            results.append(video)

        current_count += 1
        page += 1
        return self.search_videos(keyword, from_datetime, sort, order, page,
                                  max_count, current_count, results)

    def search_videos_with_comments(self, keyword, from_datetime=None,
                                    max_comment_num=1500):
        results = []
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
                logger.info('Sleep {}sec... (_fetch_comments() failed)'
                            .format(sleep_sec))
                time.sleep(sleep_sec)
                continue

            if not result:
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

    def search_latest_commenting_videos(self, keyword, from_datetime=None,
                                        number_of_results=3, expire_days=30,
                                        max_post_count=1, max_count=5,
                                        current_count=1, results=None):
        results = results or []

        if current_count > max_count:
            logger.error('Recursive count over: count='.format(current_count))
            return results

        from_datetime = from_datetime or datetime.datetime.fromtimestamp(0)

        # Search latest commenting videos.
        videos = self.search_videos(keyword, sort='n', page=current_count)
        for video in videos:
            # Check if the video is already posted.
            old_post_video = self.db_manager.db_session.query(PostVideo) \
                .filter(sqlalchemy
                        .and_(PostVideo.video_id == video.id)).first()

            if old_post_video:
                now_date = datetime.datetime.now()
                delta_sec = calendar.timegm(now_date.timetuple()) \
                    - calendar.timegm(old_post_video.last_post_datetime
                                                    .timetuple())

                # Convert days to sec.
                expire_sec = expire_days * 60 * 60 * 24
                if delta_sec < expire_sec and old_post_video.post_count >= max_post_count:
                    logger.debug('Skip video: '
                                 + 'video={}'.format(video)
                                 + ', delta_sec={}'.format(delta_sec)
                                 + ', expire_sec={}'.format(expire_sec))
                    continue

                # Update post video
                old_post_video.post_count += 1
                old_post_video.last_post_datetime = now_date
            else:
                # Add new post_video to database when not registerd
                post_video = PostVideo(video.id)
                logger.info('Add new post_video to database : post_video={}'.format(post_video))
                self.db_manager.db_session.add(post_video)

            results.append(video)
            if len(results) >= number_of_results:
                return results

        current_count += 1
        return self.search_latest_commenting_videos(keyword, from_datetime,
                                                    number_of_results,
                                                    expire_days,
                                                    max_post_count,
                                                    max_count,
                                                    current_count,
                                                    results)

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
                    logger.info('Sleep {}sec... Retry {}: {}({}, {})'
                                .format(sleep_sec, retry_count, func.__name__,
                                        args, kwargs))
                    time.sleep(sleep_sec)
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

    def _fetch_videos(self, keyword, sort='f', order='d', page=1):
        """Searching by keyward, fetch videos from NicoNico.
        sort:
            f first_retrieve (default)
            n num_res
        order:
            d date (default)
        """
        # Make url to search by keyword.
        keyword = urllib.quote(keyword.encode('utf-8'))
        url = NicoSearch.SEARCH_URL + keyword
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
        if not (message_server_url or post_xml):
            return None

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
        if not 'ms' in result or len(result['ms']) < 1:
            logger.error('Could not get message server url: result={}'
                         .format(result))
            return None, None
        ms = result['ms'][0]

        thread_id = result['thread_id'][0]
        user_id = result['user_id'][0]
        fields = {'user_id': user_id, 'thread_id': thread_id}
        post_xml = NicoSearch.POST_XML.format(**fields)

        return ms, post_xml
