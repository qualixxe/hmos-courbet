# hmos-courbet

**HarmonyOS 5 (OpenHarmony) for the Xiaomi Mi 11 Lite 4G (courbet).**

This project is a fork of `hmos2sweet`, adapted for porting HarmonyOS to the Xiaomi Mi 11 Lite 4G (codename `courbet`).

`hmos-courbet` takes a **HarmonyOS full OTA package** (`update_full_base.zip` from Huawei Pura 70) and turns it into a ROM you can flash on the Mi 11 Lite 4G. The userspace stays Huawei's. What changes is underneath it:

- a LineageOS 4.14 (sm6150) kernel with the patches OpenHarmony needs;
- a set of **selectable patches** that replace the Kirin drivers with Snapdragon 732G equivalents: display, GPU, audio, coprocessors, telephony and more.

> ⚠️ **Experimental project.** No Huawei or Xiaomi image is included in this repository: the script takes them from the packages you provide. Use the resulting ROM for personal use only.
> Currently, this project is being adapted for `courbet` hardware (the original patches were written for `sweet`). Expect potential failures during the patching stage.

## Courbet Porting Status

| Feature | Status |
|---|---|
| Boot, boot animation, SceneBoard, launcher | 🟡 Work in progress |
| Display, brightness, screen off/on | 🟡 Needs DRM/KMS patch replacement for courbet |
| GPU Adreno 618 (Mesa freedreno, OpenGL ES) | ✅ Should work (same SoC) |
| Touch, volume/power keys | 🟡 Needs touch patch replacement |
| WiFi, Bluetooth, GPS, audio | 🟡 Needs HAL adaptation |
| Lock screen, PIN/password | 🟡 OpenHarmony's REE user_auth/pin_auth without TEE |
| Sensors for apps | 🟡 Needs adaptation |
| Battery, charging | 🟡 Standard HarmonyOS HAL |
| Vibration | 🟡 Exposed as /sys/class/leds/vibrator |
| Telephony: SIM, network, calls, SMS | 🟡 RIL over QMI/QRTR |
| NFC, IR blaster, Thermal | 🟡 Needs testing |
| USB (hdc, file transfer) | 🟡 Configfs gadget |
| Camera, Fingerprint, proximity sensor | 🔴 Not yet |

*Tested with: Huawei Pura 70 HarmonyOS 5.1 full OTA (`ADY-LGRP3-CHN 205.1.0.128(SP5)`, `update_full_base.zip`).*

## Requirements

- **Linux** (or **WSL** on Windows) with Python 3.8+, `e2fsprogs` (`debugfs`), `unzip`, `curl`. 
  `pip install brotli`, if the ROM uses `vendor.new.dat.br`.
- About **25 GB free**: extracted images, temporary trees and output.
- A **HarmonyOS full OTA** of the Huawei Pura 70 (`update_full_base.zip`).
- **A ROM for the Xiaomi Mi 11 Lite 4G (courbet)** with block images (e.g., LineageOS 22.2). It provides courbet's GPU, IPA, audio amplifier, WiFi and camera firmware.
- A phone with an **unlocked bootloader**, `fastboot` and `adb` (platform-tools) in PATH, and a recovery (TWRP/OrangeFox) to read the logs.

## Usage (Local)

```sh
git clone https://github.com/qualixxe/hmos-courbet && cd hmos-courbet
tools/fetch_tools.sh                     # downloads the EROFS tools into tools/bin
python3 hmos2sweet.py --ota ~/update_full_base.zip --sweet-rom ~/lineage-courbet.zip --out out
