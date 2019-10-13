#! /usr/bin/env python3

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
import re
import sys
import cmd
import bdb
import dis
import code
import glob
import pprint
import signal
import inspect
import traceback
import linecache
import json

__version__ = '0.0.2'
class Restart(Exception):
    """Causes a debugger to be restarted for the debugged python program."""
    pass

__all__ = ["run", "pm", "Debugger", "runeval", "runctx", "runcall", "set_trace",
           "post_mortem", "help"]

def find_function(funcname, filename):
    cre = re.compile(r'def\s+%s\s*[(]' % re.escape(funcname))
    try:
        fp = open(filename)
    except OSError:
        return None
    # consumer of this info expects the first line to be 1
    with fp:
        for lineno, line in enumerate(fp, start=1):
            if cre.match(line):
                return funcname, filename, lineno
    return None

def getsourcelines(obj):
    lines, lineno = inspect.findsource(obj)
    if inspect.isframe(obj) and obj.f_globals is obj.f_locals:
        # must be a module frame: do not try to cut a block out of it
        return lines, 1
    elif inspect.ismodule(obj):
        return lines, 1
    return inspect.getblock(lines[lineno:]), lineno+1

def lasti2lineno(code, lasti):
    linestarts = list(dis.findlinestarts(code))
    linestarts.reverse()
    for i, lineno in linestarts:
        if lasti >= i:
            return lineno
    return 0

class _rstr(str):
    """String that doesn't quote its repr."""
    def __repr__(self):
        return self

# Interaction prompt line will separate file and call info from code
# text using value of line_prefix string.  A newline and arrow may
# be to your liking.  You can set it once pdb is imported using the
# command "pdb.line_prefix = '\n% '".
# line_prefix = ': '    # Use this to get the old situation back
line_prefix = '\n-> '   # Probably a better default

