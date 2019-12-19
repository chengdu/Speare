Speare Debug Server v0.0.2
Copyright (c) 2019 sevenuc.com. All rights reserved.

This is the Tcl debugger for Speare code editor:
http://sevenuc.com/en/Speare.html

Package source and download:
https://github.com/chengdu/Speare
https://sourceforge.net/projects/speare
http://sevenuc.com/download/tcl_debugger.tar.gz

Package Content:

TclDebugger              
|-- readme.txt         # this file, readme for this package
|-- src                # the source code of the Tcl debugger
|   |-- appLaunch.tcl
|   |-- block.tcl
|   |-- break.tcl
|   |-- dbg.tcl
|   |-- debugger.tcl
|   |-- instrument.tcl
|   |-- location.tcl
|   |-- nub.tcl
|   `-- util.tcl
|-- tclparser.tar.gz  # the source code of the Tcl parser library


Start Debug Server:

0. Compile Tcl interpreter from source:
   Download Tcl from https://sourceforge.net/projects/tcl,
   please select a suitable Tcl version for your project.

   $ tar -zxvf tcl8.5.9-src.tar.gz
   $ cd tcl8.5.9/unix
   $ ./configure --prefix=/Users/yeung/bin/tcl \
      --enable-threads --enable-64bit \
      --enable-corefoundation
   $ make && make install
   $ export PATH=/Users/yeung/bin/tcl/bin:$PATH

   Compile Tcl parser library used by the debugger
   $ tar -zxvf tclparser.tar.gz
   $ cd tclparser
   $ ./configure --prefix=/Users/yeung/bin/tcl/bin \
     --enable-threads --enable-64bit \
     --with-tcl=/Users/yeung/bin/tcl/lib/
   $ make && make install
   After above steps, it should create a file named
   libtclparser1.8.dylib and put under tclparser1.8


1. Configure the debugger
   The configure options of the debugger was directly written 
   in the source code of the debugger, located in
   TclDebugger/src/debugger.tcl.

   # The inner port used by the debugger
   set port 2576

   # The communication port between the debugger and Speare code editor
   set svcPort 9999

   # The location of Tcl interpreter
   set tclsh "/Users/yeung/bin/tcl/bin/tclsh8.5"

   # The source code directory of the Tcl debugger
   set libDir "/Users/yeung/Desktop/TclDebugger/src"

   # The source code directory of the test project
   set startDir "/Users/yeung/Desktop/test"

2. Start Tcl debug server:
   $ cd TclDebugger/src
   $ export PATH=/Users/yeung/bin/tcl/bin:$PATH
   $ tclsh8.5 debugger.tcl

3. Luanch Speare Pro and start debugging session.
   a. select the start script
   b. add breakpoints 
   c. click "Start" button on the debug toolbar of Speare code editor. 
   d. step in, step out, step next, ...

4. Customise the debugger
   a. add filter to ignore variable dump.
      modify the proc dbg::dumpStack in dbg.tcl
 
   b. add filter to ignore folder and file Instrument
      modify the proc dbg::Instrument in dbg.tcl  

      This is useful when you don't want to trace into
      the code of some library.
   
   Note: It's not necessary to add these filters in common debugging situation.



Dec 18 2019





