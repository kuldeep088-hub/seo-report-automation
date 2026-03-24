@echo off
cd /d "C:\Users\HP\Desktop\Report Automation"
python scheduler.py >> logs\scheduler_startup.log 2>&1