class Debugger(bdb.Bdb, cmd.Cmd):

    def __init__(self, completekey='tab', stdin=None, stdout=None, skip=None,
                 nosigint=False):
        bdb.Bdb.__init__(self, skip=skip)
        cmd.Cmd.__init__(self, completekey, stdin, stdout)
        if stdout:
            self.use_rawinput = 0
        self.prompt = ''
        self.aliases = {}
        self.displaying = {}
        self.mainpyfile = ''
        self._wait_for_mainpyfile = False
        self.tb_lineno = {}
        self.sources = []
        # Try to load readline if it exists
        try:
            import readline
            # remove some common file name delimiters
            readline.set_completer_delims(' \t\n`@#$%^&*()=+[{]}\\|;:\'",<>?')
        except ImportError:
            pass
        self.allow_kbdint = False
        self.nosigint = nosigint

        # Read $HOME/.pdbrc and ./.pdbrc
        self.rcLines = []
        if 'HOME' in os.environ:
            envHome = os.environ['HOME']
            try:
                with open(os.path.join(envHome, ".pdbrc")) as rcFile:
                    self.rcLines.extend(rcFile)
            except OSError:
                pass
        try:
            with open(".pdbrc") as rcFile:
                self.rcLines.extend(rcFile)
        except OSError:
            pass

        self.commands = {} # associates a command list to breakpoint numbers
        self.commands_doprompt = {} # for each bp num, tells if the prompt
                                    # must be disp. after execing the cmd list
        self.commands_silent = {} # for each bp num, tells if the stack trace
                                  # must be disp. after execing the cmd list
        self.commands_defining = False # True while in the process of defining
                                       # a command list
        self.commands_bnum = None # The breakpoint number for which we are
                                  # defining a list

    def sigint_handler(self, signum, frame):
        if self.allow_kbdint:
            raise KeyboardInterrupt
        self.message("\nProgram interrupted. (Use 'cont' to resume).")
        self.set_step()
        self.set_trace(frame)
        # restore previous signal handler
        signal.signal(signal.SIGINT, self._previous_sigint_handler)

    def reset(self):
        bdb.Bdb.reset(self)
        self.forget()

    def forget(self):
        self.lineno = None
        self.stack = []
        self.curindex = 0
        self.curframe = None
        self.tb_lineno.clear()

    def setup(self, f, tb):
        self.forget()
        self.stack, self.curindex = self.get_stack(f, tb)
        while tb:
            # when setting up post-mortem debugging with a traceback, save all
            # the original line numbers to be displayed along the current line
            # numbers (which can be different, e.g. due to finally clauses)
            lineno = lasti2lineno(tb.tb_frame.f_code, tb.tb_lasti)
            self.tb_lineno[tb.tb_frame] = lineno
            tb = tb.tb_next
        self.curframe = self.stack[self.curindex][0]
        # The f_locals dictionary is updated from the actual frame
        # locals whenever the .f_locals accessor is called, so we
        # cache it here to ensure that modifications are not overwritten.
        self.curframe_locals = self.curframe.f_locals
        return self.execRcLines()

    # Can be executed earlier than 'setup' if desired
    def execRcLines(self):
        if not self.rcLines:
            return
        # local copy because of recursion
        rcLines = self.rcLines
        rcLines.reverse()
        # execute every line only once
        self.rcLines = []
        while rcLines:
            line = rcLines.pop().strip()
            if line and line[0] != '#':
                if self.onecmd(line):
                    # if onecmd returns True, the command wants to exit
                    # from the interaction, save leftover rc lines
                    # to execute before next interaction
                    self.rcLines += reversed(rcLines)
                    return True

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
            temp = '{"command": "Paused", "file": "%s", "line": %d}'
            self.message(temp % (filename, frame.f_lineno))
        if self.stop_here(frame):
            #self.message('--Call--')
            self.interaction(frame, None)

    def user_line(self, frame):
        """This function is called when we stop or break at this line."""
        if self._wait_for_mainpyfile:
            if (self.mainpyfile != self.canonic(frame.f_code.co_filename)
                or frame.f_lineno <= 0):
                return
            self._wait_for_mainpyfile = False
        filename = self.canonic(frame.f_code.co_filename)
        if not filename in self.excluded_files:
            temp = '{"command": "Paused", "file": "%s", "line": %d}'
            self.message(temp % (filename, frame.f_lineno))
        if self.bp_commands(frame):
            self.interaction(frame, None)

    def bp_commands(self, frame):
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
                self._cmdloop()
            self.forget()
            return
        return 1

    def user_return(self, frame, return_value):
        """This function is called when a return trap is set here."""
        if self._wait_for_mainpyfile:
            return
        frame.f_locals['__return__'] = return_value
        #self.message('--Return--')
        self.interaction(frame, None)

    def user_exception(self, frame, exc_info):
        """This function is called if an exception occurs,
        but only if we are to stop at or just below this level."""
        if self._wait_for_mainpyfile:
            return
        exc_type, exc_value, exc_traceback = exc_info
        frame.f_locals['__exception__'] = exc_type, exc_value

        # An 'Internal StopIteration' exception is an exception debug event
        # issued by the interpreter when handling a subgenerator run with
        # 'yield from' or a generator controlled by a for loop. No exception has
        # actually occurred in this case. The debugger uses this debug event to
        # stop when the debuggee is returning from such generators.
        prefix = 'Internal ' if (not exc_traceback
                                    and exc_type is StopIteration) else ''
        self.message('%s%s' % (prefix,
            traceback.format_exception_only(exc_type, exc_value)[-1].strip()))
        self.interaction(frame, exc_traceback)

    # General interaction function
    def _cmdloop(self):
        while True:
            try:
                # keyboard interrupts allow for an easy way to cancel
                # the current command, so allow them during interactive input
                self.allow_kbdint = True
                self.cmdloop()
                self.allow_kbdint = False
                break
            except KeyboardInterrupt:
                print('--KeyboardInterrupt--')

    # Called before loop, handles display expressions
    def preloop(self):
        displaying = self.displaying.get(self.curframe)
        if displaying:
            for expr, oldvalue in displaying.items():
                newvalue = self._getval_except(expr)
                # check for identity first; this prevents custom __eq__ to
                # be called at every loop, and also prevents instances whose
                # fields are changed to be displayed
                if newvalue is not oldvalue and newvalue != oldvalue:
                    displaying[expr] = newvalue
                    self.message('display %s: %r  [old: %r]' %
                                 (expr, newvalue, oldvalue))

    def interaction(self, frame, traceback):
        if self.setup(frame, traceback):
            # no interaction desired at this time (happens if .pdbrc contains
            # a command like "continue")
            self.forget()
            return
        #self.print_stack_entry(self.stack[self.curindex])
        self.print_stack_variables()
        self._cmdloop()
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
                exec(code, globals, locals)
            finally:
                sys.stdout = save_stdout
                sys.stdin = save_stdin
                sys.displayhook = save_displayhook
        except:
            exc_info = sys.exc_info()[:2]
            self.error(traceback.format_exception_only(*exc_info)[-1].strip())

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
                ii += 1
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

    def handle_command_def(self, line):
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
        if func.__name__ in self.commands_resuming:
            self.commands_doprompt[self.commands_bnum] = False
            self.cmdqueue = []
            return 1
        return

    # interface abstraction functions
    def message(self, msg):
        pass

    def error(self, msg):
        if msg == 'SyntaxError: invalid syntax':
            return
        print('***', msg, file=self.stdout)
        print('\r\n', file=self.stdout)

    # Generic completion functions.  Individual complete_foo methods can be
    # assigned below to one of these functions.

    def _complete_location(self, text, line, begidx, endidx):
        # Complete a file/module/function location for break/tbreak/clear.
        if line.strip().endswith((':', ',')):
            # Here comes a line number or a condition which we can't complete.
            return []
        # First, try to find matching functions (i.e. expressions).
        try:
            ret = self._complete_expression(text, line, begidx, endidx)
        except Exception:
            ret = []
        # Then, try to complete file names as well.
        globs = glob.glob(text + '*')
        for fn in globs:
            if os.path.isdir(fn):
                ret.append(fn + '/')
            elif os.path.isfile(fn) and fn.lower().endswith(('.py', '.pyw')):
                ret.append(fn + ':')
        return ret

    def _complete_bpnumber(self, text, line, begidx, endidx):
        # Complete a breakpoint number.  (This would be more helpful if we could
        # display additional info along with the completions, such as file/line
        # of the breakpoint.)
        return [str(i) for i, bp in enumerate(bdb.Breakpoint.bpbynumber)
                if bp is not None and str(i).startswith(text)]

    def _complete_expression(self, text, line, begidx, endidx):
        # Complete an arbitrary expression.
        if not self.curframe:
            return []
        # Collect globals and locals.  It is usually not really sensible to also
        # complete builtins, and they clutter the namespace quite heavily, so we
        # leave them out.
        ns = self.curframe.f_globals.copy()
        ns.update(self.curframe_locals)
        if '.' in text:
            # Walk an attribute chain up to the last part, similar to what
            # rlcompleter does.  This will bail if any of the parts are not
            # simple attribute access, which is what we want.
            dotted = text.split('.')
            try:
                obj = ns[dotted[0]]
                for part in dotted[1:-1]:
                    obj = getattr(obj, part)
            except (KeyError, AttributeError):
                return []
            prefix = '.'.join(dotted[:-1]) + '.'
            return [prefix + n for n in dir(obj) if n.startswith(dotted[-1])]
        else:
            # Complete a simple name.
            return [n for n in ns.keys() if n.startswith(text)]

    # Command definitions, called by cmdloop()
    # The argument is the remaining string on the command line
    # Return true to exit from the command loop

    def do_commands(self, arg):
        """commands [bpnumber]
        (com) ...
        (com) end
        """
        if not arg:
            bnum = len(bdb.Breakpoint.bpbynumber) - 1
        else:
            try:
                bnum = int(arg)
            except:
                self.error("Usage: commands [bnum]\n        ...\n        end")
                return
        self.commands_bnum = bnum
        # Save old definitions for the case of a keyboard interrupt.
        if bnum in self.commands:
            old_command_defs = (self.commands[bnum],
                                self.commands_doprompt[bnum],
                                self.commands_silent[bnum])
        else:
            old_command_defs = None
        self.commands[bnum] = []
        self.commands_doprompt[bnum] = True
        self.commands_silent[bnum] = False

        prompt_back = self.prompt
        self.prompt = '(com) '
        self.commands_defining = True
        try:
            self.cmdloop()
        except KeyboardInterrupt:
            # Restore old definitions.
            if old_command_defs:
                self.commands[bnum] = old_command_defs[0]
                self.commands_doprompt[bnum] = old_command_defs[1]
                self.commands_silent[bnum] = old_command_defs[2]
            else:
                del self.commands[bnum]
                del self.commands_doprompt[bnum]
                del self.commands_silent[bnum]
            self.error('command definition aborted, old commands restored')
        finally:
            self.commands_defining = False
            self.prompt = prompt_back

    complete_commands = _complete_bpnumber

    def do_break(self, arg, temporary = 0):
        """b(reak) [ ([filename:]lineno | function) [, condition] ]
        """
        if not arg:
            if self.breaks:  # There's at least one
                self.message("Num Type         Disp Enb   Where")
                for bp in bdb.Breakpoint.bpbynumber:
                    if bp:
                        self.message(bp.bpformat())
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
                self.error('%r not found from sys.path' % filename)
                return
            else:
                filename = f
            arg = arg[colon+1:].lstrip()
            try:
                lineno = int(arg)
            except ValueError:
                self.error('Bad lineno: %s' % arg)
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
                    if hasattr(func, '__func__'):
                        func = func.__func__
                    code = func.__code__
                    #use co_name to identify the bkpt (function names
                    #could be aliased, but co_name is invariant)
                    funcname = code.co_name
                    lineno = code.co_firstlineno
                    filename = code.co_filename
                except:
                    # last thing to try
                    (ok, filename, ln) = self.lineinfo(arg)
                    if not ok:
                        self.error('The specified object %r is not a function '
                                   'or was not found along sys.path.' % arg)
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
            if err:
                self.error(err)
            else:
                bp = self.get_breaks(filename, line)[-1]
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

    complete_break = _complete_location
    complete_b = _complete_location

    def do_tbreak(self, arg):
        """tbreak [ ([filename:]lineno | function) [, condition] ]
        Same arguments as break, but sets a temporary breakpoint: it
        is automatically deleted when first hit.
        """
        self.do_break(arg, 1)

    complete_tbreak = _complete_location

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
            self.error('Blank or comment')
            return 0
        return lineno

    def do_enable(self, arg):
        args = arg.split()
        for i in args:
            try:
                bp = self.get_bpbynumber(i)
            except ValueError as err:
                self.error(err)
            else:
                bp.enable()
                self.message('Enabled %s' % bp)

    complete_enable = _complete_bpnumber

    def do_disable(self, arg):
        args = arg.split()
        for i in args:
            try:
                bp = self.get_bpbynumber(i)
            except ValueError as err:
                self.error(err)
            else:
                bp.disable()
                self.message('Disabled %s' % bp)

    complete_disable = _complete_bpnumber

    def do_condition(self, arg):
        args = arg.split(' ', 1)
        try:
            cond = args[1]
        except IndexError:
            cond = None
        try:
            bp = self.get_bpbynumber(args[0].strip())
        except IndexError:
            self.error('Breakpoint number expected')
        except ValueError as err:
            self.error(err)
        else:
            bp.cond = cond
            if not cond:
                self.message('Breakpoint %d is now unconditional.' % bp.number)
            else:
                self.message('New condition set for breakpoint %d.' % bp.number)

    complete_condition = _complete_bpnumber

    def do_ignore(self, arg):
        """ignore bpnumber [count]
        """
        args = arg.split()
        try:
            count = int(args[1].strip())
        except:
            count = 0
        try:
            bp = self.get_bpbynumber(args[0].strip())
        except IndexError:
            self.error('Breakpoint number expected')
        except ValueError as err:
            self.error(err)
        else:
            bp.ignore = count
            if count > 0:
                if count > 1:
                    countstr = '%d crossings' % count
                else:
                    countstr = '1 crossing'
                self.message('Will ignore next %s of breakpoint %d.' %
                             (countstr, bp.number))
            else:
                self.message('Will stop next time breakpoint %d is reached.'
                             % bp.number)

    complete_ignore = _complete_bpnumber

    def do_clear(self, arg):
        if not arg:
            bplist = [bp for bp in bdb.Breakpoint.bpbynumber if bp]
            self.clear_all_breaks()
            for bp in bplist:
                self.message('Deleted %s' % bp)
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
                bplist = self.get_breaks(filename, lineno)
                err = self.clear_break(filename, lineno)
            if err:
                self.error(err)
            else:
                for bp in bplist:
                    self.message('Deleted %s' % bp)
            return
        numberlist = arg.split()
        for i in numberlist:
            try:
                bp = self.get_bpbynumber(i)
            except ValueError as err:
                self.error(err)
            else:
                self.clear_bpbynumber(i)
                self.message('Deleted %s' % bp)
    do_cl = do_clear # 'c' is already an abbreviation for 'continue'

    complete_clear = _complete_location
    complete_cl = _complete_location

    def do_where(self, arg):
        self.print_stack_trace()
    do_w = do_where
    do_bt = do_where

    def _select_frame(self, number):
        assert 0 <= number < len(self.stack)
        self.curindex = number
        self.curframe = self.stack[self.curindex][0]
        self.curframe_locals = self.curframe.f_locals
        self.print_stack_entry(self.stack[self.curindex])
        self.lineno = None

    def do_up(self, arg):
        if self.curindex == 0:
            self.error('Oldest frame')
            return
        try:
            count = int(arg or 1)
        except ValueError:
            self.error('Invalid frame count (%s)' % arg)
            return
        if count < 0:
            newframe = 0
        else:
            newframe = max(0, self.curindex - count)
        self._select_frame(newframe)
    do_u = do_up

    def do_down(self, arg):
        if self.curindex + 1 == len(self.stack):
            self.error('Newest frame')
            return
        try:
            count = int(arg or 1)
        except ValueError:
            self.error('Invalid frame count (%s)' % arg)
            return
        if count < 0:
            newframe = len(self.stack) - 1
        else:
            newframe = min(len(self.stack) - 1, self.curindex + count)
        self._select_frame(newframe)
    do_d = do_down

    def do_until(self, arg):
        if arg:
            try:
                lineno = int(arg)
            except ValueError:
                self.error('Error in argument: %r' % arg)
                return
            if lineno <= self.curframe.f_lineno:
                self.error('"until" line number is smaller than current '
                           'line number')
                return
        else:
            lineno = None
        self.set_until(self.curframe, lineno)
        return 1
    do_unt = do_until

    def do_step(self, arg):
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
        # this is caught in the main debugger loop
        raise Restart

    do_restart = do_run

    def do_return(self, arg):
        self.set_return(self.curframe)
        return 1
    do_r = do_return

    def do_continue(self, arg):
        if not self.nosigint:
            try:
                self._previous_sigint_handler = \
                    signal.signal(signal.SIGINT, self.sigint_handler)
            except ValueError:
                # ValueError happens when do_continue() is invoked from
                # a non-main thread in which case we just continue without
                # SIGINT set. Would printing a message here (once) make
                # sense?
                pass
        self.set_continue()
        return 1
    do_c = do_cont = do_continue

    def do_jump(self, arg):
        if self.curindex + 1 != len(self.stack):
            self.error('You can only jump within the bottom frame')
            return
        try:
            arg = int(arg)
        except ValueError:
            self.error("The 'jump' command requires a line number")
        else:
            try:
                # Do the jump, fix up our copy of the stack, and display the
                # new position
                self.curframe.f_lineno = arg
                self.stack[self.curindex] = self.stack[self.curindex][0], arg
                self.print_stack_entry(self.stack[self.curindex])
            except ValueError as e:
                self.error('Jump failed: %s' % e)
    do_j = do_jump

    def do_debug(self, arg):
        sys.settrace(None)
        globals = self.curframe.f_globals
        locals = self.curframe_locals
        p = Pdb(self.completekey, self.stdin, self.stdout)
        p.prompt = "(%s) " % self.prompt.strip()
        self.message("ENTERING RECURSIVE DEBUGGER")
        sys.call_tracing(p.run, (arg, globals, locals))
        self.message("LEAVING RECURSIVE DEBUGGER")
        sys.settrace(self.trace_dispatch)
        self.lastcmd = p.lastcmd

    complete_debug = _complete_expression

    def do_quit(self, arg):
        self._user_requested_quit = True
        self.set_quit()
        return 1

    do_q = do_quit
    do_exit = do_quit

    def do_EOF(self, arg):
        self.message('')
        self._user_requested_quit = True
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
            if name in dict:
                self.message('%s = %r' % (name, dict[name]))
            else:
                self.message('%s = *** undefined ***' % (name,))
    do_a = do_args

    def do_retval(self, arg):
        if '__return__' in self.curframe_locals:
            self.message(repr(self.curframe_locals['__return__']))
        else:
            self.error('Not yet returned!')
    do_rv = do_retval

    def _getval(self, arg):
        try:
            return eval(arg, self.curframe.f_globals, self.curframe_locals)
        except:
            exc_info = sys.exc_info()[:2]
            self.error(traceback.format_exception_only(*exc_info)[-1].strip())
            raise

    def _getval_except(self, arg, frame=None):
        try:
            if frame is None:
                return eval(arg, self.curframe.f_globals, self.curframe_locals)
            else:
                return eval(arg, frame.f_globals, frame.f_locals)
        except:
            exc_info = sys.exc_info()[:2]
            err = traceback.format_exception_only(*exc_info)[-1].strip()
            return _rstr('** raised %s **' % err)

    def do_p(self, arg):
        try:
            self.message(repr(self._getval(arg)))
        except:
            pass

    def do_pp(self, arg):
        try:
            self.message(pprint.pformat(self._getval(arg)))
        except:
            pass

    complete_print = _complete_expression
    complete_p = _complete_expression
    complete_pp = _complete_expression

    def do_source(self, arg):
        try:
            obj = self._getval(arg)
        except:
            return
        try:
            lines, lineno = getsourcelines(obj)
        except (OSError, TypeError) as err:
            self.error(err)
            return
        self._print_lines(lines, lineno)

    complete_source = _complete_expression

    def _print_lines(self, lines, start, breaks=(), frame=None):
        """Print a range of lines."""
        if frame:
            current_lineno = frame.f_lineno
            exc_lineno = self.tb_lineno.get(frame, -1)
        else:
            current_lineno = exc_lineno = -1
        for lineno, line in enumerate(lines, start):
            s = str(lineno).rjust(3)
            if len(s) < 4:
                s += ' '
            if lineno in breaks:
                s += 'B'
            else:
                s += ' '
            if lineno == current_lineno:
                s += '->'
            elif lineno == exc_lineno:
                s += '>>'
            self.message(s + '\t' + line.rstrip())

    def do_whatis(self, arg):
        """whatis arg
        Print the type of the argument.
        """
        try:
            value = self._getval(arg)
        except:
            # _getval() already printed the error
            return
        code = None
        # Is it a function?
        try:
            code = value.__code__
        except Exception:
            pass
        if code:
            self.message('Function %s' % code.co_name)
            return
        # Is it an instance method?
        try:
            code = value.__func__.__code__
        except Exception:
            pass
        if code:
            self.message('Method %s' % code.co_name)
            return
        # Is it a class?
        if value.__class__ is type:
            self.message('Class %s.%s' % (value.__module__, value.__qualname__))
            return
        # None of the above...
        self.message(type(value))

    complete_whatis = _complete_expression

    def do_display(self, arg):
        if not arg:
            self.message('Currently displaying:')
            for item in self.displaying.get(self.curframe, {}).items():
                self.message('%s: %r' % item)
        else:
            val = self._getval_except(arg)
            self.displaying.setdefault(self.curframe, {})[arg] = val
            self.message('display %s: %r' % (arg, val))

    complete_display = _complete_expression

    def do_undisplay(self, arg):
        if arg:
            try:
                del self.displaying.get(self.curframe, {})[arg]
            except KeyError:
                self.error('not displaying %s' % arg)
        else:
            self.displaying.pop(self.curframe, None)

    def complete_undisplay(self, text, line, begidx, endidx):
        return [e for e in self.displaying.get(self.curframe, {})
                if e.startswith(text)]

    def do_interact(self, arg):
        ns = self.curframe.f_globals.copy()
        ns.update(self.curframe_locals)
        code.interact("*interactive*", local=ns)

    def do_alias(self, arg):
        args = arg.split()
        if len(args) == 0:
            keys = sorted(self.aliases.keys())
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

    def do_basedir(self, arg):
        if os.path.isdir(arg) and not arg in self.basedirs:
            self.basedirs.append(arg)
            sys.path.insert(0, arg)
            self.message('%s added in sys.path.' % arg)
        else: self.message('*** %s is not a directory or already added.' % arg)

    def complete_unalias(self, text, line, begidx, endidx):
        return [a for a in self.aliases if a.startswith(text)]

    # List of all the commands making the program resume execution.
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
        if frame is self.curframe:prefix = '> '
        else: prefix = '  '
        self.message(prefix + self.format_stack_entry(frame_lineno, prompt_prefix))

    def viewstack(self, data):
        """
        Dumps data related to a referenced event to the socket.
        """
        try:
            dumped = json.dumps({"command": "stack", "data": data})
            dumped = dumped.replace("u\'","\'") # get rid of backslashes
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
        excluded_names = ["globals", "locals", "statement", "built-in", \
            "__builtins__", "__debug_code__", "__debug_script__"]
        for frame in stack_data:
            for k, v in frame[1]["locals"].items():
                if k in excluded_names: continue
                if not v.startswith("<module") and not v.startswith("exec(compile"):
                    locals_dict[k] = v
        self.viewstack(locals_dict)

    def lookupmodule(self, filename):
        
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
        self._wait_for_mainpyfile = True
        self.mainpyfile = self.canonic(filename)
        self._user_requested_quit = False

        with open(filename, "rb") as fp:
            statement = "exec(compile(%r, %r, 'exec'))" % \
                        (fp.read(), self.mainpyfile)
        self.run(statement)

# Simplified interface

def run(statement, globals=None, locals=None):
    Pdb().run(statement, globals, locals)

def runeval(expression, globals=None, locals=None):
    return Pdb().runeval(expression, globals, locals)

def runctx(statement, globals, locals):
    # B/W compatibility
    run(statement, globals, locals)

def runcall(*args, **kwds):
    return Pdb().runcall(*args, **kwds)

def set_trace():
    Pdb().set_trace(sys._getframe().f_back)

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

    p = Pdb()
    p.reset()
    p.interaction(None, t)

def pm():
    post_mortem(sys.last_traceback)

