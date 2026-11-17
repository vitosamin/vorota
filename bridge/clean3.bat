@echo off
cd /d C:\Users\Public
del /q dev_state.txt ev_ok.txt final_list.txt gate_cfg.txt gate_ini.txt gate_ini2.txt queue.txt lat*.txt per3.txt reg*.txt watch.txt period*.txt restart_serv.txt csc_bridge3.log bridge_watchdog.bat.orig inst.txt pub_list.txt recovery.txt remotask.txt mkw2.txt 2>nul
del /q *.png 2>nul
echo === итог === > C:\Users\Public\fl.txt
for %%F in (*.exe *.vbs *.bat *.json *.cs *.log) do echo %%F >> C:\Users\Public\fl.txt
