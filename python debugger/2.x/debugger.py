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

import sys
import linecache
import cmd
import bdb

import os
import re
import pprint
import traceback
import json
from repr import Repr

__version__ = '0.0.2'

# Create a custom safe Repr instance and increase its maxstring.
# The default of 30 truncates error messages too easily.
_repr = Repr()
_repr.maxstring = 200
_saferepr = _repr.repr

class Restart(Exception):
    """Causes debugger to be restarted for the debugged python program."""
    pass

__all__ = ["run", "pm", "Debugger", "runeval", "runctx", "runcall", "set_trace",
           "post_mortem", "help"]

def find_function(funcname, filename):
    cre = re.compile(r'def\s+%s\s*[(]' % re.escape(funcname))
    try:
        fp = open(filename)
    except IOError:
        return None
    # consumer of this info expects the first line to be 1
    lineno = 1
    answer = None
    while 1:
        line = fp.readline()
        if line == '':
            break
        if cre.match(line):
            answer = funcname, filename, lineno
            break
        lineno = lineno + 1
    fp.close()
    return answer

# Interaction prompt line will separate file and call info from code
# text using value of line_prefix string.  A newline and arrow may
# be to your liking.  You can set it once pdb is imported using the
# command "pdb.line_prefix = '\n% '".
# line_prefix = ': '    # Use this to get the old situation back
line_prefix = '\n-> '   # Probably a better default

