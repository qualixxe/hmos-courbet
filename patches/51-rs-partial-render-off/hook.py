"""Set render_service's partial render mode to DISABLED (0).

RS partial render (PartialRenderType 4 = SET_DAMAGE_AND_CLIP_AND_DROP_OP by
default) clips every frame to the computed damage region and publishes it with
eglSetDamageRegionKHR. Mesa's OHOS platform does not implement
set_damage_region (KHR_partial_update is forced off in
src/mesa/0001-mesa-ohos-platform-for-sweet.patch), so the call fails on every
frame while the canvas has already been clipped; any mismatch between buffer
age, dirty history and the real buffer content then shows up as corrupted
frames on the screen.

rosen.uni.partialrender.enabled=0 (plus the legacy rosen.partialrender.enabled)
makes RS redraw the full client target each frame and skip the damage/age
path entirely.

init loads param files with "first value wins" semantics, starting from the
highest-priority config directory, so the hook rewrites every definition it
can reach in the rebuilt partitions (system, vendor) and appends the pair to
a .para file when the parameters are not defined yet. Definitions in
partitions that are copied through unchanged are only reported in the build
log.
"""
import os

PARAMS = ("rosen.uni.partialrender.enabled", "rosen.partialrender.enabled")
VALUE = "0"
EDITABLE = ("system", "vendor")
READONLY = ("cust", "patch", "chip_prod", "sys_prod", "preload")
PARAM_DIR = "etc/param"


def _match(line, key):
    s = line.strip()
    return s == key or s.startswith(key + "=") or s.startswith(key + " ")


def _hits(text):
    found = []
    for line in text.splitlines():
        for key in PARAMS:
            if _match(line, key):
                found.append(key)
                break
    return found


def _force(text):
    out, n = [], 0
    for line in text.splitlines():
        for key in PARAMS:
            if _match(line, key):
                out.append("%s=%s" % (key, VALUE))
                n += 1
                break
        else:
            out.append(line)
    return "\n".join(out) + ("\n" if out else ""), n


def _walk(root):
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files):
            yield os.path.join(base, name)


def _image_files(ctx, part, rel):
    for name, is_dir in ctx.list_image_dir(part, rel):
        p = ("%s/%s" % (rel, name)).strip("/")
        if is_dir:
            for x in _image_files(ctx, part, p):
                yield x
        else:
            yield p


def apply(ctx):
    trees = {"system": ctx.system(), "vendor": ctx.vendor}
    forced = 0
    for part in EDITABLE:
        root = trees[part].path(PARAM_DIR)
        if not os.path.isdir(root):
            ctx.info("  /%s/%s does not exist" % (part, PARAM_DIR))
            continue
        for path in _walk(root):
            try:
                with open(path, "rb") as fh:
                    raw = fh.read()
            except OSError:
                continue
            text = raw.decode("utf-8", errors="replace")
            if not _hits(text):
                continue
            new, n = _force(text)
            rel = os.path.relpath(path, trees[part].path("")).replace(os.sep, "/")
            trees[part].write(rel, new.encode("utf-8"))
            forced += n
            ctx.info("  /%s/%s: %d definition(s) -> %s=%s" % (part, rel, n, ",".join(PARAMS), VALUE))
    for part in READONLY:
        if part not in ctx.images:
            continue
        for rel in _image_files(ctx, part, PARAM_DIR):
            raw = ctx.cat_image_file(part, rel)
            if not raw:
                continue
            for key in _hits(raw.decode("utf-8", errors="replace")):
                ctx.warn("  /%s/%s defines %s (partition copied unchanged, value kept)"
                         % (part, rel, key))
    if forced:
        ctx.info("  %d existing definition(s) forced to %s" % (forced, VALUE))
        return
    block = "".join("%s=%s\n" % (k, VALUE) for k in PARAMS)
    appended = []
    for part in EDITABLE:  # vendor first: config policy loads it before system
        tree = trees[part]
        target = None
        pdir = tree.path(PARAM_DIR)
        if os.path.isdir(pdir):
            for path in _walk(pdir):
                if path.endswith(".para"):
                    target = path
                    break
        if target:
            rel = os.path.relpath(target, tree.path("")).replace(os.sep, "/")
            cur = tree.read(rel).decode("utf-8", errors="replace")
            if cur and not cur.endswith("\n"):
                cur += "\n"
            tree.write(rel, (cur + block).encode("utf-8"))
            appended.append("/%s/%s" % (part, rel))
        else:
            rel = PARAM_DIR + "/sweet-rs.para"
            tree.write(rel, block.encode("utf-8"))
            appended.append("/%s/%s (new)" % (part, rel))
    ctx.info("  appended %s to %s" % ("; ".join("%s=%s" % (k, VALUE) for k in PARAMS),
                                      ", ".join(appended)))
