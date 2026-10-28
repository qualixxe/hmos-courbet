@echo off
REM Mark HarmonyOS OOBE as finished from recovery (phone in recovery, adb works).
REM Patches settingsdata databases in /data (f2fs, not encrypted) and cleans
REM bring-up debug flags. sweet-oobedone must sit next to this script.
set HERE=%~dp0
adb wait-for-recovery || exit /b 1
adb push "%HERE%sweet-oobedone" /tmp/sweet-oobedone || exit /b 1
adb push "%HERE%q.sh" /tmp/q.sh || exit /b 1
adb shell "sh /tmp/q.sh"
echo.
echo Reboot to system from the recovery menu, or: adb reboot
