#!/bin/bash
# Mesa (freedreno on kgsl, OHOS EGL platform) -> patches/11-gpu-mesa/files.
# MESA_SRC: a Mesa tree with the OHOS patch (tested: mesa main, 27.0.0-devel).
# Needs: meson >= 1.4, ninja, python3-mako, python3-yaml, bison, flex, cross binutils.
set -e
. "$(dirname "$0")/env.sh"
O=$OH_SRC; M=$WORK/mesa-build
rm -rf "$M"; mkdir -p "$M/pc" "$SYSROOT/usr/lib"
cd "$MESA_SRC"

P="$REPO/src/mesa/0001-mesa-ohos-platform-for-sweet.patch"
patch -p1 -N --dry-run < "$P" >/dev/null 2>&1 || {
  echo "ERROR: mesa patch does not apply to $MESA_SRC"; exit 1; }
patch -p1 -N < "$P"
grep -q 'with_platform_ohos' meson.build || { echo "ERROR: meson.build not patched"; exit 1; }
[ -f src/egl/drivers/dri2/platform_ohos.c ] || { echo "ERROR: platform_ohos.c missing"; exit 1; }
grep -q "'ohos'" meson.options || { echo "ERROR: meson.options not patched"; exit 1; }

# ---------------------------------------------------------------- pkg-config
# The CI runner has no HarmonyOS sysroot, so describe the device libraries
# ourselves.  Names must match the ones the stock HarmonyOS 5 userspace uses.
pc() { printf 'Name: %s\nDescription: %s\nVersion: %s\nLibs: -L%s -l%s\nCflags: %s\n' \
       "$1" "$1" "$2" "$SYSROOT/usr/lib" "$3" "$4" > "$M/pc/$1.pc"; }
pc libdrm 2.4.120 drm "-I$O/third_party_libdrm -I$O/third_party_libdrm/include/drm"
pc libhilog 1.0 hilog "-I$O/hiviewdfx_hilog/interfaces/native/innerkits/include"
pc libsurface 1.0 surface.z "-I$O/graphic_graphic_surface/interfaces/inner_api/surface -I$O/graphic_graphic_surface/interfaces/inner_api/utils -I$O/drivers_peripheral/display/interfaces/include -I$O/graphic_graphic_surface/interfaces/inner_api/common"
pc zlib 1.2.13 shared_libz.z "-I$SYSROOT/usr/include"

# ------------------------------------------------------- stub shared objects
# Link-time only: the device provides the real libraries.  Every stub carries
# the SONAME of the device library so DT_NEEDED entries stay valid on device.
printf 'void mesa_build_link_stub(void) {}\n' > "$M/stub.c"
stub_so() {
  local out="$SYSROOT/usr/lib/$1"
  [ -f "$out" ] && return 0
  "$REPO/build/ohos-clang" -shared -Wl,-soname,"$1" -o "$out" "$M/stub.c" -O2 -fPIC
}
for l in libdrm.so libsurface.z.so libhilog.so libshared_libz.z.so libdl.so \
         librt.so libm.so libpthread.so libz.so \
         libcutils.so libhardware.so liblog.so libutils.so libsync.so \
         libnativewindow.so libatomic.so; do
  stub_so "$l"
done

# libc: meson runs compile+link sanity checks, so the stub needs the crt entry
# point and a few libc symbols the test programs reference.
if [ ! -f "$SYSROOT/usr/lib/libc.so" ]; then
  cat > "$M/libc_stub.c" <<'EOF'
#include <stddef.h>
void __libc_start_main(int (*main)(int, char **, char **), int argc, char **argv,
                       void (*init)(void), void (*fini)(void),
                       void (*rtld_fini)(void), void *stack_end) {}
