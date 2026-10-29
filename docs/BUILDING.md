# Rebuilding the binaries

`hmos2sweet.py` uses the binaries already built in `prebuilt/` and `patches/*/files/`. Rebuilding them is only
needed if you change the sources in `src/`. All scripts are in `build/` and read their settings from
`build/env.sh`.

| Script | Produces | Needs |
|---|---|---|
| `build_kernel.sh` | `prebuilt/kernel/{Image.gz,xiaomi-sdmmagpie.dtb,dtbo.img}` | clang/lld 15+, `aarch64-linux-gnu-` and `arm-linux-gnueabi-` binutils |
| `build_static.sh` | hmos-preinit, sweet-rproc, qrtr/rmtfs/tqftpserv/pd-mapper, sweet-oobedone, sqlite3, CameraDaemon placeholder | `aarch64-linux-gnu-gcc` (static glibc) |
| `fetch_oh_sources.sh` | OpenHarmony 5.1 sources (HDI/HDF headers, HUKS, OpenSSL) | git |
| `make_sysroot.sh <work>` | HarmonyOS sysroot for `ohos-clang` | an hmos2sweet `work` folder (`ota/system.img`, `ota/vendor.img`) |
| `build_ohos.sh` | composer + allocator, audio, user_auth, HUKS, sensors, RIL, GNSS, IR | clang/lld, llvm-strip, sysroot, OH sources |
| `build_iam.sh` | OpenHarmony REE user_auth / pin_auth HDI services (patch 46) | as above + hdi-gen output for user_auth/pin_auth |
| `build_camera_android.sh` | cambridge (bionic) + sweetcam-launch (static), patch 47 | clang/lld, AOSP headers in `$AOSP`, bionic runtime of a sweet ROM in `$ANDROID_LIBS` + crt objects in `$ANDROID_CRT` |
| `build_mesa.sh` | Mesa (EGL/GLES + gallium freedreno) | meson, ninja, python3-mako/yaml, `MESA_SRC` (Mesa 26.1.x, CI pins `mesa-26.1.8`) |
| `build_all.sh <work>` | everything above | |

## Notes

- **`ohos-clang`** builds for `aarch64-linux-ohos` (OpenHarmony's musl). It uses libc++ with the `__h` ABI
  namespace, the same as HarmonyOS, so the binaries link against the phone's system libraries.
- **Sysroot**:
  - headers and crt objects come from `build/sysroot-base.tar.xz` (musl, libc++, Linux UAPI, libdrm, all open
    source);
  - the `.so` libraries to link against are copied from the OTA images, which is why `make_sysroot.sh` wants the
    `work` folder of a conversion.
- **Kernel**: LineageOS `android_kernel_xiaomi_sm6150`, branch `lineage-24.0`, commit `e03e5ba22`, with
  `vendor/sdmsteppe-perf_defconfig vendor/sweet.config vendor/ohos.config`.
- **Mesa**: `src/mesa/0001-mesa-ohos-platform-for-sweet-26.1.patch` is generated against the `mesa-26.1.8` tag and
  the CI pins that tag (`MESA_REF`). Mesa master moves the DRI2 loader API (`dri_loader_funcs`,
  `dri2_egl_display.has_native_fence_fd`, swap-buffers signature) under the port, so do not build against `main`.
  `src/mesa/0001-mesa-ohos-platform-for-sweet.patch` is the older master-port, kept for reference.
- **Camera (work in progress)**: `src/camera/bridge/cambridge.c` is built for Android (bionic) with clang
  `--target=aarch64-linux-android33`, the AOSP bionic/libhardware/system_core/system_media headers and linked
  against the bionic libraries of a sweet Android ROM; `src/camera/launcher` is a static glibc binary.

## Adding a patch

1. Create `patches/NN-name/patch.json` with:
   - `name`, `description`, `default`;
   - `requires` for dependencies;
   - the actions: `vendor_files` (`src`/`dst`/`mode`), `vendor_dirs`, `vendor_remove`, `system_remove`,
     `sweet_blobs` (`from`/`to`, trailing `/` for folders), `markers`, `ueventd`;
   - `init`, with `jobs` and `services` in the HarmonyOS init cfg format.
2. Binaries go to `patches/NN-name/files/`, sources to `src/`.
3. To modify files taken from the OTA add a `hook.py` with an `apply(ctx)` function. `ctx` provides:
   - `ctx.vendor` and `ctx.system()`: EROFS trees with `read`/`write`/`add_file`/`remove`/`exists`;
   - `ctx.image_file(partition, path)` to read a file from an untouched image;
   - `ctx.save_removed()` to keep the removed files.
4. `python3 tools/gen_patch_docs.py` updates `docs/PATCHES.md`.

The numbers decide the order in which patches are applied and the order of the commands in the init cfg.
