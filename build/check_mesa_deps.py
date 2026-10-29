#!/usr/bin/env python3
"""Check that the Mesa drivers built by build_mesa.sh can be loaded on device.

The five shipped objects import their drm, surface and zlib calls from the
HarmonyOS libraries named in DT_NEEDED.  Nothing else is consulted at runtime,
so a missing entry surfaces only after the phone has been reflashed --
"relocating failed: symbol not found ... libEGL_impl.so s=drmFreeDevice" and a
black screen.  An extra entry is equally fatal when the vendor namespace has no
such library.  Both come from how the link stubs are declared, so assert the
result here instead.

usage: check_mesa_deps.py <directory with libEGL_impl.so and friends>
"""

import os
import struct
import sys

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
    """Return (DT_NEEDED names, undefined symbol names) of an ELF shared object."""
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
    undef = []
    for i in range(sym[5] // entsize):
        p = sym[4] + i * entsize
        st_name = struct.unpack_from("<I", d, p)[0]
        st_shndx = struct.unpack_from("<H", d, p + 6)[0]
        if st_shndx == 0 and st_name:
            undef.append(strtab(st_name))
    return needed, undef


def main(directory):
    problems = []
    for fn, required in REQUIRED.items():
        path = os.path.join(directory, fn)
        if not os.path.exists(path):
            problems.append(f"{fn}: not produced by the build")
            continue
        needed, undef = dynamic(path)
        missing = required - set(needed)
        unexpected = set(needed) - ALLOWED
        for lib in sorted(missing):
            names = stranded(lib, undef)
            problems.append(f"{fn}: DT_NEEDED lacks {lib}, which should supply "
                            f"{len(names)} imports"
                            + (f" ({', '.join(names[:3])}, ...)" if names else ""))
        if unexpected:
            problems.append(f"{fn}: DT_NEEDED has {sorted(unexpected)}, "
                            "which the vendor namespace does not carry")
        print(f"{fn}: NEEDED {needed}")
    for p in problems:
        print(f"ERROR: {p}", file=sys.stderr)
    if problems:
        return 1
    print("DT_NEEDED of all five objects matches what the device can resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
