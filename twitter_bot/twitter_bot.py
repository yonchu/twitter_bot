#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import calendar
import datetime
import logging
import sqlalchemy
import time
import tweepy

import prettyprint
from config import Config
from database import DbManager
from models import Job, User, PostVideo
from niconico import NicoSearch
from youtube import YoutubeSearch

logger = logging.getLogger(__name__)


class JobManager(DbManager):
    def __init__(self):
        DbManager.__init__(self)

        # {'class name': instance}
        self.instances = {}

        # [(class name, function name, args, kwargs, interval_min), ]
        self.functions = []

    def _run_job(self, class_name, function_name, args, kwargs, interval_min):
        job = self.db_session.query(Job) \
            .filter(sqlalchemy
                    .and_(Job.class_name == class_name,
                          Job.function_name == function_name)).first()

        now_date = datetime.datetime.now()
        delta_sec = calendar.timegm(now_date.timetuple()) \
            - calendar.timegm(job.called_at.timetuple())

        if delta_sec < interval_min * 60:
            logger.debug('Skip job : '
                         + 'job={}'.format(job)
                         + ', delta_sec={}'.format(delta_sec)
                         + ', interval_min={}'.format(interval_min))
            return

        if not class_name in self.instances:
            return

        instance = self.instances[class_name]
        function = getattr(instance, function_name)

        # Call function.
        try:
            logger.debug('Start job : {}'.format(job))
            if args and kwargs:
                function(*args, **kwargs)
            elif args:
                function(*args)
            elif kwargs:
                function(**kwargs)
            else:
                function()
        finally:
            job.called_at = now_date
            self.commit()
            logger.debug('End job : {}'.format(job))

    def run(self):
        # [(Exception, func), ]
        failed_funcs = []
        for func in self.functions:
            try:
                self._run_job(*func)
            except Exception as e:
                logger.exception('Jobs failed: func={}'.format(func))
                failed_funcs.append((e, func))

        if failed_funcs:
            raise Exception('Jobs failed {}'
                            .format(prettyprint.pp_str(failed_funcs)))

    def register_jobs(self, instance, func_and_intervals):
        """
        func_and_intervals: [(function, args, kwargs, interval_min), ]
        """
        class_name = instance.__class__.__name__
        self.instances[class_name] = instance

        for func, args, kwargs, interval_min in func_and_intervals:
            function_name = func.__name__
            func_tuple = (class_name, function_name, args, kwargs, interval_min)
            self.functions.append(func_tuple)

            job = Job(class_name, function_name)
            logger.debug('Register job : job={}, interval_min={}'
                         .format(job, interval_min))

            # Check if the job is already registerd.
            old_job = self.db_session.query(Job) \
                .filter(sqlalchemy
                        .and_(Job.class_name == job.class_name,
                              Job.function_name == job.function_name)).first()
            if not old_job:
                # Add function when not registerd
                logger.info('Add new job to database : job={}'.format(job))
                self.db_session.add(job)

        self.commit()

    def get_job_called_datetime(self, class_name, function_name):
        called_datetime = None
        try:
            job = self.db_session.query(Job) \
                .filter(sqlalchemy
                        .and_(Job.class_name == class_name,
                              Job.function_name == function_name)).one()
            called_datetime = job.called_at
        except sqlalchemy.orm.exc.NoResultFound:
            pass
        return called_datetime


