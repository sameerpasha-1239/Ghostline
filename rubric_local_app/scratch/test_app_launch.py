import sys
import os
import subprocess
import time

# Clean up any test files
for f in ["pyw_check.py", "pyw_result.txt", "app_test_out.log", "app_test_err.log"]:
    if os.path.exists(f):
        try: os.remove(f)
        except Exception: pass

print("--- Testing rubric_local/app.py launch with pythonw ---")
with open("app_test_out.log", "w") as out_f, open("app_test_err.log", "w") as err_f:
    proc = subprocess.Popen(
        ["pythonw", "rubric_local/app.py"],
        stdout=out_f,
        stderr=err_f,
        cwd=os.getcwd()
    )
    time.sleep(2)
    poll = proc.poll()
    print("Process PID:", proc.pid, "Status after 2s:", poll)
    if poll is None:
        print("Application is running properly!")
        proc.terminate()
        time.sleep(0.5)
        if proc.poll() is None:
            proc.kill()
    else:
        print("Application exited immediately!")

with open("app_test_out.log", "r") as f:
    out = f.read()
with open("app_test_err.log", "r") as f:
    err = f.read()

print("STDOUT:", repr(out))
print("STDERR:", repr(err))
