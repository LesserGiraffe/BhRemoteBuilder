#!/bin/bash
cd $(dirname $0)
./stop.sh
SCRIPT_PATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
touch port.txt
JAVA_PATH=$SCRIPT_PATH/../BhRuntime/bin/java
HWCTRL_PATH=$SCRIPT_PATH/../BhRuntime/App/Actions/hwctrl
$JAVA_PATH -Djava.rmi.server.hostname=$1 -cp "$SCRIPT_PATH/../BhRuntime/App/Jlib/*"  net.seapanda.bunnyhop.runtime.AppMain --remote --hwctrl | tee port.txt &
echo $JAVA_PATH $HWCTRL_PATH > pname.txt
