#!/bin/bash
# Real kill switch series through the public API, one task at a time. Usage: kill_series.sh <base url> <tasks dir>
B="$1"
E="$2"
LONG="Run one python step that prints a heartbeat line every second for 100 seconds, flushing each line, and then writes done.txt containing the word done."
for i in 1 2 3 4 5; do
  timeout 240 python scripts/live_task.py "$B" "$E" "kill-step-$i" "$LONG" --kill-after 6 --timeout 220 2>&1 | grep -E 'final |KILL|Traceback|Error' | cut -c1-200
done
for i in 1 2 3; do
  timeout 240 python scripts/live_task.py "$B" "$E" "kill-boot-$i" "$LONG" --kill-after 10 --kill-when provisioning --timeout 220 2>&1 | grep -E 'final |KILL|Traceback|Error' | cut -c1-200
done
echo series-done
