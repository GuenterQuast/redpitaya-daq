#! /bin/sh

apps_dir=/media/mmcblk0p1/apps

cat $apps_dir/mcpha/mcpha.bit > /dev/xdevcfg

$apps_dir/mcpha/mcpha-server &
$apps_dir/mcpha/pha-server &
