Speare Debug Server v1.0
Copyright (c) 2019 sevenuc.com. All rights reserved.

This is the Python debugger for Speare Pro:
http://sevenuc.com/en/Speare.html

Package source and download:
https://github.com/chengdu/Speare
http://sevenuc.com/download/python_debugger.tar.gz

Directory Structure:

debugger
|____2.x # Python debugger for 2.5, 2.6, 2.7
| |____debugger.py   
| |____debugstub.py
| |____server.py
|____3.x # Python debugger for 3.x
| |____debugger.py
| |____debugstub.py
| |____server.py
|____killproc.sh  # shell script to kill Python process
|____readme.txt   # readme for this package


Start Debug Server:
1. For Python 2.5, 2.6, 2.7
$ cd ~/Desktop/debugger/2.x
$ python server.py

2. For Python 3.x
$ cd ~/Desktop/debugger/3.x
$ python3 server.py

You can directly switch to any Python interpreter to start a 
debugging session or use your own customised Python version.

12 Oct 2019





