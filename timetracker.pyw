import os, sys

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__),"application"))
except NameError:
    pass

import application.timetracker as timetracker

timetracker.main()