void *memcpy(void *d, const void *s, size_t n) { return d; }
void *memmove(void *d, const void *s, size_t n) { return d; }
void *memset(void *d, int c, size_t n) { return d; }
int memcmp(const void *a, const void *b, size_t n) { return 0; }
size_t strlen(const char *s) { return 0; }
int strcmp(const char *a, const char *b) { return 0; }
int strncmp(const char *a, const char *b, size_t n) { return 0; }
int clock_gettime(int clk_id, void *tp) { return 0; }
int dl_iterate_phdr(void *cb, void *data) { return 0; }
void exit(int code) { for (;;) {} }
void abort(void) { for (;;) {} }
EOF
  "$REPO/build/ohos-clang" -fno-builtin -shared -Wl,-soname,libc.so \
    -o "$SYSROOT/usr/lib/libc.so" "$M/libc_stub.c" -O2 -fPIC
fi

# libc++: only operator new/delete are needed by the C++ link checks.
if [ ! -f "$SYSROOT/usr/lib/libc++.so" ]; then
  cat > "$M/libcxx_stub.cpp" <<'EOF'
#include <cstddef>
void *operator new(std::size_t) { return nullptr; }
void *operator new[](std::size_t) { return nullptr; }
void operator delete(void *) noexcept {}
void operator delete[](void *) noexcept {}
void operator delete(void *, std::size_t) noexcept {}
void operator delete[](void *, std::size_t) noexcept {}
EOF
  "$REPO/build/ohos-clang++" -fno-exceptions -fno-rtti -shared -Wl,-soname,libc++.so \
    -o "$SYSROOT/usr/lib/libc++.so" "$M/libcxx_stub.cpp" -O2 -fPIC
fi

# ------------------------------------------------------------- cross file
cat > "$M/cross.ini" <<EOC
[binaries]
c = '$REPO/build/ohos-clang'
cpp = '$REPO/build/ohos-clang++'
ar = 'ar'
strip = '${CROSS_STRIP:-aarch64-linux-gnu-strip}'
pkgconfig = 'pkg-config'
[built-in options]
c_args = ['-O2', '-fno-emulated-tls', '-Wno-error', '-Wno-int-conversion', '-Wno-incompatible-function-pointer-types', '-DHAVE_OHOS_PLATFORM']
cpp_args = ['-O2', '-fno-emulated-tls', '-Wno-error']
c_link_args = ['-Wl,--undefined-version', '$SYSROOT/usr/lib/libc.so']
cpp_link_args = ['-Wl,--undefined-version', '$SYSROOT/usr/lib/libc++.so', '$SYSROOT/usr/lib/libc.so']
[properties]
needs_exe_wrapper = true
pkg_config_libdir = '$M/pc'
[host_machine]
system = 'linux'
cpu_family = 'aarch64'
cpu = 'armv8-a'
endian = 'little'
EOC

# ---------------------------------------------------------------- configure
meson setup "$M/b" --cross-file "$M/cross.ini" --buildtype=release \
  -Dplatforms=ohos -Degl-native-platform=ohos \
  -Dgallium-drivers=freedreno,softpipe -Dvulkan-drivers= -Dfreedreno-kmds=kgsl \
  -Dgles1=enabled -Dgles2=enabled -Dopengl=false -Dgbm=disabled -Dglx=disabled \
  -Degl=enabled -Dllvm=disabled -Dandroid-stub=false -Dunversion-libgallium=true \
  -Dglvnd=disabled -Ddisplay-info=disabled

ninja -C "$M/b"

# ------------------------------------------------------------------ install
STRIP=${CROSS_STRIP:-aarch64-linux-gnu-strip}
F=$REPO/patches/11-gpu-mesa/files/lib64/chipsetsdk
mkdir -p "$F"
pick() { find "$M/b" -name "$1" -type f | head -1; }
"$STRIP" -o "$F/libEGL_impl.so"      "$(pick 'libEGL.so')"
"$STRIP" -o "$F/libGLESv1_impl.so"   "$(pick 'libGLESv1_CM.so')"
"$STRIP" -o "$F/libGLESv2_impl.so"   "$(pick 'libGLESv2.so')"
cp "$F/libGLESv2_impl.so" "$F/libGLESv3_impl.so"
"$STRIP" -o "$F/libgallium_dri.so"   "$(pick 'libgallium_dri.so')"
rm -f "$F"/libgallium-*.so
echo "Mesa -> $F"
ls -l "$F"
