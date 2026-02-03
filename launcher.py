import subprocess
import time
import sys
import os

def main():
    # Get the folder where this executable is running
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    # Define paths to the two worker EXEs
    backend_path = os.path.join(base_dir, "backend.exe")
    frontend_path = os.path.join(base_dir, "frontend.exe")

    print("🚀 Launching EYRA System...")

    # 1. Start Backend (Hidden Window)
    # 0x08000000 is the Windows flag for "CREATE_NO_WINDOW"
    creation_flags = 0x08000000 if sys.platform == "win32" else 0
    
    try:
        backend_process = subprocess.Popen([backend_path], creationflags=creation_flags)
    except FileNotFoundError:
        print("❌ Error: Could not find 'backend.exe'.")
        input("Press Enter to exit...")
        return

    time.sleep(2) # Wait for Brain to wake up

    # 2. Start Frontend (Visible) and WAIT for it to close
    try:
        subprocess.call([frontend_path])
    except FileNotFoundError:
        print("❌ Error: Could not find 'frontend.exe'.")
        backend_process.terminate()
        input("Press Enter to exit...")
        return

    # 3. Cleanup: When Frontend closes, kill the Backend
    backend_process.terminate()

if __name__ == "__main__":
    main()