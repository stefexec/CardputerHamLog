import os
import tarfile
import shutil
import stat

def build():
    os.makedirs("dist", exist_ok=True)
    tar_name = "dist/payload.tar.gz"
    
    # Bundle the python code and assets
    with tarfile.open(tar_name, "w:gz") as tar:
        for f in os.listdir("."):
            if f.endswith(".py") or f in ["assets", "fonts"]:
                tar.add(f)

    # Create self-extracting bash script
    script = """#!/bin/sh
APP_DIR=/tmp/hamlog_app
mkdir -p "$APP_DIR"
sed '1,/^__PAYLOAD_BEGIN__/d' "$0" | tar xz -C "$APP_DIR"
cd "$APP_DIR"
exec python3 main.py "$@"
exit 0
__PAYLOAD_BEGIN__
"""
    with open("dist/run.sh", "wb") as f:
        f.write(script.encode())
        with open(tar_name, "rb") as t:
            f.write(t.read())
            
    os.remove(tar_name)
    
    # Make executable
    st = os.stat("dist/run.sh")
    os.chmod("dist/run.sh", st.st_mode | stat.S_IEXEC)

    # Provide the icon in dist so pack_deb.py embeds it in the desktop file
    if os.path.exists("assets/icon.png"):
        shutil.copy2("assets/icon.png", "dist/icon.png")

build()
print("SConstruct completed successfully.")
