import subprocess
import time
import os
import sys

exe_path = r"d:\ANTIGRAVITY\Theo-doi-hanh-trinh-don-hang\dist\Theo-doi-hanh-trinh-don-hang\Theo-doi-hanh-trinh-don-hang.exe"

if not os.path.exists(exe_path):
    print("EXE not found!")
    sys.exit(1)

env = os.environ.copy()
env["QT_QPA_PLATFORM"] = "offscreen"

proc = subprocess.Popen([exe_path], env=env)
time.sleep(3)

if proc.poll() is None:
    print("SUCCESS: Executable is running properly!")
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
    sys.exit(0)
else:
    print(f"FAILED: Exited with code {proc.returncode}")
    sys.exit(1)