class TwitterBotBase(object):
    CONFIG_SECTION_TWITTER_BOT = 'twitter'

    TW_MAX_TWEET_LENGTH = 140
    TW_URL_LENGTH = 20

    def __init__(self, bot_config):
        logger.debug('Read config file: {}'.format(bot_config))

        # Read twitter_bot config.
        self.config = Config(bot_config)
        self.consumer_key = \
            self.config.get_value('consumer_key',
                                  section=TwitterBotBase.CONFIG_SECTION_TWITTER_BOT)
        self.consumer_secret = \
            self.config.get_value('consumer_secret',
                                  section=TwitterBotBase.CONFIG_SECTION_TWITTER_BOT)
        self.access_token = \
            self.config.get_value('access_token',
                                  section=TwitterBotBase.CONFIG_SECTION_TWITTER_BOT)
        self.access_token_secret = \
            self.config.get_value('access_token_secret',
                                  section=TwitterBotBase.CONFIG_SECTION_TWITTER_BOT)

        # Create tweepy api.
        auth = tweepy.OAuthHandler(self.consumer_key, self.consumer_secret)
        auth.set_access_token(self.access_token, self.access_token_secret)
        self.api = tweepy.API(auth)
        self.is_test = False

    def _make_tweet_msg(self, tweet_format, *args, **kwargs):
        # Make tweet message.
        tweet_msg = tweet_format.decode('utf-8').format(*args, **kwargs)
        tweet_msg_len = len(tweet_msg)

        # Consider URL length specifications of twitter.
        url = None
        if 'url' in kwargs:
            url = kwargs['url']
            del(kwargs['url'])
            url_len = len(url)
            if url_len > self.TW_URL_LENGTH:
                tweet_msg_len -= (url_len - self.TW_URL_LENGTH)

        delta_tw_max = tweet_msg_len - self.TW_MAX_TWEET_LENGTH
        if delta_tw_max <= 0:
            return tweet_msg

        kwargs_list = kwargs.items()
        kwargs_list.sort(key=lambda x: len(str(x[1])), reverse=True)

        # Triming tweet message.
        kwargs_list_len = len(kwargs_list)
        if kwargs_list_len == 1:
            key, value = kwargs_list[0]
            value = str(value).decode('utf-8')
            trim_len = delta_tw_max
            value = value[:-trim_len]
            kwargs[key] = value
        elif kwargs_list_len >= 2:
            key0, value0 = kwargs_list[0]
            key1, value1 = kwargs_list[1]
            value0 = str(value0).decode('utf-8')
            value1 = str(value1).decode('utf-8')
            value0_len = len(value0)
            value1_len = len(value1)
            delta = abs(value0_len - value1_len)

            if kwargs_list_len >= 3:
                key2, value2 = kwargs_list[2]
                value2 = str(value2).decode('utf-8')
                value2_len = len(value2)
                value2_delta = value0_len - value2_len + value1_len - value2_len
                if 0 < value2_delta < delta_tw_max:
                    delta_tw_max = value2_delta

            if value0_len > value1_len:
                if delta_tw_max <= delta:
                    value0 = value0[:-delta_tw_max]
                elif delta_tw_max > delta:
                    value0 = value0[:-delta]
            elif value0_len < value1_len:
                if delta_tw_max <= delta:
                    value1 = value1[:-delta_tw_max]
                elif delta_tw_max > delta:
                    value1 = value1[:-delta]
            else:
                if delta_tw_max <= 2:
                    trim_len = 1
                    value0 = value0[:-trim_len]
                    value1 = value1[:-trim_len]
                elif kwargs_list_len >= 3 and value0_len == value2_len:
                    trim_len = int(delta_tw_max / 3)
                    value0 = value0[:-trim_len]
                    value1 = value1[:-trim_len]
                    value2 = value2[:-trim_len]
                    kwargs[key2] = value2
                else:
                    trim_len = delta_tw_max / 2
                    value0 = value0[:-trim_len]
                    value1 = value1[:-trim_len]
            kwargs[key0] = value0
            kwargs[key1] = value1
        else:
            raise Exception('Unexpected kwargs_list={}'.format(kwargs_list))

        # Restore url.
        if url:
            kwargs['url'] = url
        return self._make_tweet_msg(tweet_format, *args, **kwargs)

    def tweet_msg(self, msg):
        logger.info('Tweet : {}'.format(msg))
        if not self.is_test:
            self.api.update_status(msg)

    def tweet_msgs(self, msgs, sleep_time_sec=1):
        if not msgs:
            logger.debug('No tweet messages')
            return
        # [(Exception, tweet), ]
        failed_tweet = []
        for msg in msgs:
            try:
                self.tweet_msg(msg)
            except Exception as e:
                logger.exception('Tweet failed msg={}'.format(msg))
                failed_tweet.append((e, msg))
            finally:
                time.sleep(sleep_time_sec)

        if failed_tweet:
            #fail_msg = '\n'.join('{}: {}'.format(e, m) for e, m in failed_tweet)
            #raise Exception('Tweet faild\n{}'.format(fail_msg))
            raise Exception('Tweet faild {}'
                            .format(prettyprint.pp_str(failed_tweet)))


