#!/usr/bin/python
# -*- coding: utf-8 -*-

import os, sys
from datetime import datetime
import time
try: 
   from hashlib import md5
except ImportError:
   from md5 import md5
   
METHODS = []

curdir = os.path.join(os.path.dirname(__file__))
site_packages = os.path.join(curdir,'..', 'site_packages')
if site_packages not in sys.path:
    sys.path.insert(0, site_packages)
if curdir not in sys.path:
    sys.path.insert(0, curdir)

import simplejson as json

DATABASE = os.path.join(curdir, 'timetracker.db')
DEBUG = False

from sqlalchemy import create_engine, func
from sqlalchemy import Table, Column, Integer, Float, String, DateTime, MetaData, ForeignKey, Unicode, Boolean
from sqlalchemy.sql.expression import and_, or_, between, asc
from sqlalchemy.orm import sessionmaker, mapper, relation
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.session import object_session

if not os.path.exists(DATABASE):
    mustReset = True
else:
    mustReset = False

class BaseModel(object):
    def __new__(cls, *args, **kwargs):
        if cls==BaseModel:
            raise TypeError, "You can not instantiate a BaseModel"
        return super(BaseModel, cls).__new__(cls, *args, **kwargs)

    @property
    def session(self):
        return session ## object_session(self)        

    def drop(self):
        self.session.delete(self)

    def save(self):
        self.session.add(self)

    def serialize(self):
        tmp = self.__dict__.copy()
        del tmp['_sa_instance_state']
        return json.dumps(tmp)        

    @classmethod
    def load(cls, session, **kwargs):
        q = session.query(cls)
        filters = [getattr(cls, field_name)==kwargs[field_name] \
            for field_name in kwargs]
        result = q.filter(and_(*filters))
        if result.count() != 1:
            return None
        return result.one()        

class User(BaseModel):
    def __init__(self, name, password):
        self.name = name
        self.password = password

    def __repr__(self):
        return '<Activity %r, %r>' % (self.name, self.password)

class Activity(BaseModel):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<Activity %r>' % (self.name)

class ActivityLog(BaseModel):
    def __init__(self, activity):
        self.activity = activity

    def __repr__(self):
        return '<ActivityLog %r>' % (self.activity.name)

engine = create_engine('sqlite:///%s' % DATABASE, echo=DEBUG)

metadata = MetaData()
user_table = Table('user', metadata,
                       Column('id', Integer, primary_key=True),
                       Column('name', String, unique=True),
                       Column('password', String),                       
                       )

activity_table = Table('activity', metadata,
                       Column('id', Integer, primary_key=True),
                       Column('user_id', Integer, ForeignKey('user.id')),
                       Column('name', String(20), unique=True),
                       )

activitylogs_table = Table('activitylog', metadata,
                       Column('id', Integer, primary_key=True),
                       Column('user_id', Integer, ForeignKey('user.id')),                           
                       Column('activity_id', Integer, ForeignKey('activity.id')),
                       Column('description', Unicode),
                       Column('date_start', DateTime, default=datetime.now()),                     
                       Column('date_stop', DateTime, onupdate=datetime.now()),
                       Column('is_completed', Boolean, default=False)
                     )

mapper(User, user_table)
mapper(Activity, activity_table, properties={
            'user': relation(User, backref='activities'),
            })
mapper(ActivityLog, activitylogs_table, properties={
            'activity': relation(Activity, backref='logs'),
            'user': relation(User, backref='logs'),
            })        
metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

    
def rpccall(func):
    METHODS.append(func.__name__)
    def wrapper(**kwargs):
        id = kwargs.pop('id', 0)
        error = False
        result = func(**kwargs)
        if type(result) in [str, unicode]:
          result = str(data)
        elif type(result) == dict:
            if 'error' in result:
                error = result.pop('error')
        return {'id': id, 'result': result, 'error': error}
    return wrapper

@rpccall
def addUser(**kwargs):
    uname = kwargs.get('uname')
    pwd = kwargs.get('pwd')
    u = User.load(session, name=uname)
    if u:
        return {'msg':'User already exists!', 'error': True}
    newuser = User(uname, pwd)
    newuser.save()
    session.commit()
    return {'uid': newuser.id, 'error': False}

@rpccall
def authUser(**kwargs):
    uname = kwargs.get('uname')
    pwd = kwargs.get('pwd')
    u = User.load(session, name=uname)
    if u:
        if u.password == pwd:
            return {'uid': u.id, 'error': False}
        else:
            return {'msg':'Password do not match!', 'error': True}            
    return {'msg':'User do not exist!', 'error': True}

@rpccall
def getStatus(**kwargs):
    uid = kwargs.get('uid')   
    act = ActivityLog.load(session, user_id=uid, is_completed=False)
    if act:
        return {'name': act.activity.name,
                'start': act.date_start.strftime("%d/%m/%Y %H:%M:%S"),
                'current': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                }
    return {'name':'none', 'start':''}

