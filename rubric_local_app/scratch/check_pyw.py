import sys
import subprocess

with open("pyw_check.py", "w", encoding="utf-8") as f:
    f.write("""import sys
with open("pyw_result.txt", "w", encoding="utf-8") as rf:
    rf.write(f"stdout is: {sys.stdout!r}\\n")
    try:
        print("Testing print under pythonw")
        rf.write("print succeeded\\n")
    except Exception as e:
        rf.write(f"print failed: {e}\\n")
""")

res = subprocess.run(["pythonw", "pyw_check.py"])
print("Exit code:", res.returncode)
with open("pyw_result.txt", "r", encoding="utf-8") as f:
    print("Result:\n" + f.read())
