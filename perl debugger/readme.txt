Speare Debug Server v0.0.1
Copyright (c) 2019 sevenuc.com. All rights reserved.

This is the Perl debugger for Speare Pro:
http://sevenuc.com/en/Speare.html

Package source and download:
https://github.com/chengdu/Speare
http://sevenuc.com/download/perl_debugger.tar.gz

Directory Structure:

debugger
|____Speare          # Perl debugger for Perl 5
| |____dbutil.pl     # helper file of the debugger
| |____perl5db.pl    # the main source file of the debugger
| |____Devel    
|      |____Debugger.pm # perl5db.pl wrapper
|____killproc.sh     # shell script to kill Perl process
|____readme.txt      # readme for this package


Start Debug Server:
$ cd ~/Desktop/debugger
$ perl -I ~/Desktop/debugger/Speare -d:Debugger fullpath.pl

* Warning: 
  fullpath.pl the file must input with full path.

You can directly switch to any Perl interpreter of version 5 
to start a debugging session or use your own self-compiled
Perl version.

7 Nov 2019

