#! /usr/bin/env python

# The C and C++ debugger for Speare code editor.
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

import os, re, sys
import lldb
import json
import socket
import time
import thread
import threading
import platform
import resource

debugger = None
new_breakpoints = []
registered_breakpoints = set()
# The configure file must be put together with this script
configfile = "speare_lldb.json"

class StepType:
  INSTRUCTION = 1
  INSTRUCTION_OVER = 2
  INTO = 3
  OVER = 4
  OUT = 5

def print_banner():
  print("\n")
  print("   ____")
  print("  / __/ __  ___ ___  ___ ___")
  print("  _\\ \\/ _ \\/ -_) _ `/ __/ -_)")
  print(" /___/ .__/\\__/\\_,_/_/  \\__/")
  print("    /_/")
  print("Speare Debug Server v0.0.4")
  print("(c) http://sevenuc.com \n")

def state_tostring(v):
  states = { lldb.eStateInvalid: "invalid", lldb.eStateUnloaded: "unloaded",
          lldb.eStateConnected: "connected", lldb.eStateAttaching: "attaching",
          lldb.eStateLaunching: "launching", lldb.eStateStopped: "stopped",
          lldb.eStateRunning: "running",  lldb.eStateStepping: "stepping",
          lldb.eStateCrashed: "crashed",  lldb.eStateDetached: "detached",
          lldb.eStateExited: "exited",  lldb.eStateSuspended: "suspended"}
  if v in states.keys(): return states[v]
  else: raise Exception("Unknown StateType enum")

def zip_whitespace(s):
  return re.sub("\s+", " ", s)

def breakpoint_callback(frame, bp_loc, dict):
  # Ensure breakpoint contained in the frame be selected
  global debugger
  frame.thread.process.SetSelectedThread(frame.thread)
  frame.thread.SetSelectedFrame(frame.idx)
  debugger.sendPausedInfo(frame)
  # Returning True means that we actually want to stop at this breakpoint
  return True

def pause_helper(frame):
  line  = str(frame)
  #frame #0: 0x0000000100000edd hello`main at /your/source/path/hello.c:9
  p = line.rfind(" at ")
  if p != -1:
     fileline = line[p+4:]
     p = fileline.rfind(':')
     if p != -1:
       srcfile = fileline[:p]
       return (srcfile, fileline[p+1:])
  return None

def notify_target(event):
  global debugger
  if event.GetType() & lldb.SBTarget.eBroadcastBitModulesLoaded != 0:
    for i in xrange(lldb.SBTarget.GetNumModulesFromEvent(event)):
      mod = lldb.SBTarget.GetModuleAtIndexFromEvent(i, event)
      string = 'Module loaded: %s.' % mod.GetFileSpec().fullpath
      if mod.GetSymbolFileSpec().IsValid():
          string += ' Symbols loaded.'
      debugger.message(string)

def notify_stdio(ev_type):
  global debugger
  if ev_type == lldb.SBProcess.eBroadcastBitSTDOUT:
    read_stream = debugger.process.GetSTDOUT
    isStdout = True
  else:
    read_stream = debugger.process.GetSTDERR
    isStdout = False
  output = read_stream(1024)
  while output:
    # TODO: you can hook here to log big data output or error in file.
    debugger.message(output)
    output = read_stream(1024)

def start_loop_listener():
  global debugger
  listener = lldb.SBListener("loop listener")
  def listen():
    event = lldb.SBEvent()
    while True:
      if listener.WaitForEvent(1, event):
        #if lldb.SBProcess.EventIsProcessEvent(event):
        #  print("process event")
        ev_type = event.GetType()
        if ev_type & (lldb.SBProcess.eBroadcastBitSTDOUT | lldb.SBProcess.eBroadcastBitSTDERR) != 0:
          notify_stdio(ev_type)
      elif lldb.SBTarget.EventIsTargetEvent(event):
        notify_target(event)
  listener_thread = threading.Thread(target=listen)
  listener_thread.daemon = True
  listener_thread.start()
  if not debugger.process.IsValid():
    print('Error: process is invalid when running loop listener.')
    sys.exit(0)
  debugger.process.GetBroadcaster().AddListener(listener, 0xFFFFFF)

