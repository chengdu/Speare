#! /usr/bin/env python

# A generic Python debugger for Speare Pro.
# Copyright (c) 2019 sevenuc.com. All rights reserved.
# 
# THIS FILE IS PART OF THE ADVANCED VERSION OF SPEARE CODE EDITOR.
# WITHOUT THE WRITTEN PERMISSION OF THE AUTHOR THIS FILE MAY NOT
# BE USED FOR ANY COMMERCIAL PRODUCT.
# 
# More info: 
#    http://sevenuc.com/en/Speare.html
# Contact:
#    Sevenuc support <info@sevenuc.com>
# Issue report and requests pull:
#    https://github.com/chengdu/Speare

import os
import sys
import codecs
import signal
import socket
from bdb import BdbQuit
from debugstub import Debugstub

port = 4444
__version__ = '0.0.2'
if (sys.version_info.major != 2):
    print("Wrong Python version!")
    sys.exit(0)

reload(sys)
sys.setdefaultencoding('utf-8')

def printbanner():
    print("\n")
    print("   ____")
    print("  / __/ __  ___ ___  ___ ___")
    print("  _\\ \\/ _ \\/ -_) _ `/ __/ -_)")
    print(" /___/ .__/\\__/\\_,_/_/  \\__/")
    print("    /_/")
    print("Speare Debug Server v1.0")
    print("(c) http://sevenuc.com \n")

def startDebugger(sock, connection, port, filename):
    print('Start debugging session on: %s' % filename)
    base = os.path.dirname(filename)
    sys.path.insert(0, base)
    signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    dbs = Debugstub(sock, connection)
    dir_path = os.path.dirname(os.path.realpath(__file__))
    files = ["debugger.py", "debugstub.py", "server.py"]
    dbs.excluded_files = map(lambda x: os.path.join(dir_path, x), files)
    dbs.set_trace()
    dbs.basedirs = []
    dbs.basedirs.append(base)
    dbs._runscript(filename)

if len(sys.argv) == 2:
    try: port = int(sys.argv[1])
    except:
        print('*** invalid port number: "%s".' % sys.argv[1])
        sys.exit(0)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_address = ('localhost', port)
sock.bind(server_address) # Address already in use
sock.listen(1) # Listen for incoming connection
filename = None
printbanner()
print('Listen on port %d ...' % port)
connection, client_address = sock.accept()
#connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
while True:
    data = connection.recv(1024) # Receive the startup script
    filename = data.decode('utf-8').strip('\r\n')
    if filename.startswith("b'"): filename = filename[2:-2]
    break
try:
    if filename: startDebugger(sock, connection, port, filename)
    else: print("*** can't get a script to start debugging session.")
finally:
    if connection: connection.close()
    if sock: sock.close()

