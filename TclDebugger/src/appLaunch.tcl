# The Tcl debugger for Speare code editor.
# Copyright (c) 1998-2000 Ajuba Solutions
# Copyright (c) 2019 sevenuc.com. All rights reserved.
# 
# THIS FILE IS PART OF SPEARE CODE EDITOR. WITHOUT THE
# WRITTEN PERMISSION OF THE AUTHOR THIS FILE MAY NOT
# BE USED FOR ANY COMMERCIAL PRODUCT.
# 
# More info: 
#    http://sevenuc.com/en/Speare.html
# Contact:
#    Sevenuc support <info@sevenuc.com>
# Issue report and requests pull:
#    https://github.com/chengdu/Speare


# DbgNub_Main --
#
#	Initializes the nub and invokes the client script.
#
# Arguments:
#	None.
#
# Results:
#	None.

proc DbgNub_Main {} {
    global argc argv0 argv errorCode errorInfo tcl_version

    if {$argc < 4} {
	   error "$argv0 needs cmd line args:  hostname port scriptName data ?args?"
    }

    # Parse command line arguments

    set libDir [file dirname $argv0]
    set host [lindex $argv 0]
    set port [lindex $argv 1]
    set script [lindex $argv 2]
    set data [lindex $argv 3]
    set argList [lrange $argv 4 end]

    # Set up replacement arguments so the client script doesn't see the
    # appLaunch arguments.

    set argv0 $script
    set argv $argList
    set argc [llength $argList]

    # The following code needs to be kept in sync with initdebug.tcl
    
    if {[catch {set socket [socket $host $port]}] != 0} {
    	puts "appLaunch can't create socket"
	    exit 1
    }
    fconfigure $socket -blocking 1 -translation binary

    # On 8.1 and later versions we should ensure the socket is not doing
    # any encoding translations.

    if {$tcl_version >= 8.1} {
	fconfigure $socket -encoding utf-8
    }

    # Attach to the debugger as a local app.

    set msg [list HELLO 1.0 $tcl_version $data]
    puts $socket [string length $msg]
    puts -nonewline $socket $msg
    flush $socket

    # Get the rest of the nub library and evaluate it in the current scope.
    # Note that the nub code assumes there will be a "socket" variable that
    # contains the debugger socket channel.

    if {[gets $socket bytes] == -1} {
      puts "appLaunch read nub failed."
      exit 1
    }
    set msg [read $socket $bytes]
    
    eval [lindex $msg 1]
    return
}

DbgNub_Main
source $argv0

