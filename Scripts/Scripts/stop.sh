#!/bin/bash
cd $(dirname $0)

# 指定したプロセスの子孫プロセスの PID を全て出力する.
list_descendants() {
    local PID=$1
    local CHILD
    for CHILD in $(pgrep -P "$PID"); do
        echo "$CHILD"
        list_descendants "$CHILD"
    done
}

if [ -f pname.txt ]; then
    PNAME=$(cat ./pname.txt | awk '{print $1}')
    if [[ -n "$PNAME" ]]; then
        TARGET_PIDS=()
        for PID in $(pgrep -f -- "$PNAME"); do
            # 親プロセスを kill すると子プロセスの親が付け替わるので, 先に親子関係を全て調べておく.
            TARGET_PIDS+=("$PID" $(list_descendants "$PID"))
        done
        # hwctrl に後処理をさせるため SIGTERM(15) を送る.
        for PID in "${TARGET_PIDS[@]}"; do
            # echo "kill " $PID   # output process ID
            kill -15 "$PID" 2> /dev/null
        done
        # 全てのプロセスが終了するのを最大 7 秒待つ.
        for _ in $(seq 70); do
            ALIVE=0
            for PID in "${TARGET_PIDS[@]}"; do
                if kill -0 "$PID" 2> /dev/null; then
                    ALIVE=1
                    break
                fi
            done
            if [[ $ALIVE -eq 0 ]]; then
                break
            fi
            sleep 0.1
        done
    fi
fi

if [ -f port.txt ]; then
    rm port.txt
fi
