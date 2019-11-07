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

package Debugger;

use IO::Socket::INET;

binmode STDIN, ':utf8'; 
binmode STDOUT, ':utf8';
binmode STDERR, ':utf8';

# flush after every write
$| = 1;
my ($socket, $client_socket);

BEGIN {  
  require "perl5db.pl";
}

sub start_server{
  my ($peeraddress, $peerport); 
  # socket creation, binding and listening at the specified port.
  $socket = new IO::Socket::INET (
  LocalHost => '127.0.0.1',
  LocalPort => '5000', #remember to set on Speare code editor side if change this value.
  Proto => 'tcp',
  Listen => 5,
  Reuse => 1
  ) or die "ERROR in Socket Creation : $!\n";

  print "*** Waiting for connection on port 5000.\n";
  # waiting for new client connection.
  $client_socket = $socket->accept();
  # get the host and port number of newly connected client.
  $peer_address = $client_socket->peerhost();
  $peer_port = $client_socket->peerport();
  print "New connection accepted. \n";

  STDOUT->fdopen($client_socket, "w");
  STDERR->fdopen($client_socket, "w");

   my $sysdir;
    foreach my $t (@INC) {
       if (-e "$t/perl5db.pl"){
         $sysdir  = $t;
         last;
       }
    }

    $dbutil::workdir = $sysdir;
    $dbutil::perlsys = "/Library/Perl";
    $dbutil::perlsysdir = "/System/Library/Perl"; 

    $DB::frame = 4;
    $DB::trace = 0; # AutoTrace
    $DB::OUT = $client_socket;
    $DB::IN = $client_socket;
    $DB::tty = $DB::LINEINFO = $client_socket;

};

start_server();

1;