def start_breakpoint_listener():
  # Listens for breakpoints event
  global debugger
  listener = lldb.SBListener("breakpoint listener")

  def listen():
    event = lldb.SBEvent()
    try:
      while True:
        #TODO: add an option in configure file, default 120
        if listener.WaitForEvent(120, event):
          if lldb.SBBreakpoint.EventIsBreakpointEvent(event) and \
                  lldb.SBBreakpoint.GetBreakpointEventTypeFromEvent(event) == \
                  lldb.eBreakpointEventTypeAdded:
            breakpoint = lldb.SBBreakpoint.GetBreakpointFromEvent(event)
            global debugger, new_breakpoints
            new_breakpoints.append(breakpoint.id)
            file = None; line = None
            string  = str(breakpoint)
            #SBBreakpoint: id = 2, file = '/your/source/path/hello.c', line = 14
            for item in string.split(', '):
              if item.startswith('file = '):
                file = item[8:-1]
              elif item.startswith('line = '):
                line = item[7:]
              if file and line: break
            if file and line:
              temp = '{"command": "breakpoint", "id": %s, "file": "%s", "line": %s}'
              debugger.message(temp % (str(breakpoint.id), file, line))
    except:
      print("*** Breakpoint listener shutting down")
  listener_thread = threading.Thread(target=listen)
  listener_thread.daemon = True
  listener_thread.start()
  broadcaster = debugger.target.GetBroadcaster()
  broadcaster.AddListener(listener, lldb.SBTarget.eBroadcastBitBreakpointChanged)

