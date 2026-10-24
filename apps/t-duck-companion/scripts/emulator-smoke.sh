#!/usr/bin/env bash
set -u
if gradle -p apps/t-duck-companion --no-daemon connectedDebugAndroidTest; then
  test_result=0
else
  test_result=$?
fi
# Android's test runner uninstalls both APKs after testing. Reinstall the same build for visual QA.
if [ "$test_result" -eq 0 ]; then
  set -e
  adb install -r apps/t-duck-companion/app/build/outputs/apk/debug/app-debug.apk
  adb shell am force-stop com.tduck.companion
  adb shell am start -W -n com.tduck.companion/.MainActivity
  sleep 2
  adb shell screencap -p /sdcard/companion-home.png
  adb pull /sdcard/companion-home.png apps/t-duck-companion/app/build/companion-home.png
fi
exit "$test_result"
