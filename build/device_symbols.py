#!/usr/bin/env python3
"""Write build/device-symbols/*.txt: the exports of the HarmonyOS libraries the
shipped Mesa objects import from, read straight out of the OTA images.

check_mesa_deps.py treats these lists as the only truth about what the device
loader can resolve; qsort_r was not there and blackened the screen, while the
link-time stubs had it.  The lists must be rebuilt whenever the Mesa imports
change, so they live in git and are produced by CI, the only place the real
images are at hand.

The images are unpacked whole: guessing at directory layouts blew up twice
(extract.erofs leaves symlinks dangling, and libdrm.so is not under the
lib64/ names one expects), while a tree walk finds a library wherever the image
keeps it and can follow its symlinks on disk.

usage: device_symbols.py <update_full_base.zip | update.bin> [work dir]
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import hwota  # noqa: E402
from lib.util import Fatal, die, info, mkdirs, tool  # noqa: E402

OUT = os.path.join("build", "device-symbols")

# (library, published list) -- the five DT_NEEDED targets of the Mesa objects
# that come from the device, see check_mesa_deps.py.  Copies found in either
# image are merged: they are one build of the library, and the gate only asks
# whether the device can resolve an import at all.
WANT = [
    ("libc.so", "libc"),
    ("libc++.so", "libcxx"),
    ("libdrm.so", "libdrm"),
    ("libsurface.z.so", "libsurface"),
    ("libshared_libz.z.so", "libz"),
]

COMPONENTS = ("system", "vendor")


def image_tree(image, workdir):
    """Root of the extracted image (extract.erofs names it after the image)."""
    out = mkdirs(workdir)
    subprocess.run([tool("extract.erofs"), "-i", image, "-x", "-o", out, "-s", "-f", "-T4"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    produced = [os.path.join(out, d) for d in sorted(os.listdir(out))]
    produced = [d for d in produced if os.path.isdir(d)]
    if len(produced) != 1:
        die("extract.erofs did not unpack %s" % image)
    return produced[0]


def find_hits(root, name):
    """Paths relative to the image root of every entry with this name."""
    hits = []
    for r, _, files in os.walk(root):
        if name in files:
            hits.append(os.path.relpath(os.path.join(r, name), root).replace("\\", "/"))
    return sorted(hits)


def read_following_links(image, root, rel):
    """Bytes of one entry, following symlinks inside the extracted tree.

    An absolute target may carry the mount point that the image root already
    stands for ("/vendor/lib64/x" inside vendor.img), so the spelling without
    it is tried too.
    """
    mount = os.path.splitext(os.path.basename(image))[0]
    p = os.path.join(root, rel)
    for _ in range(8):
        if not os.path.islink(p):
            if not os.path.isfile(p):
                return None
            with open(p, "rb") as fh:
                return fh.read()
        target = os.readlink(p)
        if os.path.isabs(target):
            t = target.lstrip("/")
            cands = [t] + ([t[len(mount) + 1:]] if t.startswith(mount + "/") else [])
            nxt = next((c for c in cands if os.path.lexists(os.path.join(root, c))), None)
            if nxt is None:
                return None
            p = os.path.join(root, nxt)
        else:
            p = os.path.normpath(os.path.join(os.path.dirname(p), target))
    return None


def symbols_of(path):
    out = subprocess.run(["nm", "-D", "--defined-only", path],
                         stdout=subprocess.PIPE, universal_newlines=True).stdout
    return {p[2].split("@")[0]
            for p in (l.split(None, 3) for l in out.splitlines()) if len(p) > 2}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip().splitlines()[-1])
        return 0 if len(sys.argv) > 1 else 1
    work = sys.argv[2] if len(sys.argv) > 2 else "work"
    ota = hwota.HwOta(sys.argv[1])
    imgs = ota.extract(list(COMPONENTS), mkdirs(os.path.join(work, "ota")))
    for comp in COMPONENTS:
        if comp not in imgs:
            die("the OTA has no %s image: not a full HarmonyOS phone package?" % comp)

    roots = {}

    def root_of(comp):
        if comp not in roots:
            roots[comp] = image_tree(imgs[comp], os.path.join(work, "tree-" + comp))
            info("unpacked %s -> %s" % (os.path.basename(imgs[comp]), roots[comp]))
        return roots[comp]

    mkdirs(OUT)
    mkdirs(os.path.join(work, "symtmp"))
    for name, stem in WANT:
        syms, found = set(), []
        for comp in COMPONENTS:
            root = root_of(comp)
            for rel in find_hits(root, name):
                data = read_following_links(imgs[comp], root, rel)
                if not data or data[:4] != b"\x7fELF":
                    info("  %s:%s is not a 64-bit ELF, skipped" % (comp, rel))
                    continue
                tmp = os.path.join(work, "symtmp", stem + ".so")
                with open(tmp, "wb") as fh:
                    fh.write(data)
                got = symbols_of(tmp)
                if not got:
                    info("  %s:%s exported no symbols, skipped" % (comp, rel))
                    continue
                found.append("%s:%s (%d)" % (comp, rel, len(got)))
                syms |= got
        if not syms:
            die("%s not found as an ELF in any of the OTA images (%s)"
                % (name, ", ".join(COMPONENTS)))
        with open(os.path.join(OUT, stem + ".txt"), "w") as fh:
            fh.write("\n".join(sorted(syms)) + "\n")
        info("%-12s %5d symbols  %s" % (stem, len(syms), "  ".join(found)))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fatal as e:
        print("ERROR: %s" % e, file=sys.stderr)
        sys.exit(1)
