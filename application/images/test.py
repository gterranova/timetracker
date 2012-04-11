import time, os
import Image, ImageSequence
from images2gif import writeGif

for f in ['manon','manoff','ladyon', 'ladyoff']:
  frames = []
  files = []
  im = Image.open("%s.gif" % f)
  original_duration = im.info['duration']
  try:
    i=-1
    while 1:
      i=i+1
      im.seek(i)
      print i, im.info, im.format, im.mode
      pixdata = im.load()

      for y in xrange(im.size[1]):
        for x in xrange(im.size[0]):
          if pixdata[x, y] == (255, 255, 255, 255):
            pixdata[x, y] = (0, 0, 0, 0)
      im.save("%s%d.gif" % (f,i), transparency=0)
##      files.append("%s%d.gif" % (f,i))
##      time.sleep(2)
  except Exception:
    pass
##  fp = open("animated%s.gif" % f, 'wb')
##  _writeGifToFile(fp, frames, [original_duration for im in frames], 0)
##  fp.close()
##  frames = [Image.open(f) for f in files]  
##  print len(frames)
##  writeGif("animated%s.gif" % f, frames)

