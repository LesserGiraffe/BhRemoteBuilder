#!/bin/bash
cd $(dirname $0)

if [ -f pname.txt ]; then
    PNAMES=$(cat ./pname.txt | awk '{print $1} {print $2}')
    for PNAME in $PNAMES
    do
        # echo $PNAME  # output process name
        PIDS=($(pgrep -f $PNAME))
        if [[ ${#PIDS[@]} -gt 0 ]]; then
            for PID in "${PIDS[@]}"; do
                # echo "pid " $PID   # output process ID
                if [[ -n "$PID" ]]; then
                    PGID=$(ps -o pgid= -p "$PID" | awk '{print $1}')
                    # echo "pgid " $PGID   # output process group ID
                    if [[ -n "$PGID" ]]; then
                        kill -15 -"$PGID"  # hwctrl に後処理をさせるため SIGTERM(15) を送る.
                    fi
                fi
            done
        fi
    done
fi

if [ -f port.txt ]; then
    rm port.txt
fi
