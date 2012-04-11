#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import datetime
from sqlalchemy.orm import sessionmaker    

from sqlalchemy import create_engine, Table, Column, \
     Integer, Float, Text, UnicodeText, Unicode, Boolean, Date, DateTime, ForeignKey, \
     MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref

#sqlitefile = os.path.join(os.path.dirname(__file__),'timetracker.db')
curdir = os.path.join(os.path.dirname(__file__))
sqlitefile = os.path.join(curdir, 'timetracker.db')
engine = create_engine('sqlite:///'+sqlitefile)

Base = declarative_base()

class Activity(Base):
    __tablename__ = 'activity'    
    id = Column(Integer, primary_key=True)
    name = Column(Unicode)
    logs = relationship("ActivityLog")
    def __init__(self, name):
        self.name = name

class ActivityLog(Base):
    __tablename__ = 'activitylog'
    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, ForeignKey('activity.id'))
    description = Column(Unicode)
    date_start = Column(DateTime, default=datetime.datetime.now)
    date_stop = Column(DateTime, onupdate=datetime.datetime.now)
    is_completed = Column(Boolean, default=False)
    

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine, autoflush=True, autocommit=False)
session = Session()
