#!/system/bin/sh
# no setup wizard: mark HarmonyOS OOBE as finished.
# Patches *settingsdata*.db under /data/app|service/el1|el2
# (device_provisioned, user_setup_complete, basic_statement_agreed = 1).
# Run from LineageOS-based recovery as root: sh /tmp/q.sh
if [ ! -d /data/app ]; then
  for dev in /dev/block/by-name/userdata /dev/block/bootdevice/by-name/userdata; do
    [ -e "$dev" ] || continue
    mount -t f2fs "$dev" /data 2>/dev/null && break
    mount -t ext4 "$dev" /data 2>/dev/null && break
  done
fi
if [ ! -d /data/app ]; then
  echo "ERROR: /data is not mounted"
  exit 1
fi
echo "== settingsdata databases =="
find /data/app/el1 /data/app/el2 /data/service/el1 /data/service/el2 \
  -name '*settingsdata*.db' 2>/dev/null
chmod 755 /tmp/sweet-oobedone
/tmp/sweet-oobedone
echo "== kernel log =="
dmesg | grep sweet-oobedone | tail -n 20
echo "== cleanup of bring-up debug flags =="
rm -f /data/hdi_dump_layer && echo "removed /data/hdi_dump_layer"
echo "clearing /data/local/traces (13 GB, may take a minute) ..."
rm -rf /data/local/traces/* 2>/dev/null
echo "DONE"
