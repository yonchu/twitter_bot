#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import datetime
import logging
import os
import unittest

from twitter_bot import (Config, NicoSearch, NicoVideo, NicoComment,
                         JobManager, TwitterBot, TwitterBotBase,
                         TwitterVideoBot, Job, User)

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
        TwitterBotBase.__init__(self, bot_config)
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


class TwitterVideoBotTest(unittest.TestCase):
    def setUp(self):
        with TwitterBot(BOT_CONFIG) as bot:
            bot.create_database()

        self.prev_datetime = datetime.datetime.now()
        self.prev_datetime = self.prev_datetime - datetime.timedelta(1)

    def test_nico_video_post(self):
        bot = TwitterVideoBot(BOT_CONFIG)
        bot.is_test = True
        bot.nico_video_post('mbaacc 馬場', self.prev_datetime)

    def test_nico_comment_post(self):
        bot = TwitterVideoBot(BOT_CONFIG)
        bot.is_test = True
        bot.nico_comment_post('mbaacc', self.prev_datetime)

    def test_nico_latest_commenting_video(self):
        bot = TwitterVideoBot(BOT_CONFIG)
        bot.is_test = True
        bot.nico_latest_commenting_video('作業用BGM', self.prev_datetime)

    def test_youtube_video_post(self):
        bot = TwitterVideoBot(BOT_CONFIG)
        bot.is_test = True
        bot.youtube_video_post('mbaacc', self.prev_datetime)


class NicoSearchTest(unittest.TestCase):
    def setUp(self):
        config = Config(BOT_CONFIG, section='niconico')
        self.user_id = config.get_value('user_id')
        self.pass_word = config.get_value('pass_word')

        with TwitterBot(SAMPLE_BOT_CONFIG) as bot:
            bot.create_database()

        self.from_datetime = datetime.datetime.strptime('2013-01-01 00:00:00', '%Y-%m-%d %H:%M:%S')

    def test_make_tweet_msg_for_comments(self):
        nico_search = NicoSearch(self.user_id, self.pass_word)
        post_datetime = datetime.datetime.strptime('2013-01-01 00:00:00', '%Y-%m-%d %H:%M:%S')

        comment = 'x' * 10
        title = 'y' * 10
        url = 'u' * 10
        msg = nico_search._make_tweet_msg_for_comments(comment, '00:00', post_datetime, title, url)
        self.assertTrue(len(msg) < 140)
        self.assertEquals(msg, '[コメント]xxxxxxxxxx (00:00)[13/01/01 00:00] | yyyyyyyyyy uuuuuuuuuu')

        comment = 'x' * 10
        title = 'y' * 110
        url = 'u' * 10
        msg = nico_search._make_tweet_msg_for_comments(comment, '00:00', post_datetime, title, url)
        self.assertEquals(len(msg), 140)
        self.assertEquals(msg, '[コメント]xxxxxxxxxx (00:00)[13/01/01 00:00] | yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy uuuuuuuuuu')

        comment = 'x' * 100
        title = 'y' * 20
        url = 'u' * 10
        msg = nico_search._make_tweet_msg_for_comments(comment, '00:00', post_datetime, title, url)
        self.assertEquals(len(msg), 140)
        self.assertEquals(msg, '[コメント]xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (00:00)[13/01/01 00:00] | yyyyyyyyyyyyyyyyyyyy uuuuuuuuuu')

        comment = 'x' * 100
        title = 'y' * 100
        url = 'u' * 10
        msg = nico_search._make_tweet_msg_for_comments(comment, '00:00', post_datetime, title, url)
        self.assertEquals(len(msg), 140)
        self.assertEquals(msg, '[コメント]xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (00:00)[13/01/01 00:00] | yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy uuuuuuuuuu')

        comment = 'x' * 100
        title = 'y' * 100
        url = 'u' * 20 + 'U' * 5
        msg = nico_search._make_tweet_msg_for_comments(comment, '00:00', post_datetime, title, url)
        self.assertEquals(len(msg), 145)
        self.assertEquals(msg, '[コメント]xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (00:00)[13/01/01 00:00] | yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy uuuuuuuuuuuuuuuuuuuuUUUUU')

    def test_tweet_msgs_for_latest_commenting_videos_exception(self):
        try:
            with NicoSearch(self.user_id, self.pass_word) as nico_search:
                nico_search.login()

                msgs = nico_search.tweet_msgs_for_latest_commenting_videos('作業用BGM', self.from_datetime)
                self.assertTrue(len(msgs) > 0)
                raise Exception('error test')
        except:
            return

        self.fail('Do not occurs exception')

if __name__ == '__main__':
    unittest.main(verbosity=2)
