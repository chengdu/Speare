#!/bin/bash

# start up Speare Debug Server for lldb
if ! [[ $PATH == *"/System/Library/Frameworks/Python.framework/Versions/2.7/bin"* ]]; then
  export PATH=/System/Library/Frameworks/Python.framework/Versions/2.7/bin:$PATH
fi

export PYTHONPATH=/Applications/Xcode.app/Contents/SharedFrameworks/LLDB.framework/Resources/Python
python2.7 lldb_debugger.py

