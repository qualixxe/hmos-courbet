# -*- coding: utf-8 -*-
"""Build flash/no-setup-wizard.zip from the files in this directory."""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.normpath(os.path.join(
    HERE, "..", "..", "patches", "50-remove-setup-wizard", "files", "bin", "sweet-oobedone"))
OUT = os.path.normpath(os.path.join(HERE, "..", "no-setup-wizard.zip"))


def add(z, path, arc, executable=False):
    info = zipfile.ZipInfo(arc)
    info.date_time = (2024, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (0o100755 if executable else 0o100644) << 16
    with open(path, "rb") as f:
        z.writestr(info, f.read())


with zipfile.ZipFile(OUT, "w") as z:
    add(z, os.path.join(HERE, "update-binary"),
        "META-INF/com/google/android/update-binary", executable=True)
    add(z, os.path.join(HERE, "updater-script"),
        "META-INF/com/google/android/updater-script")
    add(z, BIN, "sweet-oobedone", executable=True)

print("%s = %d bytes" % (OUT, os.path.getsize(OUT)))