class TwitterBot(TwitterBotBase, DbManager):
    FOLLOW_MARGIN = 100

    def __init__(self, bot_config):
        # Init TwitterBotBase.
        TwitterBotBase.__init__(self, bot_config)

        # Init DbManager.
        DbManager.__init__(self)

    def _utc2datetime(self, utc_str):
        utc_time = time.strptime(utc_str, '%a %b %d %H:%M:%S +0000 %Y')
        jst_time = time.localtime(calendar.timegm(utc_time))
        jst_datetime = datetime.datetime(*jst_time[:6])
        return jst_datetime

    def _get_follower_ids(self, user_id=None):
        """Get all followers id list of a specified user."""
        followers = []
        cursor = -1
        while True:
            # ret = ([id-list], (position, rest))
            ret = self.api.followers_ids(user_id, cursor=cursor)
            followers += ret[0]
            cursor = ret[1][1]
            if cursor == 0:
                break
        return followers

    def _get_friend_ids(self, user_id=None):
        """Get all frienda id list of a specified user."""
        friends = []
        cursor = -1
        while True:
            ret = self.api.friends_ids(user_id, cursor=cursor)
            friends += ret[0]
            cursor = ret[1][1]
            if cursor == 0:
                break
        return friends

    def create_database(self):
        """Create database and table definition."""
        logger.info('Create database : db_name={}'.format(self.db_name))
        User.metadata.create_all(self.db_engine)
        Job.metadata.create_all(self.db_engine)
        PostVideo.metadata.create_all(self.db_engine)

    def follow_not_following_users(self, limit=10):
        """Follow users who are not follow."""
        date = datetime.datetime.now()

        users = self.db_session.query(User) \
            .filter(User.follow_status == User.follow_status_not_following) \
            .order_by(User.date)
        for user in users:
            try:
                # Follow on twitter.
                logger.info('Follow user : user_id={}'.format(user.user_id))
                self.api.create_friendship(user.user_id)
            except:
                # Cannot follow.
                user.follow_status = User.follow_status_cannot_follow_back
                user.date = date
            else:
                # Update db.
                logger.info('Update user status to following : user_id={}'
                            .format(user.user_id))
                user.follow_status = User.follow_status_following
                user.date = date
                limit -= 1
                if limit == 0:
                    break
        self.commit()

    def unfollow_not_followers(self, limit=-1):
        """Unfollow friends who don't follow back."""
        date = datetime.datetime.now()

        users = self.db_session.query(User) \
            .filter(sqlalchemy
            .and_(User.follower_status == User.follower_status_not_follower,
                  User.follow_status == User.follow_status_following)).order_by(User.date)
        for user in users:
            try:
                # Unfollow on twitter
                logger.info('Unfollow user : user_id={}'.format(user.user_id))
                self.api.destroy_friendship(user.user_id)
            except:
                # Cannot unfollow
                pass
            else:
                # Update db
                logger.info('Update user status to unfollowing : user_id={}'
                            .format(user.user_id))
                user.follow_status = User.follow_status_removed
                user.date = date
                limit -= 1
                if limit <= 0:
                    break
        self.commit()

    def limit_friends(self):
        me = self.api.me()
        if me.friends_count < 2000:
            return

        # followers - friends > FOLLOW_MARGIN
        follow_limit = me.followers_count - me.friends_count
        num_remove = self.FOLLOW_MARGIN - follow_limit
        if num_remove > 0:
            self.unfollow_not_followers(num_remove)

    def retweet_mentions(self, since):
        """Retweet mentions."""
        statuses = self.api.mentions()
        for status in statuses:
            created_at = self._utc2datetime(status.created_at)
            if created_at < since:
                continue
            try:
                logger.info('Retweet mentions : id={}'.format(status.id))
                self.api.retweet(id=status.id)
            except:
                return

    def retweet_retweeted_of_me(self, since):
        """Retweet post retweeted of me."""
        statuses = self.api.retweeted_of_me()
        for status in statuses:
            if status.user.lang != 'ja':
                continue
            created_at = self._utc2datetime(status.created_at)
            if created_at < since:
                continue
            try:
                logger.info('Retweet retweeted of me: id={}'.format(status.id))
                self.api.retweet(id=status.id)
            except:
                return

    def make_follow_list_from_followers(self, target_user_id):
        """Make user list to follow from the followers of specified user."""
        logger.debug('Enter make_follow_list_from_followers()')

        target_user = self.api.get_user(target_user_id)
        follow_candidate_ids = set(self._get_follower_ids(target_user.id))

        date = datetime.datetime.now()

        count = 0
        for candidate_id in follow_candidate_ids:
            try:
                self.db_session.query(User).filter(User.user_id == candidate_id).one()
            except sqlalchemy.orm.exc.NoResultFound:
                # Add user when not follow
                logger.info('Add new following candidate : id={}'
                            .format(candidate_id))
                user = User(candidate_id, User.follow_status_not_following,
                            User.follower_status_not_follower, date)
                self.db_session.add(user)
                count += 1

        self.commit()
        logger.info('Added new following candidates : {}'.format(count))
        logger.debug('Return make_follow_list_from_followers()')

    def update_database(self):
        """Update database."""
        logger.debug('Enter update_database()')

        # Get all followers and followings
        follower_ids = set(self._get_follower_ids())
        following_ids = set(self._get_friend_ids())

        date = datetime.datetime.now()

        # Register users to database.
        for user_id in set(follower_ids) | set(following_ids):
            follow_status = User.follow_status_following if user_id in following_ids \
                else User.follow_status_not_following
            follower_status = User.follower_status_follower if user_id in follower_ids \
                else User.follower_status_not_follower
            try:
                user = self.db_session.query(User).filter(User.user_id == user_id).one()
                user.follow_status = follow_status
                user.follower_status = follower_status
                user.date = date
            except sqlalchemy.orm.exc.NoResultFound:
                user = User(user_id, follow_status, follower_status, date)
                self.db_session.add(user)
                logger.info('Added user to database : user_id={}'.format(user.user_id))

        self.commit()
        logger.debug('Return update_database()')


