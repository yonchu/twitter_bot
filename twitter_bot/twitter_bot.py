#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import datetime
import logging
import sqlalchemy
import time
import tweepy

import prettyprint
import utils
from config import Config
from database import DbManager
from models import Job, User, PostVideo
from niconico import NicoSearch
from youtube import YoutubeSearch

logger = logging.getLogger(__name__)


class TwitterBotBase(object):
    CONFIG_SECTION_TWITTER_BOT = 'twitter'

    def __init__(self, bot_config, sleep_time_sec):
        self.sleep_time_sec = sleep_time_sec

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

    def tweet_msg(self, msg, is_sleep=False):
        logger.info('Tweet : {}'.format(msg))
        if self.is_test:
            return
        try:
            self.api.update_status(msg)
        finally:
            if is_sleep:
                time.sleep(self.sleep_time_sec)

    def tweet_msgs(self, msgs):
        if not msgs:
            logger.debug('No tweet messages')
            return
        # [(Exception, tweet), ]
        tweet_count = 0
        failed_list = []
        for msg in msgs:
            try:
                self.tweet_msg(msg, is_sleep=True)
                tweet_count += 1
            except Exception as e:
                logger.exception('Tweet failed msg={}'.format(msg))
                failed_list.append((e, msg))

        logger.info('nico_latest_commenting_video(): {} tweet'
                    .format(tweet_count))
        if failed_list:
            raise Exception('Tweet faild {}'
                            .format(prettyprint.pp_str(failed_list)))


