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

set clientsock -1


# initDbg --
#
#	Initialize the debugger
#	This routine must be called from within the src directory.
#
# Arguments:
#	None.
#
# Results:
#	None.

proc initDbg {} {
    variable libDir

    set blk::blockCounter 0
    dbg::initialize $libDir
    
    #Register events sent from the engine.
    dbg::register stackinfo  {stackinfoHandler}
    dbg::register linebreak  {linebreakHandler}
    dbg::register varbreak   {varbreakHandler}
    dbg::register userbreak  {userbreakHandler}
    dbg::register cmdresult  {cmdresultHandler}
    dbg::register exit       {exitHandler}
    dbg::register error      {errorHandler}
    dbg::register result     {resultHandler}
    dbg::register attach     {attachHandler}
    dbg::register instrument {instrumentHandler}
    # Register the error handler for errors during instrumentation.
    set instrument::errorHandler instrumentErrorHandler
    
    return
}


proc attachHandler { clientData } {
	#dbg::changeState running
	#puts "attachHandler $clientData"
}


#  resultHandler --
#
#	Callback executed when the nub sends a result message.
#	Notify the Eval Window of the result and update the
#	variable windows in case the eval changed the var frames.
#
# Arguments:
#	code		A standard Tcl result code for the evaled cmd.
#	result		A value od the result for the evaled cmd.
#	errCode		A standard Tcl errorCode for the evaled cmd.
#	errInfo		A standard Tcl errorInfo for the evaled cmd.
#
# Results:
#	None.

proc resultHandler {id code result errCode errInfo} {
    puts "resultHandler $result"
    return
}


#  varbreakHandler --
#
#	Update the debugger when a VBP is fired.  Store in the
#	GUI that the break occured because of a VBP so the
#	codeBar will draw the correct icon.
#
# Arguments:
#	var	The var that cused the break.
#	type	The type of operation performed in the var (w,u,r)
#
# Results:
#	None.

proc varbreakHandler {var type} {
    #dbg::stoppedHandler var
    puts "varbreakHandler $var"
    return
}


#  stackinfoHandler --
#
#	Send the variable values to Speare code editor
#   whenever the app stopped.
#
# Arguments:
#	stackdata	The global and local variable values.
#
# Results:
#	None.
proc stackinfoHandler { stackdata } {
	variable clientsock
	if {$stackdata == ""} {
		return
	}

	puts -nonewline $clientsock "\r\n"
	puts -nonewline $clientsock $stackdata
	puts -nonewline $clientsock "\r\n"
	return
}


#  linebreakHandler --
#
#	Update the debugger when a LBP is fired.  Store in the
#	GUI that the break occured because of a LBP so the
#	codeBar will draw the correct icon.
#
# Arguments:
#	None.
#
# Results:
#	None.

proc linebreakHandler {args} {
	variable clientsock

    set file [lindex $args 0]
    set line [lindex $args 1]
	
	if {$file == "" || $line == ""} {
		return
	}
	
    puts $clientsock "\r\n{\"command\": \"paused\", \"file\": \"$file\", \"line\": $line}"

    return
}


#  cmdresultHandler --
#
#	Update the display when the debugger stops at the end of a
#	command with the result.
#
# Arguments:
#	None.
#
# Results:
#	None.

proc cmdresultHandler {args} {
    #dbg::stoppedHandler cmdresult
    #puts "cmdresultHandler $args"
    return
}

#  userbreakHandler --
#
#	This handles a users call to "debugger_break" it is
#	handled just like a line breakpoint - except that we
#	also post a dialog box that denotes this type of break.
#
# Arguments:
#	None.
#
# Results:
#	None.

proc userbreakHandler {args} {
    eval linebreakHandler $args

    set str [lindex $args 0]
    if {$str == ""} {
	  puts "Script called debugger_break"
    } else {
	  puts $str
    }

    return
}


#  stoppedHandler --
#
#	Update the debugger when the app stops.
#
# Arguments:
#	breakType	Store the reason for the break (result, line, var...)
#
# Results:
#	None.

proc stoppedHandler {breakType} {
    #dbg::changeState stopped
    #dbg::Log timing {dbg::stoppedHandler $breakType}
    
    return
}


#  exitHandler --
#
#	Callback executed when the nub sends an exit message.
#	Re-initialize the state of the Debugger and clear all
#	sub-windows.
#
# Arguments:
#	None.
#
# Results:
#	None.

proc exitHandler {} {
    variable clientsock
   
    #dbg::changeState dead
    #puts "end of script..."
    puts $clientsock "\r\nexit\r\n"
    exit 1
    
    return
}

#  errorHandler --
#
#	Show the error message in the error window.
#
# Arguments:
#	None.
#
# Results:
#	None.

proc errorHandler {errMsg errStk errCode uncaught} {
    variable uncaughtError
    
    stoppedHandler error
    #set uncaughtError $uncaught
    set level [dbg::getLevel]
    set pc [dbg::getPC]
    puts $level $pc $errMsg $errStk $errCode
    exit 1 

    return
}


proc instrumentHandler {status block} {
	#puts "instrumentHandler $status"
    if {$status == "end"} {
		dbg::SetState "stopped"
	}
}


proc instrumentErrorHandler {} {
	puts "instrument error"
	exit 1
}


# quitDbg --
#
#	Stop debugging the application and unregister the eventProcs	
#
# Arguments:
#	None.
#
# Results:
#	None.

proc quitDbg {} {
    catch {dbg::quit; after 100}
    
    exit 1
    return
}