class LLDBDebugger(object):
  eventDelayStep = 2
  eventDelayLaunch = 1
  eventDelayContinue = 1

  def __init__(self, sock, lstener, config):
    self.target = None
    self.process = None
    self.load_dependent_modules = True
    self.listener = lstener
    self.socket = sock
    self.queue = []
    self.queue_lock = threading.Lock()
    self.mappathchecked = False
    self.configdict = config
    self.show_disassembly = None
    self.dbg = lldb.SBDebugger.Create()
    self.commandInterpreter = self.dbg.GetCommandInterpreter()
    self.setSettings()

  def handleSettings(self, string):
    self.commandInterpreter.HandleCommand(str(string), lldb.SBCommandReturnObject())

  def setSettings(self):
    self.handleSettings("settings set target.inline-breakpoint-strategy always")
    self.handleSettings("settings set frame-format frame #${frame.index}: " \
                   "${frame.pc}{ ${module.file.basename}{\`${function.name}}}" \
                       "{ at ${line.file.fullpath}:${line.number}}\n")
    self.handleSettings("settings set target.load-script-from-symbol-file false")

  def remapSourcePath(self, srcfile):
    # If the build path of the program WAS NOT
    # the same path for the debug session use the running path instead of the build path
    # debugger.handleSettings("settings set target.source-map /buildbot/path /my/path")
    runnning_dir = self.configdict['remappath']
    if runnning_dir[0] == '#': return # remap path not set
    compile_dir = os.path.dirname(srcfile)
    self.handleSettings("settings set target.source-map %s %s" % (compile_dir, runnning_dir))

  def message(self, data):
    self.socket.sendall(data + '\r\n')

  def addRequest(self, req):
    self.queue_lock.acquire()
    self.queue.append(req)
    self.queue_lock.release()

  def filespecToLocal(self, filespec):
    if not filespec.IsValid():
      return None
    local_path = os.path.normpath(filespec.fullpath)
    if not os.path.isfile(local_path):
      local_path = None
    return local_path

  # Should we show source or disassembly for this frame
  def inDisassembly(self, frame):
    if self.show_disassembly == 'never':
      return False
    elif self.show_disassembly == 'always':
      return True
    else:
      fs = frame.GetLineEntry().GetFileSpec()
      return self.filespecToLocal(fs) is None

  def doStep(self, stepType):
    target = self.dbg.GetSelectedTarget()
    process = target.GetProcess()
    t = process.GetSelectedThread()
    if stepType == StepType.INTO:
      if not self.inDisassembly(t.GetFrameAtIndex(0)):
        t.StepInto()
      else:
        t.StepInstruction(False) # StepType.INSTRUCTION
    elif stepType == StepType.OVER:
      if not self.inDisassembly(t.GetFrameAtIndex(0)):
        t.StepOver()
      else:
        t.StepInstruction(True) # StepType.INSTRUCTION_OVER
    elif stepType == StepType.OUT:
      t.StepOut()
    self.processPendingEvents(self.eventDelayStep, True)

  def doSelect(self, command, args):
    # Like doCommand, but suppress output when "select" is the first argument.
    a = args.split(' ')
    return self.doCommand(command, args, "select" != a[0], True)

  def doProcess(self, args):
    # Handle 'process' command. If 'launch' is requested, use doLaunch() instead
    # of the command interpreter to start the inferior process.
    a = args.split(' ')
    if len(args) == 0 or (len(a) > 0 and a[0] != 'launch'):
      self.doCommand("process", args)
    else:
      self.doLaunch('-s' not in args, "")

  def doAttach(self, process_name):
    error = lldb.SBError()
    self.processListener = lldb.SBListener("process_event_listener")
    self.target = self.dbg.CreateTarget('')
    self.process = self.target.AttachToProcessWithName(self.processListener, process_name, False, error)
    if not error.Success():
      print("Error during attach: " + str(error))
      return
    self.pid = self.process.GetProcessID()
    print("Attached %s (pid=%d)" % (process_name, self.pid))

  def doDetach(self):
    if self.process is not None and self.process.IsValid():
      pid = self.process.GetProcessID()
      state = state_tostring(self.process.GetState())
      self.process.Detach()
      self.processPendingEvents(self.eventDelayLaunch)

  def doLaunch(self, stop_at_entry, args):
    error = lldb.SBError()
    fs = self.target.GetExecutable()
    exe = os.path.join(fs.GetDirectory(), fs.GetFilename())
    if self.process is not None and self.process.IsValid():
      pid = self.process.GetProcessID()
      state = state_tostring(self.process.GetState())
      self.process.Destroy()
    launchInfo = lldb.SBLaunchInfo(args.split(' '))
    self.process = self.target.Launch(launchInfo, error)
    if not error.Success():
      print("Error during launch: " + str(error))
      return
    # launch succeeded, store pid and add some event listeners
    self.pid = self.process.GetProcessID()
    self.processListener = lldb.SBListener("process_event_listener")
    self.process.GetBroadcaster().AddListener(self.processListener, \
        lldb.SBProcess.eBroadcastBitStateChanged)
    start_loop_listener()

    # Limits debugger's memory usage to 4GB to prevent machine crash
    if self.configdict['memorylimits_enable']:
      soft, hard = resource.getrlimit(resource.RLIMIT_AS)
      limits = 4 # 4GB by default
      try: 
        memorylimits = self.configdict['memorylimits']
        if memorylimits.endswith('GB'): memorylimits = memorylimits[:-2]
        limits = int(memorylimits)
      except: pass
      resource.setrlimit(resource.RLIMIT_AS, (limits * 1024**3, hard))

    print("Launched %s (pid=%d)" % (exe, self.pid))
    if not stop_at_entry:
      self.doContinue()
    else:
      self.processPendingEvents(self.eventDelayLaunch)

  def doTarget(self, args):
    target_args = [ "delete", "list", "modules", "select", "stop-hook", "symbols", "variable"]
    a = args.split(' ')
    if len(args) == 0 or (len(a) > 0 and a[0] in target_args):
      print("args=%s" % args)
      self.doCommand("target", str(args))
      return
    elif len(a) > 1 and a[0] == "create":
      exe = a[1]
    elif len(a) == 1 and a[0] not in target_args:
      exe = a[0]
    err = lldb.SBError()
    self.target = self.dbg.CreateTarget(str(exe), None, None, self.load_dependent_modules, err)
    if not self.target:
      print("Error creating target %s. %s" % (str(exe), str(err)))
      return

  def sendPausedInfo(self, frame):
    if frame.IsInlined(): return None
    temp = '{"command": "paused", "file": "%s", "line": %d}'
    filespec = frame.GetLineEntry().GetFileSpec()
    srcfile = filespec.fullpath #os.path.normpath(filespec.fullpath)
    if srcfile:
      line =  frame.GetLineEntry().GetLine()
      self.message(temp % (srcfile, line))
    else:
      fileline = pause_helper(frame)
      if fileline:
        srcfile = fileline[0]
        self.message(temp % (fileline[0], fileline[1]))
    return srcfile

  def doContinue(self):
    #TODO:switch to doCommand("continue", ...) to handle -i ignore-count param.
    if not self.process or not self.process.IsValid():
      print("No process to continue.")
      return
    self.process.Continue()
    self.processPendingEvents(self.eventDelayContinue)
    self.registerBreakpoint()

  def doRefresh(self):
    status = self.processPendingEvents()

  def doExit(self, tracback = False):
    if not self.process: return
    if tracback: # print stack data when crashed
      self.printFrames()
      self.traceAll(True)

    self.dbg.Terminate()
    self.dbg = None
    if self.listener: self.listener.close()
    if self.socket: self.socket.close()
    self.process.Kill()
    self.process = None

  def getCommandResult(self, command, command_args = ""):
    result = lldb.SBCommandReturnObject()
    cmd = "%s %s" % (command, command_args)
    self.commandInterpreter.HandleCommand(cmd, result)
    return (result.Succeeded(), result)

  def doCommand(self, command, command_args, print_on_success = True, goto_file=False):
    (success, result) = self.getCommandResult(command, command_args)
    output = result.GetOutput() if result.Succeeded() else result.GetError()
    if success:
      #if command == "breakpoint": #hook breakpoint call
      #  self.breakpoint_post_handle(result, command_args)
      if (output and len(output) > 0) and print_on_success:
        print(output)
    else:
      print(output + "\n")

  def registerBreakpoint(self):
    res = lldb.SBCommandReturnObject()
    while len(new_breakpoints) > 0:
      res.Clear()
      breakpoint_id = new_breakpoints.pop()
      if breakpoint_id in registered_breakpoints:
        pass #breakpoint with id xxx is already registered. Ignoring.
      else:
        bpid = str(breakpoint_id)
        # make sure to register them with the breakpoint callback
        callback_command = ("breakpoint command add -F breakpoint_callback " + bpid)
        self.commandInterpreter.HandleCommand(callback_command, res)
        if res.Succeeded():
          registered_breakpoints.add(breakpoint_id)
        else:
          print("Error while trying to register breakpoint callback, id = " + bpid)

  def processPendingEvents(self, wait_seconds=0, goto_file=True):
    # Handle any events that are queued from the inferior.
    # Blocks for at most wait_seconds, or if wait_seconds == 0,
    # process only events that are already queued.
    status = None
    num_events_handled = 0

    if self.process is not None:
      event = lldb.SBEvent()
      old_state = self.process.GetState()
      new_state = None
      done = False
      if old_state == lldb.eStateInvalid or old_state == lldb.eStateExited:
        # Early-exit if we are in 'boring' states
        pass
      else:
        while not done and self.processListener is not None:
          if not self.processListener.PeekAtNextEvent(event):
            if wait_seconds > 0:
              # No events on the queue, but we are allowed to wait for wait_seconds
              # for any events to show up.
              self.processListener.WaitForEvent(wait_seconds, event)
              new_state = lldb.SBProcess.GetStateFromEvent(event)
              num_events_handled += 1
            done = not self.processListener.PeekAtNextEvent(event)
          else:
            # An event is on the queue, process it here.
            self.processListener.GetNextEvent(event)
            new_state = lldb.SBProcess.GetStateFromEvent(event)

            # continue if stopped after attaching
            if old_state == lldb.eStateAttaching and new_state == lldb.eStateStopped:
              self.process.Continue()

            # If needed, perform any event-specific behaviour here
            num_events_handled += 1
            
            ev_type = event.GetType()
            if ev_type & (lldb.SBProcess.eBroadcastBitSTDOUT | lldb.SBProcess.eBroadcastBitSTDERR) != 0:
              self.notify_stdio(ev_type)

    if num_events_handled == 0:
      pass
    else:
      if new_state == lldb.eStateCrashed or new_state == lldb.eStateExited:
        print("\n*** process exited.\n")
        self.doExit(new_state == lldb.eStateCrashed)

  def dumpGlobals(self):
    if not self.target: return
    module = self.target.module[self.target.executable.basename]
    if not module: return
    items = list()
    global_names = list()
    for symbol in module.symbols:
      if symbol.type == lldb.eSymbolTypeData:
        global_name = symbol.name
        if global_name not in global_names:
          global_names.append(global_name)
          global_variable_list = module.FindGlobalVariables(self.target, global_name, lldb.UINT32_MAX)
          if global_variable_list:
            for global_variable in global_variable_list:
              items.append('{"%s": {"type": "%s", "value": "%s"}}' % \
                 (global_variable.name, global_variable.type, global_variable.value))
    return items

  """
  def dumpSBValue(self, sbvalue):
    children = []
    for i in range(sbvalue.GetNumChildren()):
      x = sbvalue.GetChildAtIndex(i, lldb.eNoDynamicValues, True)
      if isinstance(x, dict) or isinstance(x, list):
        s = self.dumpSBValue(x)
      else: s = str(x)
      children.append(s)
    return children
  """

  def disasm(self, frame):
    def disassemble_instructions (insts):
      for i in insts:
        print i
    print("~~~~~~~~~")
    print frame # print the frame summary
    function = frame.GetFunction()
    # see if we have debug info (a function)
    if function:
      # print some info for the function
      print function
      # nNow get all instructions for this function and print them
      insts = function.GetInstructions(target)
      disassemble_instructions (insts)
    else:
      # see if we have a symbol in the symbol table for where we stopped
      symbol = frame.GetSymbol();
      if symbol:
        # we do have a symbol, print some info for the symbol
        print symbol
        # now get all instructions for this symbol and print them
        insts = symbol.GetInstructions(target)
        disassemble_instructions (insts)

    registerList = frame.GetRegisters()
    print('Frame registers (size of register set = %d):' % registerList.GetSize())
    for value in registerList:
      print value
      print('%s (number of children = %d):' % (value.GetName(), value.GetNumChildren()))
      for child in value:
        print('Name: ', child.GetName(), ' Value: ', child.GetValue())
    print("~~~~~~~~~")

  def traceAll(self, force = False):
    if not self.dbg: return
    target = self.dbg.GetSelectedTarget()
    process = target.GetProcess()
    thread = process.GetSelectedThread()
    #thread = process.GetThreadAtIndex(0)
    
    #1. Dump image symbol address: 
    if force or self.configdict['dumpimage']:
      (success, result) = self.getCommandResult("image", "list")
      if success: print(result.GetOutput())

    #2. Display registers
    if force or self.configdict['dumpregisters']:
      (success, result) = self.getCommandResult("register", "read")
      if success: print(result.GetOutput())
      frame = thread.GetFrameAtIndex(0)
      if frame: self.disasm(frame)

    #3. Trace back threads
    if not force and not self.configdict['dumpframes']: 
      return
    (success, result) = self.getCommandResult("thread", "backtrace")
    if success: print(result.GetOutput())

    #4. Dump all frames of current thread
    print("Current Frames:")
    for frame in thread:
      if not frame.IsInlined():
        print(frame)
        print("frame.pc = 0x%16.16x" % frame.pc)
        function = frame.GetFunction()
        if function: #'No value'
          print(function)
        vars = frame.get_all_variables()
        for var in vars: print(var)
        args = frame.get_arguments()
        for arg in args: print(arg)
    print("---------------")

  def dumpArgsAndVariables(self, name, args, stack):
    if len(args):
      argstring = []
      for arg in args:
        argstring.append('{"%s": {"type": "%s", "value": "%s"}}' % (arg.name, arg.type, arg.value))
      stack.append('"' + name + '": [\n' + ',\n'.join(argstring) + '],')

  def printFrames(self):
    if not self.dbg: return
    target = self.dbg.GetSelectedTarget()
    process = target.GetProcess()
    thread = process.GetSelectedThread()

    stack = []
    #frame = thread.GetSelectedFrame()
    frame = thread.GetFrameAtIndex(0)
    if frame:
      srcfile = self.sendPausedInfo(frame)
      if not frame.IsInlined():
        # Map source dir
        if srcfile and not self.mappathchecked:
          self.remapSourcePath(srcfile)
          self.mappathchecked = True
        
        #SBFunction: id = 0x0000011c, name = main, type = main
        function = frame.GetFunctionName() #frame.GetFunction()
        if function:
          stack.append('"function": "%s",' % function)
        
        args = frame.get_arguments()
        self.dumpArgsAndVariables("args", args, stack)
        vars = frame.get_all_variables()
        self.dumpArgsAndVariables("vars", vars, stack)

    globalvars = self.dumpGlobals()
    if len(globalvars):
      stack.append('"global": [\n' + ',\n'.join(globalvars) + '],')
    if len(stack):
      self.message('{\n "command": "stack",\n' + '\n'.join(stack) + '\n}')

  def doRequest(self, line):
    if not line or len(line) == 0: 
      return
    try:
      d = json.loads(line)
    except ValueError:
      return
    if not d: return
    cmd = d['command']

    if cmd == 'step':
      args = d['args']
      if args == 'into': stepType = StepType.INTO
      elif args == 'over': stepType = StepType.OVER
      elif args == 'out': stepType = StepType.OUT
      else: return;
      self.doStep(stepType)
      self.printFrames()
      self.traceAll() # TODO: more hook info here.
    elif cmd == 'continue':
      self.doContinue()
    elif cmd == 'breakpoint':
      args = d['args']
      self.doCommand("breakpoint", str(args), True, True)
    elif cmd == 'exit':
      self.doExit()
    elif cmd == 'attach':
      process_name = d['process_name']
      self.doAttach(str(process_name))
    elif cmd == 'dettach':
      self.doDetach()
    else: # other command
      args = d['args'] or ""
      #print("command: %s %s" % (cmd, args))
      self.doCommand(cmd, str(args))

  def handelRequest(self):
    if not self.process: return
    #TODO: handle exit gracefully
    state = self.process.GetState()
    if state in [lldb.eStateInvalid, lldb.eStateCrashed, lldb.eStateExited]:
      self.doExit(state == lldb.eStateCrashed)
      return

    self.queue_lock.acquire()
    if len(self.queue) > 0:
      for req in self.queue:
        self.doRequest(req)
        self.doRefresh()
        self.registerBreakpoint()
        self.queue.remove(req)
    self.queue_lock.release()

