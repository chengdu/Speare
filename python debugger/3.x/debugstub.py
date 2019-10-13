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

from __future__ import print_function
import errno
import os
import re
import socket
import sys
from debugger import Debugger

__version__ = '0.0.2'
def info(message, stderr=sys.__stderr__):
    print(message, file=stderr)
    stderr.flush()

class SocketHandle(object):
    def __init__(self, connection):
        self.connection = connection
        self.stream = fh = connection.makefile('rw')
        self.read = fh.read
        self.readline = fh.readline
        self.readlines = fh.readlines
        self.close = fh.close
        self.flush = fh.flush
        self.fileno = fh.fileno
        if hasattr(fh, 'encoding'):
            self._send = lambda data: connection.sendall(data.encode(fh.encoding))
        else:
            self._send = connection.sendall

    @property
    def encoding(self):
        return self.stream.encoding

    def __iter__(self):
        return self.stream.__iter__()

    def write(self, data, nl_rex=re.compile("\r?\n")):
        data = nl_rex.sub("\r\n", data)
        self._send(data)

    def writelines(self, lines, nl_rex=re.compile("\r?\n")):
        for line in lines:
            self.write(line, nl_rex)
        self.stream.flush()

class Debugstub(Debugger):
    active_instance = None
    
    def __init__(self, sock, connection):
        self._quiet = False
        patch_stdstreams=False
        self.sock = sock
        self.connection = connection
        self.handle = SocketHandle(connection)
        Debugger.__init__(self, completekey='tab', stdin=self.handle, stdout=self.handle)
        self.backup = []
        if patch_stdstreams:
            for name in (
                    'stderr',
                    'stdout',
                    '__stderr__',
                    '__stdout__',
                    'stdin',
                    '__stdin__',
            ):
                self.backup.append((name, getattr(sys, name)))
                setattr(sys, name, self.handle)
        Debugstub.active_instance = self

    def message(self, msg):
        print(msg, file=self.stdout)
        print('\r\n', file=self.stdout)

    def release_sock(self):
        info('*** socket released.')
        if self.connection: self.connection.close()
        if self.sock: self.sock.close()

    def onexception(self):
        self.release_sock()

    def __restore(self):
        if self.backup and not self._quiet:
            info('*** Restoring streams: %s ...' % self.backup)
        for name, fh in self.backup:
            setattr(sys, name, fh)
        self.release_sock()
        self.handle.close()
        Debugstub.active_instance = None

    def do_quit(self, arg):
        self.__restore()
        return Debugger.do_quit(self, arg)

    do_q = do_exit = do_quit

    def set_trace(self, frame=None):
        if frame is None:
            frame = sys._getframe().f_back
        try:
            Debugger.set_trace(self, frame)
        except IOError as exc:
            if exc.errno != errno.ECONNRESET:
                raise

