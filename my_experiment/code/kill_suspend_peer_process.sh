#!/bin/bash

# Get the process IDs of all processes with name containing "peer"
pids=$(pgrep -f "peer")

# Kill each process
for pid in $pids; do
  kill -9 $pid
done
