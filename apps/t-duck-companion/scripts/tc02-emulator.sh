#!/usr/bin/env bash
set -eu
python tools/t-duck-bridge/prepare_android_test.py
export T_DUCK_TOKEN="$(python -c 'import json; print(json.load(open("apps/t-duck-companion/app/src/androidTest/assets/tc02-bridge.json"))["token"])')"
export TC02_FOUNDATION="$PWD/.tc02/foundation"
export TC02_RL="$PWD/.tc02/rl"
export TC02_RUNTIME="$PWD/.tc02/runtime"
mkdir -p .tc02/evidence
python -m unittest discover -s tools/t-duck-bridge -v > .tc02/evidence/bridge-tests.txt 2>&1
python tools/t-duck-bridge/bridge.py --foundation-source "$TC02_FOUNDATION" --rl-source "$TC02_RL" --runtime-source "$TC02_RUNTIME" --cert .tc02/ca.pem --key .tc02/key.pem --audit .tc02/evidence/bridge-audit.jsonl > .tc02/evidence/bridge-server.log 2>&1 &
bridge_pid=$!
trap 'kill "$bridge_pid" 2>/dev/null || true' EXIT
python - <<'PY'
import os,ssl,time,urllib.request
context=ssl.create_default_context(cafile='.tc02/ca.pem')
for attempt in range(100):
 try:
  request=urllib.request.Request('https://localhost:8443/v1/capabilities',headers={'Authorization':'Bearer '+os.environ['T_DUCK_TOKEN']})
  with urllib.request.urlopen(request,context=context,timeout=1) as response:
   assert response.status==200
  break
 except Exception:
  if attempt==99: raise
  time.sleep(.1)
PY
adb reverse tcp:8443 tcp:8443
if gradle -p apps/t-duck-companion --no-daemon connectedDebugAndroidTest; then
  python tools/t-duck-bridge/collect_android_evidence.py
else
  exit 1
fi
# Preserve the ordinary demo screenshot and confirm a normal test APK launches independently.
adb install -r apps/t-duck-companion/app/build/outputs/apk/debug/app-debug.apk
adb shell am start -W -n com.tduck.companion/.MainActivity
sleep 2
adb shell screencap -p /sdcard/companion-home.png
adb pull /sdcard/companion-home.png apps/t-duck-companion/app/build/companion-home.png
