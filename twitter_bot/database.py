#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import logging
import sqlalchemy
import sqlalchemy.orm

logger = logging.getLogger(__name__)


class DbManager(object):
    DB_NAME = 'sqlite:///twitter_bot.db'

    def __init__(self):
        self.db_name = DbManager.DB_NAME

    def __enter__(self):
        # Create db session.
        self.db_engine = sqlalchemy.create_engine(self.db_name)
        Session = sqlalchemy.orm.sessionmaker(bind=self.db_engine)
        self.db_session = Session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Check exception.
        try:
            if exc_type:
                try:
                    self.db_session.rollback()
                except:
                    logger.exception('DbManager.__exit__() is failed')
            else:
                self.db_session.commit()
        finally:
            self.close()

        if exc_type:
            return False
        return True

    def close(self):
        # Close db session.
        if self.db_session:
            try:
                self.db_session.close()
            except:
                logger.exception('Closing DB session is failed')
            finally:
                self.db_session = None

    def commit(self):
        if self.db_session:
            self.db_session.commit()