class TwitterVideoBot(TwitterBotBase):
    # (title, first_retrieve, url)
    TW_NICO_VIDEO_TWEET_FORMAT = '[新着動画]ニコニコ動画 - {title} [{}] | {url}'
    # (title, first_retrieve, view_counter, num_res, url, mylist_counter)
    TW_NICO_DETAIL_VIDEO_TWEET_FORMAT = '{title} [投稿日:{}, 再生:{}, コメ:{}, マイリス:{}] | {url} #niconico'
    # (comment, vpos, post_datetime, title, url)
    TW_NICO_COMMENT_TWEET_FORMAT = '[コメント]{comment} ({}) [{}] | {title} {url}'

    # (title, published_at, url)
    TW_YOUTUBE_TWEET_FORMAT = '[新着動画]YouTube - {title} [{}] | {url}'

    def __init__(self, bot_config):
        # Init TwitterBotBase.
        TwitterBotBase.__init__(self, bot_config)

        self.nico_user_id = self.config.get_value('user_id', section='niconico')
        self.nico_pass_word = self.config.get_value('pass_word', section='niconico')
        self.youtube_developer_key = self.config.get_value('developer_key',
                                                           section='youtube')

    def nico_video_post(self, search_keyword, prev_datetime):
        with NicoSearch(self.nico_user_id, self.nico_pass_word) as nico:
            nico.login()
            tweet_msgs = []
            # Search latest videos by NicoNico.
            videos = nico.search_videos(search_keyword, prev_datetime)
            for video in reversed(videos):
                # Make message for twitter.
                str_first_retrieve = video.first_retrieve.strftime('%y/%m/%d %H:%M')
                tweet_msg = self._make_tweet_msg(self.TW_NICO_VIDEO_TWEET_FORMAT,
                                                 str_first_retrieve,
                                                 title=video.title,
                                                 url=video.get_url())
                tweet_msgs.append(tweet_msg)
            if not tweet_msgs:
                logger.info('nico_video_post(): No tweet messages')
            self.tweet_msgs(tweet_msgs)

    def nico_comment_post(self, search_keyword, prev_datetime,
                          max_comment_num=1500, max_tweet_num_per_video=3,
                          filter_func=None):
        with NicoSearch(self.nico_user_id, self.nico_pass_word) as nico:
            tweet_msgs = []
            nico.login()
            # Search latest comments by NicoNico.
            videos = nico.search_videos_with_comments(search_keyword,
                                                      prev_datetime,
                                                      max_comment_num)
            for video in videos:
                if filter_func and filter_func(video):
                    continue
                for nico_comment in video.get_latest_comments(max_tweet_num_per_video):
                    # Make message for twitter.
                    tweet_msg = self._make_tweet_msg(self.TW_NICO_COMMENT_TWEET_FORMAT,
                                                     nico_comment.vpos,
                                                     nico_comment.post_datetime,
                                                     comment=nico_comment.comment,
                                                     title=video.title,
                                                     url=video.get_url())
                    tweet_msgs.append(tweet_msg)
            if not tweet_msgs:
                logger.info('nico_comment_post(): No tweet messages')
            self.tweet_msgs(tweet_msgs)

    def nico_latest_commenting_video_post(self, search_keyword, prev_datetime,
                                          number_of_results=3, expire_days=30,
                                          max_post_count=1):
        tweet_msgs = []
        with NicoSearch(self.nico_user_id, self.nico_pass_word) as nico:
            nico.login()
            # Search latest commenting videos by NicoNico.
            videos = nico.search_latest_commenting_videos(search_keyword,
                                                          prev_datetime,
                                                          number_of_results,
                                                          expire_days,
                                                          max_post_count)
            for video in videos:
                # Make message to tweet.
                str_first_retrieve = video.first_retrieve.strftime('%y/%m/%d %H:%M')
                tweet_msg = self._make_tweet_msg(self.TW_NICO_DETAIL_VIDEO_TWEET_FORMAT,
                                                 str_first_retrieve,
                                                 video.view_counter,
                                                 video.num_res,
                                                 video.mylist_counter,
                                                 title=video.title,
                                                 url=video.get_url())
                tweet_msgs.append(tweet_msg)
            if not tweet_msgs:
                logger.info('nico_latest_commenting_video(): No tweet messages')
            self.tweet_msgs(tweet_msgs)

    def youtube_video_post(self, search_keyword, prev_datetime):
        youtube = YoutubeSearch(self.youtube_developer_key)
        videos = youtube.search_videos(search_keyword, prev_datetime)

        # Make tweet message.
        tweet_msgs = []
        for video in reversed(videos):
            str_published_at = video.published_at.strftime('%y/%m/%d %H:%M')
            tweet_msg = self._make_tweet_msg(self.TW_YOUTUBE_TWEET_FORMAT,
                                             str_published_at,
                                             title=video.title,
                                             url=video.get_url())
            tweet_msgs.append(tweet_msg)
        if not tweet_msgs:
            logger.info('youtube_video_post(): No tweet messages')
        self.tweet_msgs(tweet_msgs)
