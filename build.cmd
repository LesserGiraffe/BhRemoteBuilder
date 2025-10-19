@echo off
cd /d %~dp0

mkdir .\BhRemote
mkdir .\BhRemote\BhRuntime
mkdir .\BhRemote\BhRuntime\App\Actions
mkdir .\BhRemote\BhRuntime\App\Actions\open_jtalk
mkdir .\BhRemote\BhRuntime\App\License
mkdir .\BhRemote\BhRuntime\App\Version
xcopy /E /Y .\BhRuntime .\BhRemote\BhRuntime
xcopy /E /Y .\open_jtalk\RaspberryPi\openJTalk\Actions\open_jtalk .\BhRemote\BhRuntime\App\Actions\open_jtalk
xcopy /Y .\open_jtalk\RaspberryPi\openJTalk\Actions\bhSay.sh .\BhRemote\BhRuntime\App\Actions
xcopy /Y .\hwctrl\dist\hwctrl .\BhRemote\BhRuntime\App\Actions
xcopy /Y .\hwctrl\lg.zip .\BhRemote
xcopy /E /Y .\Scripts .\BhRemote
xcopy /Y .\Initialize\initialize.sh .\BhRemote
xcopy /E /Y .\License .\BhRemote\BhRuntime\App\License
xcopy /E /Y .\Version .\BhRemote\BhRuntime\App\Version
