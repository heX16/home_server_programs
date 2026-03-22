@echo off
rem Enable the UTF8 encoding support for this script file
chcp 65001 >nul
%~d0
cd "%~d0%~p0"
IF %ERRORLEVEL%==0 GOTO PATH_IS_OK
exit
:PATH_IS_OK

python example.py --dir="../.." --store=test.yaml
