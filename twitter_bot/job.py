#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import calendar
import datetime
import logging
import sqlalchemy

import prettyprint
from database import DbManager
from models import Job

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