class Debugger(bdb.Bdb, cmd.Cmd):

    def __init__(self, completekey='tab', stdin=None, stdout=None, skip=None):
        bdb.Bdb.__init__(self, skip=skip)
        cmd.Cmd.__init__(self, completekey, stdin, stdout)
        if stdout:
            self.use_rawinput = 0
        self.prompt = ''
        self.aliases = {}
        self.mainpyfile = ''
        self._wait_for_mainpyfile = 0
        self.sources = []
        # Try to load readline if it exists
        try:
            import readline
        except ImportError:
            pass

        # Read $HOME/.pdbrc and ./.pdbrc
        self.rcLines = []
        if 'HOME' in os.environ:
            envHome = os.environ['HOME']
            try:
                rcFile = open(os.path.join(envHome, ".pdbrc"))
            except IOError:
                pass
            else:
                for line in rcFile.readlines():
                    self.rcLines.append(line)
                rcFile.close()
        try:
            rcFile = open(".pdbrc")
        except IOError:
            pass
        else:
            for line in rcFile.readlines():
                self.rcLines.append(line)
            rcFile.close()

        self.commands = {} # associates a command list to breakpoint numbers
        self.commands_doprompt = {} # for each bp num, tells if the prompt
                                    # must be disp. after execing the cmd list
        self.commands_silent = {} # for each bp num, tells if the stack trace
                                  # must be disp. after execing the cmd list
        self.commands_defining = False # True while in the process of defining
                                       # a command list
        self.commands_bnum = None # The breakpoint number for which we are
                                  # defining a list

    def reset(self):
        bdb.Bdb.reset(self)
        self.forget()

    def forget(self):
        self.lineno = None
        self.stack = []
        self.curindex = 0
        self.curframe = None

    def setup(self, f, t):
        self.forget()
        self.stack, self.curindex = self.get_stack(f, t)
        self.curframe = self.stack[self.curindex][0]
        # The f_locals dictionary is updated from the actual frame
        # locals whenever the .f_locals accessor is called, so we
        # cache it here to ensure that modifications are not overwritten.
        self.curframe_locals = self.curframe.f_locals
        self.execRcLines()

    # Can be executed earlier than 'setup' if desired
    def execRcLines(self):
        if self.rcLines:
            # Make local copy because of recursion
            rcLines = self.rcLines
            # executed only once
            self.rcLines = []
            for line in rcLines:
                line = line[:-1]
                if len(line) > 0 and line[0] != '#':
                    self.onecmd(line)

    # Override Bdb methods
    def shouldtrace(self, frame):
        result = False
        filename = self.canonic(frame.f_code.co_filename)
        if not filename in self.excluded_files:
            dir_path = os.path.dirname(filename)
            for folder in self.basedirs:
                if dir_path.startswith(folder):
                    result = True
                    break
        return result

    def user_call(self, frame, argument_list):
        """This method is called when there is the remote possibility
        that we ever need to stop in this function."""
        if self._wait_for_mainpyfile: return
        show = self.shouldtrace(frame)
        filename = self.canonic(frame.f_code.co_filename)
        if show and not filename in self.sources: 
            self.sources.append(filename)
            temp = '{ "command": "Paused", "file": "%s", "line": %d }'
            self.message(temp % (filename, frame.f_lineno))
        if self.stop_here(frame):
            #print >>self.stdout, '--Call--'
            self.interaction(frame, None)

    def user_line(self, frame):
        """This function is called when we stop or break at this line."""
        if self._wait_for_mainpyfile:
            if (self.mainpyfile != self.canonic(frame.f_code.co_filename)
                or frame.f_lineno<= 0):
                return
            self._wait_for_mainpyfile = 0
        filename = self.canonic(frame.f_code.co_filename)
        if not filename in self.excluded_files:
            temp = '{ "command": "Paused", "file": "%s", "line": %d }'
            self.message(temp % (filename, frame.f_lineno))
        if self.bp_commands(frame):
            self.interaction(frame, None)

    def bp_commands(self,frame):
        """Call every command that was set for the current active breakpoint
        (if there is one).

        Returns True if the normal interaction function must be called,
        False otherwise."""
        # self.currentbp is set in bdb in Bdb.break_here if a breakpoint was hit
        if getattr(self, "currentbp", False) and \
               self.currentbp in self.commands:
            currentbp = self.currentbp
            self.currentbp = 0
            lastcmd_back = self.lastcmd
            self.setup(frame, None)
            for line in self.commands[currentbp]:
                self.onecmd(line)
            self.lastcmd = lastcmd_back
            if not self.commands_silent[currentbp]:
                self.print_stack_entry(self.stack[self.curindex])
            if self.commands_doprompt[currentbp]:
                self.cmdloop()
            self.forget()
            return
        return 1

    def user_return(self, frame, return_value):
        """This function is called when a return trap is set here."""
        if self._wait_for_mainpyfile:
            return
        frame.f_locals['__return__'] = return_value
        #print >>self.stdout, '--Return--'
        self.interaction(frame, None)

    def user_exception(self, frame, exc_info):
        """This function is called if an exception occurs,
        but only if we are to stop at or just below this level."""
        if self._wait_for_mainpyfile:
            return
        exc_type, exc_value, exc_traceback = exc_info
        frame.f_locals['__exception__'] = exc_type, exc_value
        if type(exc_type) == type(''): exc_type_name = exc_type
        else: exc_type_name = exc_type.__name__
        self.message(exc_type_name + ':', _saferepr(exc_value))
        self.interaction(frame, exc_traceback)
        self.onexception()

    # General interaction function

    def interaction(self, frame, traceback):
        self.setup(frame, traceback)
        #self.print_stack_entry(self.stack[self.curindex])
        self.print_stack_variables()
        self.cmdloop()
        self.forget()

    def displayhook(self, obj):
        """Custom displayhook for the exec in default(), which prevents
        assignment of the _ variable in the builtins.
        """
        # reproduce the behavior of the standard displayhook, not printing None
        if obj is not None:
            self.message(repr(obj))

    def default(self, line):
        if line[:1] == '!': line = line[1:]
        locals = self.curframe_locals
        globals = self.curframe.f_globals
        try:
            code = compile(line + '\n', '<stdin>', 'single')
            save_stdout = sys.stdout
            save_stdin = sys.stdin
            save_displayhook = sys.displayhook
            try:
                sys.stdin = self.stdin
                sys.stdout = self.stdout
                sys.displayhook = self.displayhook
                exec(code) in globals, locals
            finally:
                sys.stdout = save_stdout
                sys.stdin = save_stdin
                sys.displayhook = save_displayhook
        except:
            t, v = sys.exc_info()[:2]
            if type(t) == type(''):
                exc_type_name = t
            else: exc_type_name = t.__name__
            self.message('***', exc_type_name + ':', v)

    def precmd(self, line):
        """Handle alias expansion and ';;' separator."""
        if not line.strip():
            return line
        args = line.split()
        while args[0] in self.aliases:
            line = self.aliases[args[0]]
            ii = 1
            for tmpArg in args[1:]:
                line = line.replace("%" + str(ii),
                                      tmpArg)
                ii = ii + 1
            line = line.replace("%*", ' '.join(args[1:]))
            args = line.split()
        # split into ';;' separated commands
        # unless it's an alias command
        if args[0] != 'alias':
            marker = line.find(';;')
            if marker >= 0:
                # queue up everything after marker
                next = line[marker+2:].lstrip()
                self.cmdqueue.append(next)
                line = line[:marker].rstrip()
        return line

    def onecmd(self, line):
        """Interpret the argument as though it had been typed in response
        to the prompt.

        Checks whether this line is typed at the normal prompt or in
        a breakpoint command list definition.
        """
        if not self.commands_defining:
            return cmd.Cmd.onecmd(self, line)
        else:
            return self.handle_command_def(line)

    def handle_command_def(self,line):
        """Handles one command line during command list definition."""
        cmd, arg, line = self.parseline(line)
        if not cmd:
            return
        if cmd == 'silent':
            self.commands_silent[self.commands_bnum] = True
            return # continue to handle other cmd def in the cmd list
        elif cmd == 'end':
            self.cmdqueue = []
            return 1 # end of cmd list
        cmdlist = self.commands[self.commands_bnum]
        if arg:
            cmdlist.append(cmd+' '+arg)
        else:
            cmdlist.append(cmd)
        # Determine if we must stop
        try:
            func = getattr(self, 'do_' + cmd)
        except AttributeError:
            func = self.default
        # one of the resuming commands
        if func.func_name in self.commands_resuming:
            self.commands_doprompt[self.commands_bnum] = False
            self.cmdqueue = []
            return 1
        return

    def message(self, *args):
        print >>self.stdout, " ".join(map(str, args)) + "\r\n"

    # Command definitions, called by cmdloop()
    # The argument is the remaining string on the command line
    # Return true to exit from the command loop

    def do_commands(self, arg):
        """Defines a list of commands associated to a breakpoint.

        Those commands will be executed whenever the breakpoint causes
        the program to stop execution."""
        if not arg:
            bnum = len(bdb.Breakpoint.bpbynumber)-1
        else:
            try:
                bnum = int(arg)
            except:
                self.message("Usage : commands [bnum]\n ..." \
                                     "\n        end")
                return
        self.commands_bnum = bnum
        self.commands[bnum] = []
        self.commands_doprompt[bnum] = True
        self.commands_silent[bnum] = False
        prompt_back = self.prompt
        self.prompt = '(com) '
        self.commands_defining = True
        try:
            self.cmdloop()
        finally:
            self.commands_defining = False
            self.prompt = prompt_back

    def do_break(self, arg, temporary = 0):
        # break [ ([filename:]lineno | function) [, "condition"] ]
        if not arg:
            if self.breaks:  # There's at least one
                self.message("Num Type Disp Enb Where")
                for bp in bdb.Breakpoint.bpbynumber:
                    if bp:
                        bp.bpprint(self.stdout)
            return
        # parse arguments; comma has lowest precedence
        # and cannot occur in filename
        filename = None
        lineno = None
        cond = None
        comma = arg.find(',')
        if comma > 0:
            # parse stuff after comma: "condition"
            cond = arg[comma+1:].lstrip()
            arg = arg[:comma].rstrip()
        # parse stuff before comma: [filename:]lineno | function
        colon = arg.rfind(':')
        funcname = None
        if colon >= 0:
            filename = arg[:colon].rstrip()
            f = self.lookupmodule(filename)
            if not f:
                self.message('*** ', repr(filename), 'not found from sys.path')
                return
            else:
                filename = f
            arg = arg[colon+1:].lstrip()
            try:
                lineno = int(arg)
            except ValueError as e:
                self.message('*** Bad lineno:', e)
                return
        else:
            # no colon; can be lineno or function
            try:
                lineno = int(arg)
            except ValueError:
                try:
                    func = eval(arg,
                                self.curframe.f_globals,
                                self.curframe_locals)
                except:
                    func = arg
                try:
                    if hasattr(func, 'im_func'):
                        func = func.im_func
                    code = func.func_code
                    #use co_name to identify the bkpt (function names
                    #could be aliased, but co_name is invariant)
                    funcname = code.co_name
                    lineno = code.co_firstlineno
                    filename = code.co_filename
                except:
                    # last thing to try
                    (ok, filename, ln) = self.lineinfo(arg)
                    if not ok:
                        self.message('*** The specified object', \
                         repr(arg), \
                         'is not a function' \
                         'or was not found along sys.path.')
                        return
                    funcname = ok # ok contains a function name
                    lineno = int(ln)
        if not filename:
            filename = self.defaultFile()
        # Check for reasonable breakpoint
        line = self.checkline(filename, lineno)
        if line:
            # now set the break point
            err = self.set_break(filename, line, temporary, cond, funcname)
            if err: self.message('***', err)
            else:
                bp = self.get_breaks(filename, line)[-1]
                #print >>self.stdout, "Breakpoint %d at %s:%d" % (bp.number, bp.file, bp.line)
                temp = '{ "command": "Breakpoint", "id": %d, "file": "%s", "line": %d }'
                self.message(temp % (bp.number, bp.file, bp.line))

    # To be overridden in derived debuggers
    def defaultFile(self):
        """Produce a reasonable default."""
        filename = self.curframe.f_code.co_filename
        if filename == '<string>' and self.mainpyfile:
            filename = self.mainpyfile
        return filename

    do_b = do_break

    def do_tbreak(self, arg):
        self.do_break(arg, 1)

    def lineinfo(self, identifier):
        failed = (None, None, None)
        # Input is identifier, may be in single quotes
        idstring = identifier.split("'")
        if len(idstring) == 1:
            # not in single quotes
            id = idstring[0].strip()
        elif len(idstring) == 3:
            # quoted
            id = idstring[1].strip()
        else:
            return failed
        if id == '': return failed
        parts = id.split('.')
        # Protection for derived debuggers
        if parts[0] == 'self':
            del parts[0]
            if len(parts) == 0:
                return failed
        # Best first guess at file to look at
        fname = self.defaultFile()
        if len(parts) == 1:
            item = parts[0]
        else:
            # More than one part.
            # First is module, second is method/class
            f = self.lookupmodule(parts[0])
            if f:
                fname = f
            item = parts[1]
        answer = find_function(item, fname)
        return answer or failed

    def checkline(self, filename, lineno):
        """Check whether specified line seems to be executable.

        Return `lineno` if it is, 0 if not (e.g. a docstring, comment, blank
        line or EOF). Warning: testing is not comprehensive.
        """
        # this method should be callable before starting debugging, so default
        # to "no globals" if there is no current frame
        globs = self.curframe.f_globals if hasattr(self, 'curframe') else None
        line = linecache.getline(filename, lineno, globs)
        if not line:
            self.message('End of file')
            return 0
        line = line.strip()
        # Don't allow setting breakpoint at a blank line
        if (not line or (line[0] == '#') or
             (line[:3] == '"""') or line[:3] == "'''"):
            self.message('*** Blank or comment')
            return 0
        return lineno

    def do_enable(self, arg):
        args = arg.split()
        for i in args:
            try:
                i = int(i)
            except ValueError:
                self.message('Breakpoint index %r is not a number' % i)
                continue

            if not (0 <= i < len(bdb.Breakpoint.bpbynumber)):
                self.message('No breakpoint numbered', i)
                continue

            bp = bdb.Breakpoint.bpbynumber[i]
            if bp:
                bp.enable()

    def do_disable(self, arg):
        args = arg.split()
        for i in args:
            try:
                i = int(i)
            except ValueError:
                self.message('Breakpoint index %r is not a number' % i)
                continue

            if not (0 <= i < len(bdb.Breakpoint.bpbynumber)):
                self.message('No breakpoint numbered', i)
                continue

            bp = bdb.Breakpoint.bpbynumber[i]
            if bp:
                bp.disable()

    def do_condition(self, arg):
        # arg is breakpoint number and condition
        args = arg.split(' ', 1)
        try:
            bpnum = int(args[0].strip())
        except ValueError:
            # something went wrong
            self.message('Breakpoint index %r is not a number' % args[0])
            return
        try:
            cond = args[1]
        except:
            cond = None
        try:
            bp = bdb.Breakpoint.bpbynumber[bpnum]
        except IndexError:
            self.message('Breakpoint index %r is not valid' % args[0])
            return
        if bp:
            bp.cond = cond
            if not cond:
                self.message('Breakpoint', bpnum, 'is now unconditional.')

    def do_ignore(self,arg):
        """arg is bp number followed by ignore count."""
        args = arg.split()
        try:
            bpnum = int(args[0].strip())
        except ValueError:
            # something went wrong
            self.message('Breakpoint index %r is not a number' % args[0])
            return
        try:
            count = int(args[1].strip())
        except:
            count = 0
        try:
            bp = bdb.Breakpoint.bpbynumber[bpnum]
        except IndexError:
            self.message('Breakpoint index %r is not valid' % args[0])
            return
        if bp:
            bp.ignore = count
            if count > 0:
                reply = 'Will ignore next '
                if count > 1:
                    reply = reply + '%d crossings' % count
                else:
                    reply = reply + '1 crossing'
                self.message(reply + ' of breakpoint %d.' % bpnum)
            else:
                self.message('Will stop next time breakpoint', bpnum, 'is reached.')

    def do_clear(self, arg):
        if not arg:
            self.clear_all_breaks()
            return
        if ':' in arg:
            # Make sure it works for "clear C:\foo\bar.py:12"
            i = arg.rfind(':')
            filename = arg[:i]
            arg = arg[i+1:]
            try:
                lineno = int(arg)
            except ValueError:
                err = "Invalid line number (%s)" % arg
            else:
                err = self.clear_break(filename, lineno)
            if err: self.message('***', err)
            return
        numberlist = arg.split()
        for i in numberlist:
            try:
                i = int(i)
            except ValueError:
                self.message('Breakpoint index %r is not a number' % i)
                continue

            if not (0 <= i < len(bdb.Breakpoint.bpbynumber)):
                self.message('No breakpoint numbered', i)
                continue
            err = self.clear_bpbynumber(i)
            if err:
                self.message('***', err)
            else:
                self.message('Deleted breakpoint', i)
    
    do_cl = do_clear # 'c' is already an abbreviation for 'continue'

    def do_where(self, arg):
        self.print_stack_trace()
    do_w = do_where
    do_bt = do_where

    def do_up(self, arg):
        if self.curindex == 0:
            self.message('*** Oldest frame')
        else:
            self.curindex = self.curindex - 1
            self.curframe = self.stack[self.curindex][0]
            self.curframe_locals = self.curframe.f_locals
            self.print_stack_entry(self.stack[self.curindex])
            self.lineno = None
    do_u = do_up

    def do_down(self, arg):
        if self.curindex + 1 == len(self.stack):
            self.message('*** Newest frame')
        else:
            self.curindex = self.curindex + 1
            self.curframe = self.stack[self.curindex][0]
            self.curframe_locals = self.curframe.f_locals
            self.print_stack_entry(self.stack[self.curindex])
            self.lineno = None
    do_d = do_down

    def do_until(self, arg):
        self.set_until(self.curframe)
        return 1
    do_unt = do_until

    def do_step(self, arg):
        frame = self.stack[self.curindex][0]
        if self.shouldtrace(frame):
            filename = self.canonic(frame.f_code.co_filename)
            if not filename in self.sources: 
                self.sources.append(filename)
                self.set_trace(frame)
        self.set_step()
        return 1
    do_s = do_step

    def do_next(self, arg):
        self.set_next(self.curframe)
        return 1
    do_n = do_next

    def do_run(self, arg):
        if arg:
            import shlex
            argv0 = sys.argv[0:1]
            sys.argv = shlex.split(arg)
            sys.argv[:0] = argv0
        raise Restart

    do_restart = do_run

    def do_return(self, arg):
        self.set_return(self.curframe)
        return 1
    do_r = do_return

    def do_continue(self, arg):
        self.set_continue()
        return 1
    do_c = do_cont = do_continue

    def do_jump(self, arg):
        if self.curindex + 1 != len(self.stack):
            self.message("*** You can only jump within the bottom frame")
            return
        try:
            arg = int(arg)
        except ValueError:
            self.message("*** The 'jump' command requires a line number.")
        else:
            try:
                # Do the jump, fix up our copy of the stack, and display the
                # new position
                self.curframe.f_lineno = arg
                self.stack[self.curindex] = self.stack[self.curindex][0], arg
                self.print_stack_entry(self.stack[self.curindex])
            except ValueError, e:
                self.message('*** Jump failed:', e)
    do_j = do_jump

    def do_debug(self, arg):
        sys.settrace(None)
        globals = self.curframe.f_globals
        locals = self.curframe_locals
        p = Debugger(self.completekey, self.stdin, self.stdout)
        p.prompt = "(%s) " % self.prompt.strip()
        self.message("ENTERING RECURSIVE DEBUGGER")
        sys.call_tracing(p.run, (arg, globals, locals))
        self.message("LEAVING RECURSIVE DEBUGGER")
        sys.settrace(self.trace_dispatch)
        self.lastcmd = p.lastcmd

    def do_quit(self, arg):
        self._user_requested_quit = 1
        self.set_quit()
        return 1

    do_q = do_quit
    do_exit = do_quit

    def do_EOF(self, arg):
        print >>self.stdout
        self._user_requested_quit = 1
        self.set_quit()
        return 1

    def do_args(self, arg):
        co = self.curframe.f_code
        dict = self.curframe_locals
        n = co.co_argcount
        if co.co_flags & 4: n = n+1
        if co.co_flags & 8: n = n+1
        for i in range(n):
            name = co.co_varnames[i]
            if name in dict: val = dict[name]
            else: val = "*** undefined ***"
            self.message('%s = %s' % (name, val))
    do_a = do_args

    def do_retval(self, arg):
        if '__return__' in self.curframe_locals:
            self.message(self.curframe_locals['__return__'])
        else:
            self.message('*** Not yet returned!')
    do_rv = do_retval

    def do_basedir(self, arg):
        if os.path.isdir(arg) and not arg in self.basedirs:
            self.basedirs.append(arg)
            sys.path.insert(0, arg)
            self.message('%s added in sys.path.' % arg)
        else: self.message('*** %s is not a directory or already added.' % arg)

    def do_load(self, arg):
        pdir = os.path.dirname(arg)
        if not sys.path[0] == pdir: sys.path.insert(0, pdir)
        try:
            self.message('%s will be loaded.' % arg)
            self._runscript(arg)
        except:
            t, v = sys.exc_info()[:2]
            if isinstance(t, str):
                exc_type_name = t
            else: exc_type_name = t.__name__
            self.message('***', exc_type_name + ':', repr(v))
            raise

    def do_eval(self, arg):
        #retval = self.runeval(expr)
        #if not isinstance(arg, types.CodeType): arg = arg+'\n'
        #try: retval = eval(arg, globals, locals)
        #except: 
        #    t, v = sys.exc_info()[:2]
        #    if isinstance(t, str): exc_type_name = t
        #    else: exc_type_name = t.__name__
        #    print('*** %s: %s %s' % (arg, exc_type_name + ':', repr(v)))
        #if not retval: return
        #temp = '{ "command": "Expression", "eval": "%s", "result": "%s" }'
        #print >>self.stdout, temp % (arg, str(retval))
        pass

    def _getval(self, arg):
        try:
            return eval(arg, self.curframe.f_globals,
                        self.curframe_locals)
        except:
            t, v = sys.exc_info()[:2]
            if isinstance(t, str):
                exc_type_name = t
            else: exc_type_name = t.__name__
            self.message('***', exc_type_name + ':', repr(v))
            raise

    def do_p(self, arg):
        try:
            self.message(repr(self._getval(arg)))
        except:
            pass

    def do_pp(self, arg):
        try:
            pprint.pprint(self._getval(arg), self.stdout)
        except:
            pass

    def do_whatis(self, arg):
        try:
            value = eval(arg, self.curframe.f_globals,
                            self.curframe_locals)
        except:
            t, v = sys.exc_info()[:2]
            if type(t) == type(''):
                exc_type_name = t
            else: exc_type_name = t.__name__
            self.message('***', exc_type_name + ':', repr(v))
            return
        code = None
        # Is it a function?
        try: code = value.func_code
        except: pass
        if code:
            self.message('Function', code.co_name)
            return
        # Is it an instance method?
        try: code = value.im_func.func_code
        except: pass
        if code:
            self.message('Method', code.co_name)
            return
        # None of the above...
        self.message(type(value))

    def do_alias(self, arg):
        args = arg.split()
        if len(args) == 0:
            keys = self.aliases.keys()
            keys.sort()
            for alias in keys:
                self.message("%s = %s" % (alias, self.aliases[alias]))
            return
        if args[0] in self.aliases and len(args) == 1:
            self.message("%s = %s" % (args[0], self.aliases[args[0]]))
        else:
            self.aliases[args[0]] = ' '.join(args[1:])

    def do_unalias(self, arg):
        args = arg.split()
        if len(args) == 0: return
        if args[0] in self.aliases:
            del self.aliases[args[0]]

    def onexception(self):
        pass
    
    #list of all the commands making the program resume execution.
    commands_resuming = ['do_continue', 'do_step', 'do_next', 'do_return',
                         'do_quit', 'do_jump']

    # Print a traceback starting at the top stack frame.
    # The most recently entered frame is printed last;
    # this is different from dbx and gdb, but consistent with
    # the Python interpreter's stack trace.
    # It is also consistent with the up/down commands (which are
    # compatible with dbx and gdb: up moves towards 'main()'
    # and down moves towards the most recent stack frame).

    def print_stack_trace(self):
        try:
            for frame_lineno in self.stack:
                self.print_stack_entry(frame_lineno)
        except KeyboardInterrupt:
            pass

    def print_stack_entry(self, frame_lineno, prompt_prefix=line_prefix):
        frame, lineno = frame_lineno
        filename = self.canonic(frame.f_code.co_filename)
        if filename in self.excluded_files: return
        if frame is self.curframe: print('>')
        else: print(' ')
        print(self.format_stack_entry(frame_lineno, prompt_prefix))

    def viewstack(self, data):
        """
        Dumps data related to a referenced event to the socket.
        """
        try:
            dumped = json.dumps({"command": "stack", "data": data}).encode("utf-8")
            self.message(dumped)
        except OSError as e:
            pass
        except AttributeError as e:
            pass

    def print_stack_variables(self):
        """
        Dump the current stack.

        If this is a normal situation, the top two frames are BDB and the
        Debugger executing the program. If there is an exception, there are two
        further extra frames. All these frames can be ignored.
        """
        stack_data = []
        for frame, line_no in self.stack:
            filename = self.canonic(frame.f_code.co_filename)
            if filename in self.excluded_files: continue
            frame_data = (
                line_no,
                {
                    "filename": frame.f_code.co_filename,
                    "locals": {
                        k: repr(v) for k, v in frame.f_locals.items()
                    },
                    #"globals": {
                    #    k: repr(v) for k, v in frame.f_globals.items()
                    #},
                    #"builtins": {
                    #    k: repr(v) for k, v in frame.f_builtins.items()
                    #},
                    #"restricted": getattr(frame, "f_restricted", ""),
                    #"lasti": repr(frame.f_lasti),
                    #"exc_type": repr(getattr(frame, "f_exc_type", "")),
                    #"exc_value": repr(getattr(frame, "f_exc_value", "")),
                    #"exc_traceback": repr(
                    #    getattr(frame, "f_exc_traceback", "")
                    #),
                    "current": frame is self.curframe,
                },
            )
            stack_data.append(frame_data)

        locals_dict = {}
        excluded_names = ["globals", "locals", "built-in", "__builtins__", \
            "__debug_code__", "__debug_script__"]
        for frame in stack_data:
            for k, v in frame[1]["locals"].items():
                if k in excluded_names: continue
                if not v.startswith("<module") and not v.startswith("execfile("):
                    locals_dict[k] = v
        self.viewstack(locals_dict)

    def lookupmodule(self, filename):
        """Helper function for break/clear parsing -- may be overridden.

        lookupmodule() translates (possibly incomplete) file or module name
        into an absolute file name.
        """
        if os.path.isabs(filename) and  os.path.exists(filename):
            return filename
        f = os.path.join(sys.path[0], filename)
        if  os.path.exists(f) and self.canonic(f) == self.mainpyfile:
            return f
        root, ext = os.path.splitext(filename)
        if ext == '':
            filename = filename + '.py'
        if os.path.isabs(filename):
            return filename
        for dirname in sys.path:
            while os.path.islink(dirname):
                dirname = os.readlink(dirname)
            fullname = os.path.join(dirname, filename)
            if os.path.exists(fullname):
                return fullname
        return None

    def _runscript(self, filename):
        # The script has to run in __main__ namespace (or imports from
        # __main__ will break).
        #
        # So we clear up the __main__ and set several special variables
        # (this gets rid of pdb's globals and cleans old variables on restarts).
        
        import __main__
        __main__.__dict__.clear()
        __main__.__dict__.update({"__name__"    : "__main__",
                                  "__file__"    : filename,
                                  "__builtins__": __builtins__,
                                 })

        # When bdb sets tracing, a number of call and line events happens
        # BEFORE debugger even reaches user's code (and the exact sequence of
        # events depends on python version). So we take special measures to
        # avoid stopping before we reach the main script (see user_line and
        # user_call for details).
        self._wait_for_mainpyfile = 1
        self.mainpyfile = self.canonic(filename)
        self._user_requested_quit = 0 # should exit the process
        statement = 'execfile(%r)' % filename
        self.run(statement)

# Simplified interface

def run(statement, globals=None, locals=None):
    Debugger().run(statement, globals, locals)

def runeval(expression, globals=None, locals=None):
    return Debugger().runeval(expression, globals, locals)

def runctx(statement, globals, locals):
    # B/W compatibility
    run(statement, globals, locals)

def runcall(*args, **kwds):
    return Debugger().runcall(*args, **kwds)

def set_trace():
    Debugger().set_trace(sys._getframe().f_back)

# Post-Mortem interface
def post_mortem(t=None):
    # handling the default
    if t is None:
        # sys.exc_info() returns (type, value, traceback) if an exception is
        # being handled, otherwise it returns None
        t = sys.exc_info()[2]
        if t is None:
            raise ValueError("A valid traceback must be passed if no "
                                               "exception is being handled")
    p = Debugger()
    p.reset()
    p.interaction(None, t)

def pm():
    post_mortem(sys.last_traceback)

