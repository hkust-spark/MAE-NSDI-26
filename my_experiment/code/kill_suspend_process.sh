#!/bin/bash

# Get the process IDs of all processes with name containing "peer"
pids=$(pgrep -f "peer")

# Kill each process
for pid in $pids; do
  echo $pid
  kill -9 $pid
done

if [ -e "../last_average_record.log" ]; then
  rm "../last_average_record.log"
fi
if [ -e "../last_average_record_drop_period.log" ]; then
  rm "../last_average_record_drop_period.log"
fi
