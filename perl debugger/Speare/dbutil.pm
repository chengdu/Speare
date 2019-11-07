#!/usr/bin/perl

# A generic Perl debugger for Speare Pro.
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

package dbutil;

#use File::Basename;

use vars qw(
   $workdir
   $perlsys 
   $perlsysdir
);

sub isexludedpath{
  my $f = shift;
  
  if ($f eq "perl5db.pl" or $f eq $workdir.. "/perl5db.pl") {
    return 1;
  }

#  my $dirname = dirname($f);
#  foreach my $dir ($perlsys, $perlsysdir, $workdir){
#      if ($dir =~ m/^$dirname/){
#        return 1;
#      }
#  }

  # e.g. (eval 8)[/System/Library/Perl
  if ($f =~ m/^\(eval\s(\d+)\)\[/){
    return 1;
  }

  return 0;
}

1;

