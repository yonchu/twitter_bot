#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import datetime
import logging
import os
import unittest

from twitter_bot import (Config, NicoVideo, NicoComment, NicoSearch,
                         JobManager, TwitterBot, TwitterBotBase,
                         DbManager, TwitterVideoBot, Job, User, utils)

SAMPLE_BOT_CONFIG = 'samples/bot.cfg.sample'
BOT_CONFIG = 'samples/bot.cfg'

logging.basicConfig(level=logging.INFO)


class ConfigTest(unittest.TestCase):
    def setUp(self):
        print()
        self.config = Config(SAMPLE_BOT_CONFIG)

    def test_simple(self):
        self.assertEquals(SAMPLE_BOT_CONFIG, (self.config.config_file))
        self.assertEquals('consumer_key', self.config.get_value('consumer_key', section='twitter'))
        self.assertEquals('consumer_secret', self.config.get_value('consumer_secret', section='twitter'))
        self.assertEquals('access_token', self.config.get_value('access_token', section='twitter'))
        self.assertEquals('access_token_secret', self.config.get_value('access_token_secret', section='twitter'))

        self.assertEquals('xxxx@yyyy', self.config.get_value('user_id', section='niconico'))
        self.assertEquals('pass_word', self.config.get_value('pass_word', section='niconico'))

        self.assertEquals('developer_key', self.config.get_value('developer_key', section='youtube'))


class ModelsTest(unittest.TestCase):
    def setUp(self):
        print()
        class_name = self.__class__.__name__
        function_name = ModelsTest.setUp.__name__
        self.job = Job(class_name, function_name)

        self.now = datetime.datetime.now()
        self.user = User('0001', User.follow_status_following, User.follower_status_follower, self.now)

    def test_job(self):
        self.assertEquals(str(self.job),
                          'class_name={}, function_name={}, called_at={}'
                          .format(self.__class__.__name__, ModelsTest.setUp.__name__, '1970-01-01 09:00:00'))

    def test_user(self):
        self.assertEquals(str(self.user),
                          'user_id={}, follow_status={}, follower_status={}, date={}'
                          .format('0001', User.follow_status_following, User.follower_status_follower, self.now))


class SampleBot(TwitterBotBase):
    def __init__(self, bot_config):
        # Init TwitterBotBase.
        TwitterBotBase.__init__(self, bot_config, sleep_time_sec=1)
        self.post1_args = None
        self.post1_kwargs = None

        self.post2_args = None
        self.post2_kwargs = None

        self.post3_args = None
        self.post3_kwargs = None

        self.post4_args = None
        self.post4_kwargs = None

    def post1(self):
        self.post1_args = None
        self.post1_kwargs = None

    def post2(self, arg1, arg2):
        self.post2_args = [arg1, arg2]
        self.post2_kwargs = None

    def post3(self, kwarg1=1, kwarg2=1):
        self.post3_args = None
        self.post3_kwargs = {'kwarg1': kwarg1, 'kwarg2': kwarg2}

    def post4(self, arg1, arg2, kwarg1=1, kwarg2=1):
        self.post4_args = [arg1, arg2]
        self.post4_kwargs = {'kwarg1': kwarg1, 'kwarg2': kwarg2}


class TwitterBotTest(unittest.TestCase):
    def setUp(self):
        pass

    def testCreateDatabase(self):
        with TwitterBot(SAMPLE_BOT_CONFIG) as bot:
            bot.create_database()
        self.assertTrue(os.path.isfile('twitter_bot.db'))

    def testJobManager(self):
        with JobManager() as job_manager:
            ## Register jobs.
            # Make func_and_intervals.
            # (function name, args, kwargs)
            func_and_intervals = []

            func_tuple = (SampleBot.post1, None, None, 1)
            func_and_intervals.append(func_tuple)

            func_tuple = (SampleBot.post2, ['arg1', 'arg2'], None, 1)
            func_and_intervals.append(func_tuple)

            func_tuple = (SampleBot.post3, None, {'kwarg1': 2}, 1)
            func_and_intervals.append(func_tuple)

            func_tuple = (SampleBot.post4, ['arg1', 'arg2'], {'kwarg2': 2}, 1)
            func_and_intervals.append(func_tuple)

            # Register.
            bot = SampleBot(SAMPLE_BOT_CONFIG)
            job_manager.register_jobs(bot, func_and_intervals)

            self.assertTrue(bot.post1_args is None)
            self.assertTrue(bot.post1_kwargs is None)

            self.assertTrue(bot.post2_args is None)
            self.assertTrue(bot.post2_kwargs is None)

            self.assertTrue(bot.post3_args is None)
            self.assertTrue(bot.post3_kwargs is None)

            self.assertTrue(bot.post4_args is None)
            self.assertTrue(bot.post4_kwargs is None)

            # Run jobs.
            job_manager.run()

            self.assertTrue(bot.post1_args is None)
            self.assertTrue(bot.post1_kwargs is None)

            self.assertEquals('arg1', bot.post2_args[0])
            self.assertEquals('arg2', bot.post2_args[1])
            self.assertTrue(bot.post2_kwargs is None)

            self.assertTrue(bot.post3_args is None)
            self.assertEquals(2, bot.post3_kwargs['kwarg1'])
            self.assertEquals(1, bot.post3_kwargs['kwarg2'])

            self.assertEquals('arg1', bot.post4_args[0])
            self.assertEquals('arg2', bot.post4_args[1])
            self.assertEquals(1, bot.post4_kwargs['kwarg1'])
            self.assertEquals(2, bot.post4_kwargs['kwarg2'])

            prev_datetime = job_manager \
                .get_job_called_datetime(SampleBot.__name__,
                                         SampleBot.post1.__name__)
            self.assertTrue(isinstance(prev_datetime, datetime.datetime))


