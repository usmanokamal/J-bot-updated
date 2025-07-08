@echo off
cd C:\Users\Administrator\Desktop\JBot_Backend
C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe -m uvicorn main:app --host 0.0.0.0 --port 9000 --log-level info