@rpccall
def getActivities(**kwargs):
    uid = kwargs.get('uid')
    user = User.load(session, id=uid)
    if not user:
       return []
    return [a.name for a in user.activities]

@rpccall
def getItem(**kwargs):
    uid = kwargs.get('uid')      
    itemId = kwargs.get('index')
    act = ActivityLog.load(session, user_id=uid, id=itemId)
    if act:
        return { 'index': act.id,
                 'activity_id': act.activity_id,
                 'activity_name': act.activity.name,
                 'description': act.description,
                 'date_start': act.date_start.strftime("%d/%m/%Y %H:%M:%S"),
                 'date_stop': act.date_stop.strftime("%d/%m/%Y %H:%M:%S"),
                 'is_completed': act.is_completed }
        
    return {'msg':'Error occurred', 'error': True}

@rpccall
def editItem(**kwargs):
    uid = kwargs.get('uid')         
    itemId = kwargs.get('index')
    name = kwargs.get('activity_name')
    act = ActivityLog.load(session, user_id=uid, id=itemId)
    if act:
        att = Activity.load(session, user_id=uid, name=name)
        act.activity_id = att.id
        act.description = kwargs['description']
        act.date_start = datetime(*(time.strptime(kwargs['date_start'], "%d/%m/%Y %H:%M:%S")[0:6]))
        act.date_stop = datetime(*(time.strptime(kwargs['date_stop'], "%d/%m/%Y %H:%M:%S")[0:6]))
        act.save()
        session.commit()
        return {'msg':'Item modified', 'error': False}
    return {'msg':'Error occurred', 'error': True}

@rpccall
def deleteItem(**kwargs):
    uid = kwargs.get('uid')            
    itemId = kwargs.get('index')
    act = ActivityLog.load(session, user_id=uid, id=itemId)
    if act:
        act.drop()
        session.commit()        
        return {'msg':'Item deleted', 'error': False}
    return {'msg':'Error occurred', 'error': True}

@rpccall
def startActivity(**kwargs):
    uid = kwargs.get('uid')
    name = kwargs.get('name')
    activity = Activity.load(session, user_id=uid, name=name)
    if not activity:
        activity = Activity(name)
        user.activities.append(activity)
        user.save()
    job = ActivityLog(activity)
    job.user_id = uid
    job.save()
    session.commit()
    status = getStatus(**kwargs)
    return {'msg':'Activity %s started!' % kwargs['name'],
            'status': status}
    #print "Start %s" % name

@rpccall
def stopActivity(**kwargs):
    uid = kwargs.get('uid')
    descr = kwargs.get('descr', '')
    act = ActivityLog.load(session, user_id=uid, is_completed=False)
    if act:
        act.is_completed = True
        act.description = descr
        session.commit()
        status = getStatus(**kwargs)
        return {'id': act.id, 'msg':'Activity %s (%s) stopped!' % (act.activity.name, descr),
                'status': status}
    status = getStatus(**kwargs)
    return {'msg':'Error occurred', 'status': status, 'error': True}
    
@rpccall
def getLogs(**kwargs):
    ret = {}   
    uid = kwargs.get('uid')
    user = User.load(session, id=uid)
    if not user:
        return ret
      
    for a in user.activities:
        logs = {}
        for log in a.logs:
            if not log.is_completed:
                continue
            
            date = log.date_start.strftime("%d/%m/%Y")
            time_start = log.date_start.strftime("%H:%M")
            time_stop = log.date_stop.strftime("%H:%M")            
            delta = (log.id, log.description , str(log.date_stop - log.date_start).split(".")[0], time_start, time_stop)
            
            if logs.has_key(date):
                logs[date].append(delta)
            else:
                logs[date] = [delta]
        ret[a.name] = logs
    return ret

@rpccall
def getLogsByDate(**kwargs):
    ret = {}
    uid = kwargs.get('uid')
    user = User.load(session, id=uid)
    if not user:
        return ret

    for a in user.activities:
        logs = {}
        for log in a.logs:
            if not log.is_completed:
                continue
            date = log.date_start.strftime("%d/%m/%Y")
            time_start = log.date_start.strftime("%H:%M")
            time_stop = log.date_stop.strftime("%H:%M")            
            delta = (log.id, log.description , str(log.date_stop - log.date_start).split(".")[0], time_start, time_stop)
            if not ret.has_key(date):
                ret[date] = {}
            if not ret[date].has_key(a.name):
                ret[date][a.name] = [delta]
            else:
                ret[date][a.name].append(delta)
    return ret

@rpccall
def getMethods(**kwargs):
    return {'methods': METHODS}

if __name__ == '__main__':
    import time
    print startActivity(name="test")
    time.sleep(5)
    print stopActivity(descr="test descr")
    

    for a in session.query(Activity).all():
        print a.name
        for l in a.logs:
            print " "*5, l.date_start, l.date_stop
    raw_input("press enter...")
