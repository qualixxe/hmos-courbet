#!/bin/bash
# Mesa 26.1 (freedreno on kgsl, OHOS EGL platform) -> patches/11-gpu-mesa/files.
# MESA_SRC: a Mesa 26.1-devel tree (tested: mesa-for-android-container-adreno, 26.1.0-devel).
# Needs: meson >= 1.4, ninja, python3-mako, python3-yaml, glslang (host), bison, flex.
set -e
. "$(dirname "$0")/env.sh"
O=$OH_SRC; M=$WORK/mesa-build; mkdir -p "$M/pc"
cd "$MESA_SRC"
patch -p1 -N --dry-run < "$REPO/src/mesa/0001-mesa-ohos-platform-for-sweet.patch" >/dev/null 2>&1 && \
  patch -p1 -N < "$REPO/src/mesa/0001-mesa-ohos-platform-for-sweet.patch"
pc() { printf 'Name: %s\nDescription: %s\nVersion: %s\nLibs: -L%s -l%s\nCflags: %s\n' "$1" "$1" "$2" "$SYSROOT/usr/lib" "$3" "$4" > "$M/pc/$1.pc"; }
pc libdrm 2.4.120 drm "-I$O/third_party_libdrm -I$O/third_party_libdrm/include/drm"
pc libhilog 1.0 hilog "-I$O/hiviewdfx_hilog/interfaces/native/innerkits/include"
pc libsurface 1.0 surface.z "-I$O/graphic_graphic_surface/interfaces/inner_api/surface -I$O/graphic_graphic_surface/interfaces/inner_api/utils -I$O/drivers_peripheral/display/interfaces/include -I$O/graphic_graphic_surface/interfaces/inner_api/common"
pc zlib 1.2.13 z "-I$SYSROOT/usr/include"
# create minimal libc.so / libc++.so stubs if missing (CI has no OTA images)
[ -f "$SYSROOT/usr/lib/libc.so" ] || { mkdir -p "$SYSROOT/usr/lib"; cat > "/tmp/libc_stub.c" <<'EOF'
#include <stddef.h>
void __libc_start_main(int (*main)(int, char**, char**), int argc, char** argv, void (*init)(void), void (*fini)(void), void (*rtld_fini)(void), void *stack_end) {}
int __libc_start_main(void) { return 0; }
void *memcpy(void *d, const void *s, size_t n) { return d; }
void *memset(void *d, int c, size_t n) { return d; }
size_t strlen(const char *s) { return 0; }
int strcmp(const char *a, const char *b) { return 0; }
int strncmp(const char *a, const char *b, size_t n) { return 0; }
EOF
"$REPO/build/ohos-clang" -shared -o "$SYSROOT/usr/lib/libc.so" "/tmp/libc_stub.c" -O2 -fPIC; }
[ -f "$SYSROOT/usr/lib/libc++.so" ] || { mkdir -p "$SYSROOT/usr/lib"; cat > "/tmp/libcpp_stub.cpp" <<'EOF'
void __gxx_personality_v0() {}
void *operator new(size_t s) { return NULL; }
void operator delete(void *p) {}
void *operator new[](size_t s) { return NULL; }
void operator delete[](void *p) {}
EOF
"$REPO/build/ohos-clang" -shared -o "$SYSROOT/usr/lib/libc++.so" "/tmp/libcpp_stub.cpp" -O2 -fPIC; }

# create stub .so files for Android libraries with real symbols
make_stub_so() {
    local name="$1"
    local out="$SYSROOT/usr/lib/lib${name}.so"
    if [ ! -f "$out" ]; then
        cat > "/tmp/${name}_stub.c" <<'EOF'
#include <stddef.h>
EOF
        case "$name" in
            cutils)
                cat >> "/tmp/${name}_stub.c" <<'EOF'
int property_get(const char *k, char *v, const char *d) { return 0; }
int property_set(const char *k, const char *v) { return -1; }
EOF
                ;;
            hardware)
                cat >> "/tmp/${name}_stub.c" <<'EOF'
int hw_get_module(const char *id, const void **m) { return -1; }
EOF
                ;;
            log)
                cat >> "/tmp/${name}_stub.c" <<'EOF'
int __android_log_print(int p, const char *t, const char *fmt, ...) { return 0; }
int __android_log_write(int p, const char *t, const char *m) { return 0; }
EOF
                ;;
            utils)
                cat >> "/tmp/${name}_stub.c" <<'EOF'
EOF
                ;;
            dl)
                cat >> "/tmp/${name}_stub.c" <<'EOF'
