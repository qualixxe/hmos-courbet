#!/usr/bin/env python3
"""Write build/device-symbols/*.txt: the exports of the HarmonyOS libraries the
shipped Mesa objects import from, read straight out of the OTA images.

check_mesa_deps.py treats these lists as the only truth about what the device
loader can resolve; qsort_r was not there and blackened the screen, while the
link-time stubs had it.  The lists must be rebuilt whenever the Mesa imports
change, so they live in git and are produced by CI, the only place the real
images are at hand.

usage: device_symbols.py <update_full_base.zip | update.bin> [work dir]
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import erofs, hwota  # noqa: E402
from lib.util import Fatal, die, info, mkdirs, rmtree, tool  # noqa: E402

OUT = os.path.join("build", "device-symbols")

# (component, library, published list) -- the five DT_NEEDED targets of the
# Mesa objects that come from the device, see check_mesa_deps.py.
WANT = [
    ("system", "libc.so", "system-libc"),
    ("system", "libc++.so", "system-libcxx"),
    ("vendor", "libdrm.so", "vendor-libdrm"),
    ("vendor", "libsurface.z.so", "vendor-libsurface"),
    ("vendor", "libshared_libz.z.so", "vendor-libz"),
]

# system-as-root images keep lib64 under "system/", vendor images at the root;
# chipsetsdk/hw hold the vendor copies of some of them.
DIRS = ["system/lib64", "lib64", "system/lib64/chipsetsdk", "lib64/chipsetsdk",
        "system/lib64/ndk", "lib64/ndk", "system/lib64/hw", "lib64/hw"]


def locate(image, name):
    for d in DIRS:
        if any(n == name and not is_dir for n, is_dir in erofs.list_dir(image, d)):
            return d + "/" + name
    return None


def extract_one(image, path, tmp):
    """Where extract.erofs put one entry, None if it did not come out."""
    subprocess.run([tool("extract.erofs"), "-i", image, "-X", "/" + path.strip("/"),
                    "-o", tmp, "-s", "-f"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    want = os.path.dirname("/" + path.strip("/"))
    for r, _, files in os.walk(tmp):
        if os.path.basename(path) in files and r.replace("\\", "/").endswith(want):
            return os.path.join(r, os.path.basename(path))
    return None


def read_elf(image, path, workdir):
    """Bytes of one file, following symlinks inside the image.

    extract.erofs copies a symlink as a symlink and leaves its target behind,
    so /system/lib64/libc.so (-> ld-musl-aarch64.so.1) came out dangling and
    open() failed with ENOENT; walk the chain here instead.  A target may be
    relative, image-absolute, or carry the mount point ("/vendor/lib64/..." in
    vendor.img), so a couple of spellings are tried per hop.
    """
    mount = os.path.splitext(os.path.basename(image))[0]
    tmp = mkdirs(os.path.join(workdir, "one"))
    try:
        for _ in range(8):
            p = extract_one(image, path, tmp)
            if not p and path.startswith(mount + "/"):
                path = path[len(mount) + 1:]
                p = extract_one(image, path, tmp)
            if not p:
                alt = locate(image, os.path.basename(path))
                if not alt:
                    return None
                path, p = alt, extract_one(image, alt, tmp)
            if not p:
                return None
            if not os.path.islink(p):
                with open(p, "rb") as fh:
                    return fh.read()
            target = os.readlink(p)
            path = (target.lstrip("/") if target.startswith("/")
                    else os.path.dirname(path) + "/" + target)
            path = os.path.normpath(path)
            rmtree(tmp)
            mkdirs(tmp)
    finally:
        rmtree(tmp)
    return None


def symbols(elf_path):
    out = subprocess.run(["nm", "-D", "--defined-only", elf_path],
                         stdout=subprocess.PIPE, universal_newlines=True).stdout
    return sorted({p[2].split("@")[0]
                   for p in (l.split(None, 3) for l in out.splitlines()) if len(p) > 2})


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip().splitlines()[-1])
        return 0 if len(sys.argv) > 1 else 1
    work = sys.argv[2] if len(sys.argv) > 2 else "work"
    ota = hwota.HwOta(sys.argv[1])
    imgs = ota.extract(["system", "vendor"], mkdirs(os.path.join(work, "ota")))
    for comp in ("system", "vendor"):
        if comp not in imgs:
            die("the OTA has no %s image: not a full HarmonyOS phone package?" % comp)
    mkdirs(OUT)
    mkdirs(os.path.join(work, "symtmp"))
    for comp, name, stem in WANT:
        image = imgs[comp]
        path = locate(image, name)
        if not path:
            die("%s not found in %s (%s)" % (name, image, ", ".join(DIRS)))
        data = read_elf(image, path, work)
        if not data or data[:4] != b"\x7fELF":
            die("%s:/%s did not read back as a 64-bit ELF" % (image, path))
        tmp = os.path.join(work, "symtmp", stem)
        with open(tmp, "wb") as fh:
            fh.write(data)
        syms = symbols(tmp)
        if not syms:
            die("nm returned no symbols for %s:/%s" % (image, path))
        with open(os.path.join(OUT, stem + ".txt"), "w") as fh:
            fh.write("\n".join(syms) + "\n")
        info("%-16s %5d symbols  %s:/%s" % (stem, len(syms), os.path.basename(image), path))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fatal as e:
        print("ERROR: %s" % e, file=sys.stderr)
        sys.exit(1)