# launchDbg --
#
#	Start the both the debugger and the application to debug.
#	Set up initial communication.
#
# Arguments:
#	app		Interpreter in which to run scriptFile.
#	port		Number of port on which to communicate.
#	scriptFile	File to debug.
#	verbose		Boolean that decides whether to log activity.
#	startDir	the directory where the client program should be
#			started.

proc launchDbg {app startDir scriptFile} {
    dbg::setServerPort random

    initDbg

	#set result [uplevel 1 $scriptFile]
	
	# Start the application and wait for the "attach" event.
	dbg::start $app $startDir $scriptFile {} REMOTE
	waitForApp

    return
}


# waitForApp --
#
#	Call this proc after dbg::step, dbg::run, dbg::evaluate. Returns
#	when the global variable Dbg_AppStopped is set by the breakProc
#	or exitProc procedures.
#
# Arguments:
#	None.
#
# Results:
#	None.

proc waitForApp {} {
    global Dbg_AppStopped
    
    vwait Dbg_AppStopped
    set ret $Dbg_AppStopped
    set Dbg_AppStopped "run"
    return $ret
}


# handleBreakpoint --
#
#	Call this proc when debugger received a breakpoint command.
#
# Arguments:
#	sub	The subcommand.
#	filepath	The path of the script the breakpoint located in
#	line	Line number of the breakpoint
#
# Results:
#	None.
# breakpoint + [add|remove|enable|disnable] + file + line
proc handleBreakpoint {sub filepath line} {
	set block [blk::makeBlock $filepath]
    set loc [loc::makeLocation $block $line]
	if { $sub == "add"} {
        dbg::addLineBreakpoint $loc
        return
	}
	set bps [dbg::getLineBreakpoints $loc]
	foreach bp $bps {
		if { $sub == "remove"} {
		    dbg::removeBreakpoint $bp
		}elseif { $sub == "enable"} {
			dbg::enableBreakpoint $bp
		}elseif { $sub == "disable"} {
			dbg::disableBreakpoint $bp
		}	
	}
	return
}


# doService --
#
#	Call this proc when debugger received a command 
#	from Speare code editor
#
# Arguments:
#	sock	The socket connection between debugger and Speare.
#	msg	The command sent from Speare, separated by tab
#
# Results:
#	None.
proc doService {sock msg} {
	variable tclsh 
	variable startDir
    
    # init + filepath
    # step + [into|out|over|result]
    # run
    # breakpoint + [add|remove|enable|disnable] + file + line
    # evaluate + expression
    # quit
    
    #puts "received: $msg"
 
    set lines [split $msg "\t"]
    if { [llength $lines ] < 2 } {
    	switch -- $msg {
	    	run {
	    	   dbg::run
	    	}
	    	quit {
	    	   dbg::quit
	        }
    	}
    	return
    }
    
    
    set command [lindex $lines 0]
    #puts "command: $command"
    switch -- $command {
    	init {
    		set scriptFile [lindex $lines 1]
	    	launchDbg $tclsh $startDir $scriptFile
    	}
    	step {
    		set sub [lindex $lines 1]
    		switch -- $sub {
    			into { dbg::step }
    			out { dbg::step out }
    			over { dbg::step over }
    			result { dbg::step cmdresult }
    			any { dbg::step any }
    		}
    	}
    	breakpoint {
    		if {[llength $lines] != 4} {
    		   return;
    	    }
	    	set sub [lindex $lines 1]
	    	set file [lindex $lines 2]
	    	set line [lindex $lines 3]
	    	handleBreakpoint $sub $file $line
    	}
    	evaluate {
    		set expression [lindex $lines 1]
	    	dbg::evaluate  1 $expression
    	}
    	interrupt {
    	   dbg::interrupt
    	}
    }
    
    return
}

# doService --
#
#	Handles the command sent
#	from Speare code editor
#
# Arguments:
#	sock	The socket connection between debugger and Speare.
#
# Results:
#	None. 
proc  svcHandler {sock} {
  set l [gets $sock]    ;# get the client packet
  if {[eof $sock]} {    ;# client gone or finished
     puts "*** client socket closed."
     close $sock;# release the servers client channel
     exit 0
  } else {
    doService $sock $l
  }
  return
}


# Accept-Connection handler for Speare Debug Server. 
# called When client makes a connection to the debugger
# Its passed the channel we're to communicate with the client on, 
# The address of the client and the port we're using
#
# Setup a handler for (incoming) communication on the client channel
proc accept {sock addr port} {
  variable clientsock
  set clientsock $sock

  # Setup handler for future communication on client socket
  fileevent $sock readable [list svcHandler $sock]
  fconfigure $sock -translation binary -encoding utf-8
  
  # Note we've accepted a connection from Speare code editor
  puts "Accept from [fconfigure $sock -peername]"

  # Read client input in lines, disable blocking I/O
  fconfigure $sock -buffering line -blocking 0

  # Send Acceptance string to client
  puts $sock "$addr:$port, You are connected to the Tcl debug server."
  puts $sock "It is now [exec date]"

  # log the connection
  puts "Accepted connection from $addr at [exec date]."
  
  return
}

# setup search path
lappend ::auto_path [file dirname [file normalize [info script]]]

# load debugger sources
foreach file {
    dbg.tcl block.tcl break.tcl instrument.tcl location.tcl util.tcl
} {
    source $file
}

puts "debug server listen on: $svcPort"

# Create a server socket on port $svcPort. 
# Call proc accept when a client attempts a connection.

socket -server accept $svcPort
vwait events; # handle events till variable events is set



