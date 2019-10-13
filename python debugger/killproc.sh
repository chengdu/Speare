#!/bin/sh
#kill process when address already in use
port=4444
if [ $# -eq 1 ]
 then port=$1
fi
lsof -iTCP -sTCP:LISTEN -n -P | grep $port | awk '{print $2}'| xargs kill -9

