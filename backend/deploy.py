"""Zip a backend/<dir>/index.py (plus backend/shared/*.py) and create or update its Lambda.

Usage: python backend/deploy.py <dir> <function-name> [timeout] [KEY=VAL ...]
"""
import io
import os
import subprocess
import sys
import tempfile
import zipfile

REGION = "us-east-1"
ACCOUNT = "506790343959"
ROLE = f"arn:aws:iam::{ACCOUNT}:role/flight-lambda-role"


def aws(*args, check=True):
    return subprocess.run(["aws", *args, "--region", REGION], capture_output=True, text=True, check=check)


def main():
    src_dir, name = sys.argv[1], sys.argv[2]
    timeout = sys.argv[3] if len(sys.argv) > 3 else "10"
    env = [a for a in sys.argv[4:] if "=" in a]
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, src_dir, "index.py")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(src, "index.py")
        shared = os.path.join(here, "shared")
        for fn in sorted(os.listdir(shared)):
            if fn.endswith(".py"):
                z.write(os.path.join(shared, fn), fn)
    fd, zpath = tempfile.mkstemp(suffix=".zip")
    with os.fdopen(fd, "wb") as f:
        f.write(buf.getvalue())

    exists = aws("lambda", "get-function", "--function-name", name, check=False).returncode == 0
    if exists:
        aws("lambda", "update-function-code", "--function-name", name, "--zip-file", f"fileb://{zpath}")
        aws("lambda", "wait", "function-updated", "--function-name", name)
        cfg = ["lambda", "update-function-configuration", "--function-name", name, "--timeout", timeout]
        if env:
            cfg += ["--environment", "Variables={" + ",".join(env) + "}"]
        aws(*cfg)
        print("updated", name)
    else:
        cmd = ["lambda", "create-function", "--function-name", name, "--runtime", "python3.12",
               "--handler", "index.handler", "--role", ROLE, "--timeout", timeout,
               "--zip-file", f"fileb://{zpath}"]
        if env:
            cmd += ["--environment", "Variables={" + ",".join(env) + "}"]
        aws(*cmd)
        print("created", name)
    aws("lambda", "wait", "function-active-v2", "--function-name", name)
    os.remove(zpath)


if __name__ == "__main__":
    main()
