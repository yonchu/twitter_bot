#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import calendar
import datetime
import time

TW_MAX_TWEET_LENGTH = 140
TW_URL_LENGTH = 22


def utc_str2local_datetime(utc_str, src_format='%a %b %d %H:%M:%S +0000 %Y'):
    """str(YYYY-mm-ddTHH:MM:SS:000Z) -> Local datetime"""
    utc_time = time.strptime(utc_str, src_format)
    local_struct_time = time.localtime(calendar.timegm(utc_time))
    local_datetime = datetime.datetime(*local_struct_time[:6])
    return local_datetime


def local_datetime2utc_str(local_datetime, dst_format="%Y-%m-%dT%H:%M:%SZ"):
    """Local datetime -> str(YYYY-mm-ddTHH:MM:SSZ) """
    utc_struct_time = time.gmtime(time.mktime(local_datetime.timetuple()))
    utc_str = time.strftime(dst_format, utc_struct_time)
    return utc_str


def local_datetime2utc_datetime(local_datetime):
    """Local datetime -> UTC datetime"""
    utc_struct_time = time.gmtime(time.mktime(local_datetime.timetuple()))
    #utc_dt = datetime.fromtimestamp(time.mktime(utc_struct_time))
    return datetime.datetime(*utc_struct_time[:6])


def make_tweet_msg(tweet_format, *args, **kwargs):
    # Make tweet message.
    tweet_msg = tweet_format.decode('utf-8').format(*args, **kwargs)
    tweet_msg_len = len(tweet_msg)

    # Consider URL length specifications of twitter.
    url = None
    if 'url' in kwargs:
        url = kwargs['url']
        del(kwargs['url'])
        url_len = len(url)
        if url_len > TW_URL_LENGTH:
            tweet_msg_len -= (url_len - TW_URL_LENGTH)

    delta_tw_max = tweet_msg_len - TW_MAX_TWEET_LENGTH
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
    return make_tweet_msg(tweet_format, *args, **kwargs)
