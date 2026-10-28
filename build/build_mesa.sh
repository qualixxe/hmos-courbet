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
# create minimal libc.so stub if missing (CI has no OTA images to extract it from)
[ -f "$SYSROOT/usr/lib/libc.so" ] || { mkdir -p "$SYSROOT/usr/lib"; touch "$SYSROOT/usr/lib/libc.so"; }
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
c_link_args = ['-Wl,--no-undefined', '-Wl,--undefined-version', '$SYSROOT/usr/lib/libc.so']
cpp_link_args = ['-Wl,--no-undefined', '-Wl,--undefined-version', '$SYSROOT/usr/lib/libc++.so', '$SYSROOT/usr/lib/libc.so']
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
