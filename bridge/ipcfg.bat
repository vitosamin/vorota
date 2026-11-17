@echo off
ipconfig /all > C:\Users\Public\ipcfg.txt 2>&1
route print >> C:\Users\Public\ipcfg.txt 2>&1