class TwitterBot(TwitterBotBase, DbManager):
    FOLLOW_MARGIN = 100

    def __init__(self, bot_config, sleep_time_sec=1):
        # Init TwitterBotBase.
        TwitterBotBase.__init__(self, bot_config, sleep_time_sec)

        # Init DbManager.
        DbManager.__init__(self)

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
            created_at = utils.utc_str2local_datetime(status.created_at)
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
            created_at = utils.utc_str2local_datetime(status.created_at)
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

    def __init__(self, bot_config, sleep_time_sec=1):
        # Init TwitterBotBase.
        TwitterBotBase.__init__(self, bot_config, sleep_time_sec)

        self.nico_user_id = self.config.get_value('user_id', section='niconico')
        self.nico_pass_word = self.config.get_value('pass_word', section='niconico')
        self.youtube_developer_key = self.config.get_value('developer_key',
                                                           section='youtube')

    def nico_video_post(self, search_keyword, prev_datetime):
        logger.debug('Call nico_video_post({}, {})'
                     .format(search_keyword, prev_datetime))
        if prev_datetime:
            now_date = datetime.datetime.now()
            if now_date - prev_datetime < datetime.timedelta(1):
                old_prev_datetime = prev_datetime
                prev_datetime = prev_datetime - datetime.timedelta(hours=2)
                logger.debug('Change prev_datetime: {} -> {}'
                             .format(old_prev_datetime, prev_datetime))

        with DbManager() as db_manager:
            nico = NicoSearch(db_manager, self.nico_user_id, self.nico_pass_word)
            nico.login()
            # Search latest videos by NicoNico.
            videos = nico.search_videos(search_keyword, prev_datetime)

            tweet_count = 0
            failed_list = []
            for video in reversed(videos):
                # Check if the video is already posted.
                old_post_video = db_manager.db_session.query(PostVideo) \
                    .filter(sqlalchemy
                            .and_(PostVideo.video_id == video.id)).first()

                if old_post_video:
                    logger.debug('Skip posted video: video={}'.format(video))
                    continue

                # Add new post_video to database when not registerd
                post_video = PostVideo(video.id)
                logger.info('Add new post_video to database : post_video={}'
                            .format(post_video))
                db_manager.db_session.add(post_video)

                # Make message for twitter.
                str_first_retrieve = video.first_retrieve.strftime('%y/%m/%d %H:%M')
                msg = utils.make_tweet_msg(self.TW_NICO_VIDEO_TWEET_FORMAT,
                                           str_first_retrieve,
                                           title=video.title,
                                           url=video.get_url())
                try:
                    self.tweet_msg(msg, is_sleep=True)
                    tweet_count += 1
                    db_manager.db_session.commit()
                except Exception as e:
                    db_manager.db_session.rollback()
                    logger.exception('Tweet failed msg={}'.format(msg))
                    failed_list.append((e, msg))

            logger.info('nico_latest_commenting_video(): {} tweet'
                        .format(tweet_count))
            if failed_list:
                raise Exception('Tweet faild {}'
                                .format(prettyprint.pp_str(failed_list)))

    def nico_comment_post(self, search_keyword, prev_datetime,
                          max_comment_num=1500, max_tweet_num_per_video=3,
                          filter_func=None):
        logger.debug('Call nico_comment_post({}, {}, {}, {}, {})'
                     .format(search_keyword, prev_datetime, max_comment_num,
                             max_tweet_num_per_video, filter_func))
        with DbManager() as db_manager:
            nico = NicoSearch(db_manager, self.nico_user_id, self.nico_pass_word)
            nico.login()
            # Search latest comments by NicoNico.
            videos = nico.search_videos_with_comments(search_keyword,
                                                      prev_datetime,
                                                      max_comment_num)
            tweet_count = 0
            failed_list = []
            for video in videos:
                if filter_func and filter_func(video):
                    continue
                for nico_comment in video.get_latest_comments(max_tweet_num_per_video):
                    # Make message for twitter.
                    msg = utils.make_tweet_msg(self.TW_NICO_COMMENT_TWEET_FORMAT,
                                               nico_comment.vpos,
                                               nico_comment.post_datetime,
                                               comment=nico_comment.comment,
                                               title=video.title,
                                               url=video.get_url())
                    try:
                        self.tweet_msg(msg, is_sleep=True)
                        tweet_count += 1
                    except Exception as e:
                        logger.exception('Tweet failed msg={}'.format(msg))
                        failed_list.append((e, msg))

            logger.info('nico_latest_commenting_video(): {} tweet'
                        .format(tweet_count))
            if failed_list:
                raise Exception('Tweet faild {}'
                                .format(prettyprint.pp_str(failed_list)))

    def nico_latest_commenting_video_post(self, search_keyword, prev_datetime,
                                          number_of_results=3, expire_days=30,
                                          max_post_count=1):
        logger.debug('Call nico_latest_commenting_video_post({}, {}, {}, {}, {})'
                     .format(search_keyword, prev_datetime, number_of_results,
                             expire_days, max_post_count))
        with DbManager() as db_manager:
            nico = NicoSearch(db_manager, self.nico_user_id, self.nico_pass_word)
            nico.login()
            # Search latest commenting videos by NicoNico.
            it = nico.search_latest_commenting_videos(search_keyword,
                                                      prev_datetime,
                                                      number_of_results,
                                                      expire_days,
                                                      max_post_count)
            tweet_count = 0
            failed_list = []
            for video in it:
                # Make message to tweet.
                str_first_retrieve = video.first_retrieve.strftime('%y/%m/%d %H:%M')
                msg = utils.make_tweet_msg(self.TW_NICO_DETAIL_VIDEO_TWEET_FORMAT,
                                           str_first_retrieve,
                                           video.view_counter,
                                           video.num_res,
                                           video.mylist_counter,
                                           title=video.title,
                                           url=video.get_url())
                try:
                    self.tweet_msg(msg, is_sleep=True)
                    tweet_count += 1
                    db_manager.db_session.commit()
                except Exception as e:
                    db_manager.db_session.rollback()
                    logger.exception('Tweet failed msg={}'.format(msg))
                    failed_list.append((e, msg))

            logger.info('nico_latest_commenting_video(): {} tweet'
                        .format(tweet_count))
            if failed_list:
                raise Exception('Tweet faild {}'
                                .format(prettyprint.pp_str(failed_list)))

    def youtube_video_post(self, search_keyword, prev_datetime):
        youtube = YoutubeSearch(self.youtube_developer_key)
        videos = youtube.search_videos(search_keyword, prev_datetime)
        if not videos:
            logger.info('youtube_video_post(): No tweet messages')
            return
        # Make tweet message.
        for video in reversed(videos):
            str_published_at = video.published_at.strftime('%y/%m/%d %H:%M')
            tweet_msg = utils.make_tweet_msg(self.TW_YOUTUBE_TWEET_FORMAT,
                                             str_published_at,
                                             title=video.title,
                                             url=video.get_url())
            self.tweet_msg(tweet_msg)
