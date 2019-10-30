Speare Debug Server v0.0.4
Copyright (c) 2019 sevenuc.com. All rights reserved.

This is the C and C++ debugger for Speare Pro:
http://sevenuc.com/en/Speare.html

Package source and download:
https://github.com/chengdu/Speare
http://sevenuc.com/download/c_debugger.tar.gz

Package Content:

lldb_debugger
|____speare_lldb.json # The template of configure file
|____lldb_debugger.py # The main debugger source code
|____killproc.sh      # shell script to kill Python process
|____server.sh        # shell script to start up debug server
|____readme.txt       # this file, readme for this package


Configure File:
{
  "port": 6789, # The socket communication port both used by the Debug Server and Speare.
  "program": "/path/to/your/binary",   # Full path of your binary
  "args": ["one", "two", "three"],     # Command line parameters
  "environment": [{"name1": "value1"}, {"name2": "value2"}], # Environment variables
  "dSYM": "/Users/henry/Desktop/CDebug/ctest/hello.dSYM",    # Not used at present
  "memorylimits": "4GB",               # Limits of memory usage by the debugger
  "memorylimits_enable": true,         # Turn on or off memory limits
  "remappath": "# your/running/path",  # Source code directory
  "dumpimage": false,                  # Dump binary dependency
  "dumpregisters": false,              # Dump CPU registers
  "dumpframes": false                  # Dump stack frames whenever debugger handle a command
}


Start Debug Server:

0. Compile C or C++ source files with -g option and without optimisation option -O or use -O0
   $ clang -g a.c b.c c.c -o hello
   $ clang++ -g a.cxx b.cxx c.cxx -o hello

1. Set up configure file for the debugging program.
   make a copy of the file speare_lldb.json and check each option carefully.

2. Organising debugging directory.
   ensure the binary and .dSYM file both in the same folder.
   src         # c or c++ source code
   hello       # the binary
   hello.dSYM  # the symbols file

3. Run the start up shell script.
   $ chmod 777 server.sh
   $ bash ./server.sh


Oct 30 2019





