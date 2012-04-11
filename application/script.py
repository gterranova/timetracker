import android
import os
import time
import urllib
import simplejson as json
from rpcclient import rpcClient
client = rpcClient()

PATH_BASE = '/sdcard/sl4a/scripts/test/'

msg_cancel = {'success': False, 'canceled': True, 'msg': 'Action canceled!'}

import zipfile
zfilename = 'application.zip'

def unzipFiles():
  # test if the file is a valid pkzip file
  if not zipfile.is_zipfile(zfilename):
    print "Not a valid application.zip pkzip file"
    exit()

  # open the zipped file
  zfile = zipfile.ZipFile( zfilename, "r" )

  # get each archived file and process the decompressed data
  for info in zfile.infolist():
    fname = info.filename
    # decompress each file's data
    data = zfile.read(fname)
    dirname = os.path.dirname(fname)
    basename = os.path.basename(fname)

    if basename == '':
      if not os.path.exists(dirname):
        os.makedirs(dirname)
    else:      
      # save the decompressed data to a new file
      fout = open(fname, "w")
      fout.write(data)
      fout.close()

def echo(fn):
  from itertools import chain
  def wrapped(*v, **k):
    name = fn.__name__
    result = fn(*v, **k)
    print "%s(%s) -> %s" % (name, ", ".join(map(repr, chain(v, k.values()))), result)    
    return result
  return wrapped

# Change to script directory
if os.path.exists( PATH_BASE ) is False:
  try:
    os.makedirs( PATH_BASE )
  except:
    exit()
os.chdir(PATH_BASE)

class UIHandler(object):
  def __init__(self, waitfor=None, post=None):
    # Name of the event to wait for - default python
    self.waitfor = waitfor or "python"

    # Name of the event to post
    self.post = post or "javascript"

    self.droid = android.Android()
    self.dispatch = {}

  def wait(self):
    print "wait..."
    event = self.droid.eventWaitFor(self.waitfor)
    # This is currently needed because if the waitForEvent is too fast, the event is missed
    start = time.time()
    data = event.result["data"]
    if type(data) in [str, unicode]:
      data = str(data)
      try:
        data = json.loads(data)
      except:
        print "Unable to parse Json data upon receiving event. Data passed: %s" % data
        data = {}
    else:
      print "Data received from event is not a string, using empty dict"
      data = {}
    data = dict([(str(k), v) for k, v in data.items()])
    if data.has_key('task') and hasattr(self, data["task"]):
      task = data.pop('task')
      f = getattr(self, task)
      print "Calling %s with %s" % (task, data)
      feedback = f(**data)
      passing = json.dumps(feedback)
    else:
      passing = None

    howlong = time.time() - start
    min = 0.4
    if howlong < min:
      time.sleep(min - howlong)
      print "Had to wait cause process was only %f second" % howlong
    self.droid.eventPost(self.post, passing)

  def log(self, **kwargs):
    message="LOG: " % kwargs.get('message', '')   
    print message

  def startLoad(self, **kwargs):
    title= kwargs.get('title', '')
    message=kwargs.get('message', '')
    self.droid.dialogCreateSpinnerProgress(title, message)
    self.droid.dialogShow()
    return {'success':True}

  def stopLoad(self, **kwargs):
    self.droid.dialogDismiss()
    return {'success':True}    

class Application(UIHandler):
  def __init__(self):
    UIHandler.__init__(self)
    # Create the dispatch dict which maps tasks to functions
    result = client.getStatus()
    if result.error:
      print "ERROR:", result.error
    self.status = result.result
    self.activities = None
    self.droid.webViewShow('file://%s' % os.path.join(PATH_BASE, 'html','template.html'))

  def run(self):
    droid = self.droid    
    while 1:
      if self.activityRunning():
        message = "Working on %(name)s (started on %(start)s)." % self.status
      else:
        message = "What about starting a new activity?"
        
      droid.dialogCreateAlert('Status', message)
      droid.dialogSetPositiveButtonText('New')
      if self.activityRunning():
        droid.dialogSetNegativeButtonText('Stop')
      droid.dialogSetNeutralButtonText('Cancel')
      droid.dialogShow()
      response = droid.dialogGetResponse().result
      if 'canceled' in response:
        break

      if response['which'] == 'positive':
        r = self.startActivity()
        if 'canceled' not in r:
          result = client.getStatus()
          if result.error:
            print "ERROR:", result.error
          self.status = result.result
        droid.makeToast(r['msg'])
      elif response['which'] == 'negative':
        r = self.stopActivity(name=self.status['name'])
        if 'canceled' not in r:
          result = client.getStatus()
          if result.error:
            print "ERROR:", result.error
          self.status = result.result
        droid.makeToast(r['msg'])
      else:
        break

  def getMethods(self, **kwargs):
    return ['getMethods', 'getStatus', 'startLoad', 'stopLoad', 'selectActivity', 'startActivity', 'stopActivity']

  def getStatus(self, **kwargs):
    return self.status
      
  def activityRunning(self):
    return self.status['name'] != 'none'
  
  def selectActivity(self):
    droid = self.droid
    droid.dialogCreateAlert('Activities')
    atts = self.activities or client.getActivities().result
    self.activities = atts[:]
    atts.append("Custom...")
    droid.dialogSetSingleChoiceItems(atts)
    droid.dialogSetPositiveButtonText('Select')
    droid.dialogShow()
    response = droid.dialogGetResponse().result
    if not response or 'canceled' in response:
      return None
    elif response['which'] != 'positive':
      return None
    else:
      item = droid.dialogGetSelectedItems().result[0]
      name = atts[item]
    return name

  def startActivity(self, **kwargs):
    droid = self.droid
    if self.status['name'] != 'none':
      response = self.stopActivity(name=self.status['name'])
      if 'canceled' in response:
        return msg_cancel
      
    response = self.selectActivity()
    if not response:
      return msg_cancel
    elif response == "Custom...":
      response = droid.dialogGetInput('Create new activity', 'Please enter the name:').result
      if not response:
        return msg_cancel
      self.activities.append(response)
    r = client.startActivity(name=response)
    return r

  def stopActivity(self, **kwargs):
    name= kwargs.get('name', '')
    response = self.droid.dialogGetInput('Stop activity', 'Please enter a description for %s:' % name).result
    if not response:
      return msg_cancel
    return client.stopActivity(descr=response)

if __name__ == '__main__':
  if not os.path.exists('installed'): 
    unzipFiles()

  app = Application()
  if 1:
    # Loop
    while True:
      app.wait()
    exit()
  else:
    app.run()    
  exit()