void *dlopen(const char *f, int flag) { return NULL; }
int dlclose(void *h) { return 0; }
void *dlsym(void *h, const char *s) { return NULL; }
char *dlerror(void) { return (char *)""; }
EOF
                ;;
            sync)
                cat >> "/tmp/${name}_stub.c" <<'EOF'
int sync_wait(int fd, int timeout) { return -1; }
int sync_merge(const char *name, int fd1, int fd2) { return -1; }
EOF
                ;;
            nativewindow)
                cat >> "/tmp/${name}_stub.c" <<'EOF'
void *ANativeWindow_acquire(void *w) { return w; }
void ANativeWindow_release(void *w) {}
int ANativeWindow_getWidth(void *w) { return 0; }
int ANativeWindow_getHeight(void *w) { return 0; }
int ANativeWindow_getFormat(void *w) { return 0; }
int ANativeWindow_getStride(void *w) { return 0; }
int ANativeWindow_setBuffersGeometry(void *w, int w_, int h, int f) { return -1; }
int ANativeWindow_setBuffersTransform(void *w, int t) { return -1; }
int ANativeWindow_setBuffersTimestamp(void *w, long long t) { return -1; }
int ANativeWindow_setScalingMode(void *w, int m) { return -1; }
int ANativeWindow_lock(void *w, void **b, void *r) { return -1; }
int ANativeWindow_unlockAndPost(void *w) { return -1; }
int ANativeWindow_dequeueBuffer(void *w, void **b) { return -1; }
int ANativeWindow_queueBuffer(void *w, void *b) { return -1; }
EOF
                ;;
            atomic)
                cat >> "/tmp/${name}_stub.c" <<'EOF'
int atomic_fetch_add(volatile int *p, int v) { return 0; }
int atomic_fetch_sub(volatile int *p, int v) { return 0; }
int atomic_fetch_or(volatile int *p, int v) { return 0; }
int atomic_fetch_and(volatile int *p, int v) { return 0; }
int atomic_fetch_xor(volatile int *p, int v) { return 0; }
int atomic_load(volatile int *p) { return 0; }
int atomic_store(volatile int *p, int v) { return 0; }
int atomic_exchange(volatile int *p, int v) { return v; }
int atomic_compare_exchange_strong(volatile int *p, int *e, int d) { return 0; }
EOF
                ;;
        esac
        "$REPO/build/ohos-clang" -shared -o "$out" "/tmp/${name}_stub.c" -O2 -fPIC
    fi
}
make_stub_so cutils
make_stub_so hardware
make_stub_so log
make_stub_so utils
make_stub_so dl
make_stub_so sync
make_stub_so nativewindow
make_stub_so atomic
cat > "$M/cross.ini" <<EOC
[binaries]
c = '$REPO/build/ohos-clang'
cpp = '$REPO/build/ohos-clang++'
ar = 'ar'
strip = 'strip'
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
meson setup "$M/b" --cross-file "$M/cross.ini" --buildtype=release -Dplatforms=android -Degl-native-platform=android \
  -Dandroid-stub=false -Dgallium-drivers=freedreno,softpipe -Dvulkan-drivers= -Dfreedreno-kmds=kgsl \
  -Dgles1=enabled -Dgles2=enabled -Dopengl=false -Dgbm=disabled -Dglx=disabled -Degl=enabled -Dllvm=disabled \
  --reconfigure 2>/dev/null || meson setup "$M/b" --cross-file "$M/cross.ini" --buildtype=release -Dplatforms=android \
  -Degl-native-platform=android -Dandroid-stub=false -Dgallium-drivers=freedreno,softpipe -Dvulkan-drivers= \
  -Dfreedreno-kmds=kgsl -Dgles1=enabled -Dgles2=enabled -Dopengl=false -Dgbm=disabled -Dglx=disabled -Degl=enabled -Dllvm=disabled
ninja -C "$M/b"
F=$REPO/patches/11-gpu-mesa/files/lib64/chipsetsdk
llvm-strip -o "$F/libEGL_impl.so" "$(find "$M/b" -name 'libEGL.so*' -type f | head -1)"
llvm-strip -o "$F/libGLESv1_impl.so" "$(find "$M/b" -name 'libGLESv1_CM.so*' -type f | head -1)"
llvm-strip -o "$F/libGLESv2_impl.so" "$(find "$M/b" -name 'libGLESv2.so*' -type f | head -1)"
cp "$F/libGLESv2_impl.so" "$F/libGLESv3_impl.so"
llvm-strip -o "$F/libgallium-26.1.0-devel.so" "$(find "$M/b" -name 'libgallium-*.so' -type f | head -1)"
echo "Mesa -> $F"
