import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import os
import sys
import logging

class AppServerSvc(win32serviceutil.ServiceFramework):
    _svc_name_ = "UvicornService"
    _svc_display_name_ = "Uvicorn FastAPI Service"
    _svc_description_ = "Uvicorn service for running FastAPI application."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.logger = self._getLogger()
        self.is_running = True

    def _getLogger(self):
        logger = logging.getLogger('[UvicornService]')
        handler = logging.FileHandler('C:\\Users\\Administrator\\Desktop\\JBot_Backend\\service.log')
        formatter = logging.Formatter('%(asctime)s %(levelname)-7.7s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

    def SvcStop(self):
        self.logger.info('Service is stopping...')
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.is_running = False
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        self.logger.info('Service is starting...')
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ""))
        self.main()

    def main(self):
        while self.is_running:
            try:
                python_executable = sys.executable
                self.logger.info(f'Starting Uvicorn with: {python_executable} -m uvicorn main:app --host 0.0.0.0 --port 9000 --log-level info')
                proc = subprocess.Popen(
                    [python_executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000", "--log-level", "info"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd="C:\\Users\\Administrator\\Desktop\\JBot_Backend"
                )
                stdout, stderr = proc.communicate()
                self.logger.info(stdout.decode())
                self.logger.error(stderr.decode())
                if proc.returncode != 0:
                    self.logger.error(f'Uvicorn process exited with code {proc.returncode}')
                if not self.is_running:
                    break
            except Exception as e:
                self.logger.error(f'Error: {str(e)}')

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(AppServerSvc)
