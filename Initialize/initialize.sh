#!/bin/bash

set -e
cd $(dirname $0)
sudo raspi-config nonint do_i2c 0
ln -s ./libHTSEngine.so.1.0.0 ./BhRuntime/App/Actions/open_jtalk/libHTSEngine.so.1

if [ -d ./lg ]; then
    sudo rm -rf ./lg
fi

unzip lg.zip
chmod ug+rwx -R .
cd lg
echo -e "\nInstall lg"
make
sudo make install
cd ..
sudo rm -rf ./lg

echo -e "\nCompleted"
