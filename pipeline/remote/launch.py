# Kaggle kernel entry point. Finds this batch's inputs and runs the worker shipped with them.
import glob
import json
import os
import subprocess
import sys

BATCH = "__BATCH__"
for f in glob.glob("/kaggle/input/**/job.json", recursive=True):
    with open(f) as handle:
        batch = json.load(handle)["batch"]
    if batch == BATCH:
        src = os.path.dirname(f)
        break
else:
    sys.exit(f"inputs for batch {BATCH} are not mounted")
subprocess.run(["nvidia-smi"], check=False)
worker = [sys.executable, os.path.join(src, "worker.py"), src, "/kaggle/working"]
sys.exit(subprocess.run(worker, check=False).returncode)
