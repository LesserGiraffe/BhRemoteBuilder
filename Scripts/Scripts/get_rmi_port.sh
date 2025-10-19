#!/bin/bash

cd $(dirname $0)
if [ -f ./port.txt ]; then
    cat port.txt
else
    echo -e "-1@RmiTcpPort\n"
fi
