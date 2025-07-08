import os
import threading
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from app.index_generator import generate_indexes

class CSVHandler(FileSystemEventHandler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def on_modified(self, event):
        if event.src_path.endswith('.csv'):
            print(f"Detected modification in {event.src_path}. Regenerating indexes...")
            self.callback(event.src_path)  # Pass the event source path to the callback

def start_listener(callback):
    def run_observer():
        observer = Observer()
        data_folder_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))
        observer.schedule(CSVHandler(callback), path=data_folder_path, recursive=True)
        observer.start()
        print("Index listener started. Waiting for changes...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    listener_thread = threading.Thread(target=run_observer, daemon=True)
    listener_thread.start()

if __name__ == "__main__":
    start_listener(generate_indexes)
