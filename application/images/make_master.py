#!/usr/bin/python

# This work is licensed under the Creative Commons Attribution 3.0 United 
# States License. To view a copy of this license, visit 
# http://creativecommons.org/licenses/by/3.0/us/ or send a letter to Creative
# Commons, 171 Second Street, Suite 300, San Francisco, California, 94105, USA.

import os
import Image

for f in ['manon','manoff','ladyon', 'ladyoff']:
    images = []
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
                        pixdata[x, y] = (255, 255, 255, 0)
        ##      im.save("%s%d.gif" % (f,i), transparency=0)
        ##      files.append("%s%d.gif" % (f,i))
            images.append(im.copy())
    except:
        pass

    max_width = max_height = 0

    for i in images:
        print i.size
        w, h = i.size
        if w > max_width: max_width = w
        if h > max_height: max_height = w
        

    print "%d images will be combined." % len(images)

    print "all images assumed to be %dx%d." % (max_width, max_height)

    master_width = max_width
    #seperate each image with lots of whitespace
    master_height = (max_height * len(images))
    print "the master image will by %dx%d" % (master_width, master_height)
    print "creating image...",
    master = Image.new(
        mode='RGB',
        size=(master_width, master_height),
        color=(0,0,0,0))  # fully transparent

    print "created."

    for count, image in enumerate(images):
        location = max_height*count
        print "adding fram %d at %d..." % (count, location),
        master.paste(image,(0,location))
        print "added."
    print "done adding icons."
                
    print "saving master.gif...",
    master.save('master%s.gif'%f)
    print "saved!"

    print "saving master.png...",
    master.save('master%s.png'%f)
    print "saved!"