class NicoVideoTest(unittest.TestCase):
    def setUp(self):
        nico_comments = []
        datetime_format = '%Y-%m-%d %H:%M:%S'

        post_datetime = datetime.datetime.strptime('2013-01-05 00:00:00', datetime_format)
        self.nc1 = NicoComment('1', '1', post_datetime)
        nico_comments.append(self.nc1)

        post_datetime = datetime.datetime.strptime('2013-01-01 00:00:00', datetime_format)
        self.nc2 = NicoComment('2', '2', post_datetime)
        nico_comments.append(self.nc2)

        post_datetime = datetime.datetime.strptime('2013-01-06 00:00:00', datetime_format)
        self.nc3 = NicoComment('3', '3', post_datetime)
        nico_comments.append(self.nc3)

        post_datetime = datetime.datetime.strptime('2013-01-03 00:00:00', datetime_format)
        self.nc4 = NicoComment('4', '4', post_datetime)
        nico_comments.append(self.nc4)

        post_datetime = datetime.datetime.strptime('2012-01-03 00:00:00', datetime_format)
        self.nc5 = NicoComment('5', '5', post_datetime)
        nico_comments.append(self.nc5)

        self.nico_video = NicoVideo('titel', 'description_short', '00:00', '2012-01-03 00:00:00', 1, 2, {}, 3, 'id')
        self.nico_video.nico_comments = nico_comments

    def test_tweet_msgs_for_latest_videos(self):
        latest_comments = self.nico_video.get_latest_comments(3)
        self.assertTrue(latest_comments[0] is self.nc4)
        self.assertTrue(latest_comments[1] is self.nc1)
        self.assertTrue(latest_comments[2] is self.nc3)


NG_ID = ['sm16284937', 'sm19370827', 'sm14276357', 'sm16577879', 'sm16570187', 'sm18308612', 'sm18976851', 'sm19644424']


class TwitterVideoBotTest(unittest.TestCase):
    def setUp(self):
        config = Config(BOT_CONFIG, section='niconico')
        self.user_id = config.get_value('user_id')
        self.pass_word = config.get_value('pass_word')

        with TwitterBot(BOT_CONFIG) as bot:
            bot.create_database()

        self.prev_datetime = datetime.datetime.now()
        self.prev_datetime = self.prev_datetime - datetime.timedelta(7)

    def test_nico_video_post(self):
        prev_datetime = datetime.datetime.strptime('2013-01-25 00:00:00', '%Y-%m-%d %H:%M:%S')
        bot = TwitterVideoBot(BOT_CONFIG)
        bot.is_test = True
        bot.nico_video_post('mbaacc 馬場', prev_datetime)

    def test_nico_comment_post(self):
        bot = TwitterVideoBot(BOT_CONFIG)
        bot.is_test = True
        bot.nico_comment_post('mbaacc', self.prev_datetime, filter_func=self.filter_func)

    def filter_func(self, video):
        if video.id in NG_ID:
            return True
        return False

    def test_nico_latest_commenting_video_post(self):
        bot = TwitterVideoBot(BOT_CONFIG)
        bot.is_test = True
        bot.nico_latest_commenting_video_post('作業用BGM', self.prev_datetime)

    def test_nico_latest_commenting_video_post_exception(self):
        with DbManager() as db_manager:
            nico_search = NicoSearch(db_manager, self.user_id, self.pass_word)
            nico_search.login()

            try:
                nico_search.search_latest_commenting_videos('作業用BGM', self.prev_datetime)
                raise Exception('error test')
            except Exception as e:
                if e.message == 'error test':
                    return

        self.fail('Do not occurs exception')

    def test_youtube_video_post(self):
        bot = TwitterVideoBot(BOT_CONFIG)
        bot.is_test = True
        bot.youtube_video_post('mbaacc', self.prev_datetime)


from tweepy.error import TweepError


class TwitterBotBaseTest(unittest.TestCase):
    def setUp(self):
        #from tweepy
        self.bot = TwitterBotBase(SAMPLE_BOT_CONFIG, sleep_time_sec=1)

        self.post_datetime = datetime.datetime.strptime('2013-01-01 00:00:00', '%Y-%m-%d %H:%M:%S')
        self.str_post_datetime = self.post_datetime.strftime('%y/%m/%d %H:%M')

    def test_tweet_msg(self):
        self.bot.is_test = True
        self.bot.tweet_msg('test')

        self.bot.is_test = False
        try:
            self.bot.tweet_msg('test')
            self.fail('No error')
        except TweepError:
            pass

    def test_tweet_msgs(self):
        self.bot.is_test = True
        self.bot.tweet_msg(['test1', 'test2'])

        self.bot.is_test = False
        try:
            self.bot.tweet_msg(['test1', 'test2'])
            self.fail('No error')
        except:
            pass


