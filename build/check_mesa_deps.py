#!/usr/bin/env python3
"""Check that the Mesa drivers built by build_mesa.sh can be loaded on device.

Two failure modes have already cost a reflash and a black screen:

  * a DT_NEEDED entry missing because --as-needed dropped it
    ("relocating failed: symbol not found ... libEGL_impl.so s=drmFreeDevice");
  * an import that the HarmonyOS musl libc does not export
    ("... libgallium_dri.so s=qsort_r").

The first is checked against REQUIRED below.  The second needs to know what the
device actually exports, so build-hmos.yml publishes `nm -D` dumps of the
HarmonyOS libraries into build/device-symbols/ and every strong undefined
symbol here must be defined by one of those or by another shipped object.
Weak imports are skipped: the loader resolves them to zero instead of failing.

usage: check_mesa_deps.py <directory with libEGL_impl.so and friends>
"""

import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# What each object must ask the loader for.
REQUIRED = {
    "libEGL_impl.so": {"libc.so", "libgallium_dri.so", "libsurface.z.so", "libdrm.so"},
    "libgallium_dri.so": {"libc.so", "libc++.so", "libdrm.so", "libshared_libz.z.so"},
    "libGLESv1_impl.so": {"libgallium_dri.so"},
    "libGLESv2_impl.so": {"libgallium_dri.so"},
    "libGLESv3_impl.so": {"libgallium_dri.so"},
}

# Every library the vendor/chipsetsdk namespace is known to resolve.  musl keeps
# math, threads and dl inside libc.so, so libm.so, libpthread.so and friends
# must never be referenced.
ALLOWED = set().union(*REQUIRED.values()) | {
    "libc++.so", "libEGL.so.1", "libGLESv1_CM.so.1", "libGLESv2.so.2",
    "libhilog.so", "libnative_window.so", "libsync_fence.z.so",
    "libdmabufheap.z.so", "libutils.z.so",
}

# The device libraries whose export lists build-hmos.yml publishes, and the
# file stem each list is stored under.
DEVICE_LIBS = {
    "libc.so": "system-libc",
    "libc++.so": "system-libcxx",
    "libdrm.so": "vendor-libdrm",
    "libsurface.z.so": "vendor-libsurface",
    "libshared_libz.z.so": "vendor-libz",
}

# The symbol families each HarmonyOS library is expected to supply, used only to
# report a missing DT_NEEDED entry in terms of the imports it strands.
PROVIDES = {
    "libdrm.so": ("drm",),
    "libsurface.z.so": ("Native", "GetBufferHandleFromNative"),
    "libshared_libz.z.so": ("crc32", "deflate", "inflate", "gz", "adler", "zlib"),
}


def stranded(lib, undef):
    prefixes = PROVIDES.get(lib)
    return sorted(s for s in undef if prefixes and s.startswith(prefixes))


def dynamic(fn):
    """(DT_NEEDED names, [(undefined name, binding)], {defined name}) of an ELF."""
    d = open(fn, "rb").read()
    if d[:4] != b"\x7fELF" or d[4] != 2:
        raise ValueError(f"{fn}: not a 64-bit ELF")
    shoff = struct.unpack_from("<Q", d, 0x28)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x3a)
    secs = [struct.unpack_from("<IIQQQQIIQQ", d, shoff + i * shentsize) for i in range(shnum)]
    strbase = secs[shstrndx][4]
    name = lambda i: d[strbase + i:d.index(b"\0", strbase + i)].decode()  # noqa: E731
    by = {name(s[0]): s for s in secs}
    if ".dynsym" not in by:
        raise ValueError(f"{fn}: no dynamic symbol table")
    dynstr = by[".dynstr"][4]
    strtab = lambda i: d[dynstr + i:d.index(b"\0", dynstr + i)].decode()  # noqa: E731

    needed = []
    dyn = by[".dynamic"]
    for off in range(dyn[4], dyn[4] + dyn[5], 16):
        tag, val = struct.unpack_from("<QQ", d, off)
        if tag == 0:
            break
        if tag == 1:
            needed.append(strtab(val))

    sym = by[".dynsym"]
    entsize = sym[9] or 24
    undef, defined = [], set()
    for i in range(sym[5] // entsize):
        p = sym[4] + i * entsize
        st_name = struct.unpack_from("<I", d, p)[0]
        st_info = d[p + 4]
        st_shndx = struct.unpack_from("<H", d, p + 6)[0]
        if not st_name:
            continue
        s = strtab(st_name)
        if st_shndx == 0:
            undef.append((s, st_info >> 4))
        else:
            defined.add(s)
    return needed, undef, defined


def device_symbols():
    """{lib name: defined symbol set}, from the lists build-hmos.yml publishes."""
    lists, missing = {}, []
    for lib, stem in DEVICE_LIBS.items():
        path = os.path.join(HERE, "device-symbols", stem + ".txt")
        if not os.path.exists(path):
            missing.append(os.path.relpath(path))
            continue
        with open(path) as fh:
            lists[lib] = {line.strip() for line in fh if line.strip()}
    if missing:
        raise SystemExit(
            "ERROR: no device symbol lists: " + ", ".join(missing) +
            "\nRun the 'Build HarmonyOS for Courbet' workflow once; it publishes "
            "them from the ROM it builds.")
    return lists


def main(directory):
    problems = []
    objects = {}
    for fn, required in REQUIRED.items():
        path = os.path.join(directory, fn)
        if not os.path.exists(path):
            problems.append(f"{fn}: not produced by the build")
            continue
        objects[fn] = dynamic(path)

    device = device_symbols()
    supplied = set().union(*[o[2] for o in objects.values()])
    for fn, (needed, undef, _) in objects.items():
        missing = REQUIRED[fn] - set(needed)
        unexpected = set(needed) - ALLOWED
        for lib in sorted(missing):
            names = stranded(lib, [u[0] for u in undef])
            problems.append(f"{fn}: DT_NEEDED lacks {lib}, which should supply "
                            f"{len(names)} imports"
                            + (f" ({', '.join(names[:3])}, ...)" if names else ""))
        if unexpected:
            problems.append(f"{fn}: DT_NEEDED has {sorted(unexpected)}, "
                            "which the vendor namespace does not carry")

        unexported = []
        for sym, bind in undef:
            if bind == 2 or sym in supplied:  # WEAK is never fatal at load time
                continue
            if not any(sym in syms for syms in device.values()):
                unexported.append(sym)
        if unexported:
            problems.append(f"{fn}: imports {len(unexported)} symbols that neither "
                            "the shipped objects nor the HarmonyOS libraries define: "
                            + ", ".join(sorted(unexported)[:8])
                            + (" ..." if len(unexported) > 8 else ""))
        print(f"{fn}: NEEDED {needed}, {len(undef)} imports checked")
    for p in problems:
        print(f"ERROR: {p}", file=sys.stderr)
    if problems:
        return 1
    print("DT_NEEDED and every import of the five objects match the device.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
