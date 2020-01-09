#!/usr/bin/perl -w

# A MATLAB helper script for Speare code editor.
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

use strict;
use warnings;
use Cwd;
use File::Basename;
use utf8;

binmode STDIN, ':utf8';
binmode STDOUT, ':utf8';
binmode STDERR, ':utf8';

sub scanDirectory{
    my $workdir = shift @_;
    chdir($workdir) or die "Unable to enter dir $workdir:$!\n";
    my ($startdir) = &cwd;
    opendir(DIR, $workdir) or die "Unable to open $workdir:$!\n"; # "."
    my @names = readdir(DIR) or die "Unable to read $workdir:$!\n";
    closedir(DIR);

    foreach my $name (@names){
        next if ($name eq ".");
        next if ($name eq "..");
        my $filepath = $workdir."/".$name;
        if (-d $filepath) {
            &scanDirectory($filepath);
            next;
        }
        my ($basename, $parentdir, $extension) = fileparse($filepath, qr/\.[^.]*$/);
        #if ($name =~ /\.m$/) {
        if ($extension eq ".m") {
          print($filepath, "\n");
          my $newpath = $workdir."/".$basename.".mat"; # .m --> .mat
          my $command = "mv \"$filepath\" \"$newpath\"";
          system($command);
        }
        chdir($startdir) or 
           die "Unable to change to dir $startdir:$!\n";
    }
}

# To prevent conflict with objective-c files,
# MATLAB source code file extension name must be renamed from .m to .mat.
if ($#ARGV + 1 == 1) {
  my $srcdir = $ARGV[0];
  print("Rename source files in ".$srcdir." ...\n");
  &scanDirectory($srcdir);
}else{
  print("Usage: perl rename.pl directory.\n");
}