#end class

def main():
  port = 6789
  global debugger
  if not platform.system() == 'Darwin':
    print('Invalid operation system.')
    sys.exit(0)
  fp = open(configfile, 'r')
  if not fp:
    print("Can't find %s." % configfile)
    sys.exit(0)
  dict = json.load(fp)
  fp.close()
  
  try: port = int(dict['port'])
  except:
    print('Invalid port number: "%s".' % dict['port'])
    sys.exit(0)
  executable = dict['program']
  if not os.path.exists(executable):
    print('Invalid image: %s' % executable)
    sys.exit(0)
  listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  server_address = ('localhost', port)
  listener.bind(server_address) # Address already in use
  listener.listen(1) # Listen for incoming connection
  print_banner()
  print('Listen on port %d ...' % port)
  print('image: %s' % executable)
  
  connection, client_address = listener.accept()
  #connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
  debugger = LLDBDebugger(connection, listener, dict)
  debugger.handleSettings("settings set target.env-vars DEBUG=1")
  for item in dict['environment']:
    k = item.keys()[0] 
    #TODO: some value should be quoted
    debugger.handleSettings("settings set target.env-vars %s=%s" % (k, item[k]))
  cmdline = 'create %s %s' % (executable, ' '.join(dict['args']))
  debugger.doTarget(cmdline)
  #dSYMFile = dict['dSYM'] # TODO: handle customised symbols dir
  #if os.path.exists(dSYMFile):
  #  debugger.doTarget('symbols %s' % dSYMFile) #invalid command
  p = executable.rfind('/')
  if p != -1: extradir = executable[:p]
  else: extradir = os.path.dirname(os.path.realpath(__file__))
  debugger.handleSettings("settings append target.exec-search-paths %s" % extradir)
  debugger.doCommand('b', "main", True, True) # add breakpoint on main()
  debugger.doLaunch(True, executable)
  start_breakpoint_listener() # hook breakpoint calls

  try:
    while True:
        data = connection.recv(1024) # Receive command from Speare
        if not data: break
        lines = data.decode('utf-8').split('\n')
        for line in lines:
          if len(line) > 0:
            debugger.addRequest(line)
        debugger.handelRequest()
  except socket.error:
    force = False
    if debugger.process:
      state = debugger.process.GetState()
      force = state == lldb.eStateCrashed
    debugger.doExit(force)
  finally:
    if listener: listener.close()
    if connection: connection.close()

if __name__ == "__main__":
  main()


