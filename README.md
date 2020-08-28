# Speare
![Logo of Speare](http://sevenuc.com/images/Speare/logo.png) <br>
The free small IDE for scripting languages.<br>
http://sevenuc.com/en/Speare.html<br>
http://github.com/chengdu/Speare<br>
https://sourceforge.net/projects/speare/<br>

Speare is an ultra lightweight code editor and a small IDE that provides debugging environment for C, C++, Ruby, mruby, Lua, Python, PHP, Perl and Tcl. It was originally developed to providing a native scripting language debugging environment that seamlessly integrated with C and C++, and with an efficient code navigation and call routines tracing ability. Speare has very simple interface that allows end user to add a new programming language code runner, parser, syntax highlighting, code formatter and debugger to it. Most of the debuggers of Speare code editor supports extending themselves in source code level and directly switch between any version of self-compiled scripting language interpreters.<br>

Why another code editor and IDE on macOS?
------------
Although there are so many code editor and IDE available on macOS, but three feature of Speare code editor can make it unique:<br>
1. **Lightweight.** Most of them are very heavy, bulky, but Speare code editor is really really ultra light.<br>
2. **Cost.** Most of them are very expensive, but Speare code editor is free, of course, you can purchase the pro version to donate some money to the author, but that is not mandatory.<br>
3. **Freedom.** Feel light, simple and free, flexibility to extend the IDE to support special developing requirements and easily add a new programming language to it, most of the IDE on macOS can't give you such ability and freedom. In fact, Speare code editor give you very flexible control to extend it and add a debugging environment for any programming language.<br>

Features
------------
1. Well designed user operation interface. Intuitive and simple.<br>
2. High performance of managing large amount of files and big files.<br> 
3. Fast search and replace in current document, selected folder, opened files and entire project.<br>
4. Smoothly edit multiple files that written in different programming languages simultaneously.<br>
5. Supports almost all common programming languages syntax highlighting and parsing.<br>
6. Auto-completion, sensitively typing with keywords, live parsing symbol definition with priority.<br>
7. Jump to definition and fast locate code lines between editing files by symbol index, bookmark or searching.<br>
8. Unlimited go back and forward, automatically remember jump location and current editing locations.<br>
9. Keeping entire state after quit, the opened files, selection of each file and the cursor location.<br>
10. Customisation of fonts and colours for the text editor.<br>
11. Full featured markdown editor, run Javascript code instantly, well support Web development.<br>
12. Ultra lightweight.<br>
<br>


Other Builtin Features:
------------
a. Run syntax checking and editing code instantly.<br>
b. C and C++ debugging with LLDB.<br>
c. Binary file automatically detection.<br>
d. Automatically detecting file encoding and convert to UTF-8 by default when open file.<br>
e. Code block selection by double clicking the begin symbol of code block.<br>
f. Preview all kinds of files, image, pdf, office documents, audio and video etc.<br>
<br>

Screenshots
-------------
![Screenshot of Speare](http://sevenuc.com/images/Speare/9.png) <br>
![Screenshot of Speare](http://sevenuc.com/images/Speare/1.png) <br>
![Screenshot of Speare](http://sevenuc.com/images/Speare/2.png) <br>
![Screenshot of Speare](http://sevenuc.com/images/Speare/3.png) <br>
<br>

C and C++ Debugger
-----------
The [C and C++ debugger](http://sevenuc.com/en/debugger.html#lldb) of Speare implemented as a script client of [LLDB](http://lldb.llvm.org/), and support extend it by yourself. You can enjoy debugging almost any type of C and C++ applications under the lightweight debugging environment of Speare code editor.<br>
<br>

mruby Debugger
-----------
The [mruby debugger](http://sevenuc.com/en/debugger.html#mruby) of Speare Pro is a patched version of mruby 2.0.1 that support remote debugging mruby project.<br>
<br>

Ruby Debugger
-----------
The [Ruby debugger](http://sevenuc.com/en/debugger.html#ruby) of Speare Pro support all kinds of Ruby interpreters, the version includes: 1.8.x, 1.9.x, 2.x, and JRuby. of course, Rails debugging also supported.<br>
<br>

Lua Debugger
-----------
The [Lua debugger](http://sevenuc.com/en/debugger.html#lua) of Speare Pro support Lua debugging version includes: 5.1.4, 5.1.5, 5.2.4, 5.3.5 5.4.0-alpha, all kinds of Lua interpreter or your own customised version of Lua.<br>
<br>

Python Debugger
-----------
The [Python debugger](http://sevenuc.com/en/debugger.html#python) of Speare Pro supports Python version 2.5, 2.6, 2.7 and 3.x, and MicroPython. Debugging framework such as Flask and Django based on application also supported.<br>
<br>

PHP Debugger
-----------
The [PHP debugger](http://sevenuc.com/en/debugger.html#php) of Speare Pro supports all kinds debugging of PHP applications and any version of PHP interpreter that has Xdebug support from PHP 5.x to PHP 7.x. Debugging PHP command line applications is as same as web applications that based on web frameworks.<br>
<br>

Perl Debugger
-----------
The [Perl debugger](http://sevenuc.com/en/debugger.html#perl) of Speare Pro implemented as a patched version of perl5db.pl, and support extend it by yourself. The debugger was based on the builtin debugger of Perl, so it can work with all versions of Perl interpreter that perl5db.pl supported.<br>
<br>

Tcl Debugger
-----------
The [Tcl debugger](http://sevenuc.com/en/debugger.html#tcl) of Speare code editor implemented with Tcl scripts and an extension written with C to parse Tcl source code, and support extend it by yourself. You can enjoy debugging almost all kinds of Tcl applications under the lightweight debugging environment of Speare code editor.<br>
<br>

Add a New Programming Language
-----------
Download the guide from here: [Language Extension Protocol](http://sevenuc.com/download/language_extension_protocol.pdf), and following the description to add a new programming language code runner, parser, syntax highlighting, code formatter and debugger in Speare code editor.<br>
<br>

References
-------------
Speare code editor: http://sevenuc.com/en/speare.html<br>
Speare Pro, the free small IDE for scripting languages: http://sevenuc.com/en/debugger.html<br>