class UtilTest(unittest.TestCase):
    def setUp(self):
        self.post_datetime = datetime.datetime.strptime('2013-01-01 00:00:00', '%Y-%m-%d %H:%M:%S')
        self.str_post_datetime = self.post_datetime.strftime('%y/%m/%d %H:%M')

    def test_make_tweet_msg1(self):
        title = 'あ' * 10
        url = 'http://' + 'u' * 10
        msg = utils.make_tweet_msg(TwitterVideoBot.TW_NICO_VIDEO_TWEET_FORMAT,
                                   self.str_post_datetime,
                                   title=title, url=url)
        self.assertEquals(len(msg), 62)
        self.assertEquals(msg, '[新着動画]ニコニコ動画 - ああああああああああ [13/01/01 00:00] | ' + url)

        title = 'あ' * 10
        url = 'http://' + 'u' * 140
        msg = utils.make_tweet_msg(TwitterVideoBot.TW_NICO_VIDEO_TWEET_FORMAT,
                                   self.str_post_datetime,
                                   title=title, url=url)
        self.assertEquals(len(msg), 192)
        self.assertEquals(msg, '[新着動画]ニコニコ動画 - ああああああああああ [13/01/01 00:00] | ' + url)

        title = 'あ' * 140
        url = 'http://' + 'u' * 10
        msg = utils.make_tweet_msg(TwitterVideoBot.TW_NICO_VIDEO_TWEET_FORMAT,
                                   self.str_post_datetime,
                                   title=title, url=url)
        self.assertEquals(len(msg), 140)
        self.assertEquals(msg, '[新着動画]ニコニコ動画 - ああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああ [13/01/01 00:00] | ' + url)

    def test_make_tweet_msg2(self):
        title = 'あ' * 140
        url = 'http://' + 'u' * 20
        msg = utils.make_tweet_msg(TwitterVideoBot.TW_NICO_DETAIL_VIDEO_TWEET_FORMAT,
                                   self.str_post_datetime,
                                   1000, 2000, 3000, title=title, url=url)
        self.assertEquals(len(msg), 145)
        self.assertEquals(msg, 'あああああああああああああああああああああああああああああああああああああああああああああああああああああああ [投稿日:13/01/01 00:00, 再生:1000, コメ:2000, マイリス:3000] | ' + url + ' #niconico')

    def test_make_tweet_msg3(self):
        title = 'あ' * 10
        comment = 'ア' * 10
        url = 'http://' + 'u' * 10
        msg = utils.make_tweet_msg(TwitterVideoBot.TW_NICO_COMMENT_TWEET_FORMAT, '00:00',
                                   self.str_post_datetime,
                                   title=title, comment=comment, url=url)
        self.assertEquals(len(msg), 72)
        self.assertEquals(msg, '[コメント]アアアアアアアアアア (00:00) [13/01/01 00:00] | ああああああああああ ' + url)

        title = 'あ' * 10
        comment = 'ア' * 10
        url = 'http://' + 'u' * 100
        msg = utils.make_tweet_msg(TwitterVideoBot.TW_NICO_COMMENT_TWEET_FORMAT, '00:00',
                                   self.str_post_datetime,
                                   title=title, comment=comment, url=url)
        self.assertEquals(len(msg), 162)
        self.assertEquals(msg, '[コメント]アアアアアアアアアア (00:00) [13/01/01 00:00] | ああああああああああ ' + url)

        title = 'あ' * 140
        comment = 'ア' * 10
        url = 'http://' + 'u' * 20
        msg = utils.make_tweet_msg(TwitterVideoBot.TW_NICO_COMMENT_TWEET_FORMAT, '00:00',
                                   self.str_post_datetime,
                                   title=title, comment=comment, url=url)
        self.assertEquals(len(msg), 145)
        self.assertEquals(msg, '[コメント]アアアアアアアアアア (00:00) [13/01/01 00:00] | あああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああああ ' + url)

        title = 'あ' * 140
        comment = 'ア' * 100
        url = 'http://' + 'u' * 20
        msg = utils.make_tweet_msg(TwitterVideoBot.TW_NICO_COMMENT_TWEET_FORMAT, '00:00',
                                   self.str_post_datetime,
                                   title=title, comment=comment, url=url)
        self.assertEquals(len(msg), 144)
        self.assertEquals(msg, '[コメント]アアアアアアアアアアアアアアアアアアアアアアアアアアアアアアアアアアアアアアアアア (00:00) [13/01/01 00:00] | あああああああああああああああああああああああああああああああああああああああああ ' + url)


if __name__ == '__main__':
    unittest.main(verbosity=2)
