#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  Description
#

from __future__ import print_function
import tweepy

# https://dev.twitter.com/apps
CONSUMER_KEY = ''
CONSUMER_SECRET = ''


def main():
    """main function"""
    auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth_url = auth.get_authorization_url()

    print('Please authorize: ' + auth_url)
    verifier = raw_input('PIN: ').strip()

    auth.get_access_token(verifier)
    print("ACCESS_KEY = '{}'".format(auth.access_token.key))
    print("ACCESS_SECRET = '{}'".format(auth.access_token.secret))

if __name__ == '__main__':
    main()
