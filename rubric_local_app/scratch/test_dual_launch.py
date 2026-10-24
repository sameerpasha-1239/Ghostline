import os
import subprocess
import time

print("--- Launching Instance 1 ---")
p1 = subprocess.Popen(["python", "rubric_local/app.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
time.sleep(1.5)
print("Instance 1 PID:", p1.pid, "Status:", p1.poll())

print("--- Launching Instance 2 ---")
p2 = subprocess.Popen(["python", "rubric_local/app.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
p2_out, p2_err = p2.communicate(timeout=5)
print("Instance 2 Exit Code:", p2.returncode)
print("Instance 2 STDOUT:\n", p2_out)
print("Instance 2 STDERR:\n", p2_err)

print("--- Checking Instance 1 after Instance 2 ---")
print("Instance 1 Status:", p1.poll())

p1.terminate()
time.sleep(0.5)
if p1.poll() is None:
    p1.kill()
