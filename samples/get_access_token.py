#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# https://dev.twitter.com/apps
#

from __future__ import print_function
import tweepy


def main():
    """main function"""
    consumer_key = raw_input('Consumer key: ').strip()
    consumer_secret = raw_input('Consumer secret: ').strip()

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth_url = auth.get_authorization_url()

    print('Access to authorize by browser: ' + auth_url)
    verifier = raw_input('PIN: ').strip()

    auth.get_access_token(verifier)
    print("ACCESS_KEY = '{}'".format(auth.access_token.key))
    print("ACCESS_SECRET = '{}'".format(auth.access_token.secret))

if __name__ == '__main__':
    main()
