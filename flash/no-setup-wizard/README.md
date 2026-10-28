# no setup wizard (recovery)

Marks the HarmonyOS OOBE as finished by patching the `*settingsdata*.db`
databases in `/data/app|service/el1|el2` (same logic as the
`50-remove-setup-wizard` boot service, run once from recovery).

On a **clean install** of a build with patch 50 the wizard app is already
removed from system, so this pack is not required. It is useful for:

- keeping-data flashes over a build without patch 50;
- older builds where the wizard app is still present;
- belt and suspenders: forcing `device_provisioned=1` in the databases.

## Reliable way: install.bat (adb)

1. Boot the phone into recovery (Lineage recovery: `fastboot reboot
   recovery` from fastboot mode, or Power+Volume Up).
2. Run `install.bat` on the PC (adb pushes `sweet-oobedone` and `q.sh`,
   runs the patcher, cleans up bring-up debug flags).
3. Reboot to system from the recovery menu.

## Optional: no-setup-wizard.zip

For recoveries that accept unsigned zips (TWRP and friends): copy the zip
to the phone or sideload it ("Apply from ADB"). Stock Lineage recovery
verifies zip signatures against build-time keys that we do not have, and
will refuse it - use `install.bat` there instead.

## Build

```
python make_zip.py
```
