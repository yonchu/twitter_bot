#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.ext.declarative

Base = sqlalchemy.ext.declarative.declarative_base()


class Job(Base):
    __tablename__ = 'job'

    # class_name : The Class to call in run().
    class_name = sqlalchemy.Column(sqlalchemy.String, primary_key=True)

    # function_name : The function to call in run().
    function_name = sqlalchemy.Column(sqlalchemy.String, primary_key=True)

    # called_at : Datetime when the function called.
    called_at = sqlalchemy.Column(sqlalchemy.DateTime)

    def __init__(self, class_name, function_name, called_at=None):
        self.class_name = class_name
        self.function_name = function_name
        self.called_at = called_at or datetime.datetime.fromtimestamp(0)

    def __str__(self):
        return 'class_name={}, function_name={}, called_at={}' \
            .format(self.class_name, self.function_name, self.called_at)

    def __repr__(self):
        return "Job<'{}','{}', {}>" \
            .format(self.class_name, self.function_name, self.called_at)


class User(Base):
    __tablename__ = 'user'
    # Twitter user id
    user_id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)

    # Follow status
    #   -1: removed
    #   0 : not following
    #   1 : following
    #   2 : cannot follow back
    follow_status_removed = -2
    follow_status_not_following = 0
    follow_status_following = 1
    follow_status_cannot_follow_back = 2
    follow_status = sqlalchemy.Column(sqlalchemy.Integer)

    # Follower status
    #   0: not follower
    #   1: follower
    follower_status_not_follower = 0
    follower_status_follower = 1
    follower_status = sqlalchemy.Column(sqlalchemy.Integer)

    # Update datetime
    date = sqlalchemy.Column(sqlalchemy.DateTime)

    def __init__(self, user_id, follow_status, follower_status, date):
        self.user_id = user_id
        self.follow_status = follow_status
        self.follower_status = follower_status
        self.date = date

    def __str__(self):
        return 'user_id={}, follow_status={}, follower_status={}, date={}' \
            .format(self.user_id, self.follow_status, self.follower_status,
                    self.date)

    def __repr__(self):
        return "User<'{}',{}, {}, {}>" \
            .format(self.user_id, self.follow_status, self.follower_status,
                    self.date)
