#!/usr/bin/env bash
set -u
if gradle -p apps/t-duck-companion --no-daemon connectedDebugAndroidTest; then
  test_result=0
else
  test_result=$?
fi
if adb shell pm path com.tduck.companion | grep -q '^package:'; then
  adb shell am force-stop com.tduck.companion
  adb shell am start -n com.tduck.companion/.MainActivity
  sleep 2
  adb shell screencap -p /sdcard/companion-home.png
  adb pull /sdcard/companion-home.png apps/t-duck-companion/app/build/companion-home.png
fi
exit "$test_result"
