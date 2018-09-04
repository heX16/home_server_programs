@echo off
%~d0
cd "%~d0%~p0"
IF %ERRORLEVEL%==0 GOTO PATH_IS_OK
exit
:PATH_IS_OK

python gen_test_openhab
C:\Python34\python.exe gen_test_openhab
pause
