#!/usr/bin/env bash
set -eu
python tools/t-duck-bridge/prepare_android_test.py
export T_DUCK_TOKEN="$(python -c 'import json; print(json.load(open("apps/t-duck-companion/app/src/androidTest/assets/tc02-bridge.json"))["token"])')"
export TC02_FOUNDATION="$PWD/.tc02/foundation"
export TC02_RL="$PWD/.tc02/rl"
export TC02_RUNTIME="$PWD/.tc02/runtime"
mkdir -p .tc02/evidence
python -m unittest discover -s tools/t-duck-cloud -v > .tc02/evidence/cloud-tests.txt 2>&1
python tools/t-duck-cloud/benchmark.py --foundation "$TC02_FOUNDATION" --rl "$TC02_RL" --runtime "$TC02_RUNTIME" > .tc02/evidence/resource-benchmark.json
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
test "$(adb shell getprop ro.kernel.qemu | tr -d '\r')" = 1
adb reverse tcp:8443 tcp:8443
if gradle -p apps/t-duck-companion --no-daemon connectedDebugAndroidTest -Pandroid.testInstrumentationRunnerArguments.notClass=com.tduck.companion.ProcessRestartTest; then
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

# Persistence across two actual app processes, using only disposable emulator/CI credentials.
adb install -r apps/t-duck-companion/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb logcat -c
adb shell am instrument -w -r -e class com.tduck.companion.ProcessRestartTest -e reconnectPhase seed com.tduck.companion.test/androidx.test.runner.AndroidJUnitRunner > .tc02/evidence/restart-seed.txt
adb shell am force-stop com.tduck.companion
adb shell am instrument -w -r -e class com.tduck.companion.ProcessRestartTest -e reconnectPhase restore com.tduck.companion.test/androidx.test.runner.AndroidJUnitRunner > .tc02/evidence/restart-restore.txt
adb logcat -d -s RECONNECT_PROCESS:I '*:S' > .tc02/evidence/restart-log.txt
python - <<'PYTEST'
import json,re
from pathlib import Path
root=Path('.tc02/evidence')
for name in ['restart-seed.txt','restart-restore.txt']:
 text=(root/name).read_text()
 assert re.search(r'OK \(1 test\)',text), 'Process restart instrumentation did not pass: '+name
line=next(x for x in (root/'restart-log.txt').read_text().splitlines() if '"different_process"' in x)
report=json.loads(line[line.index('{'):])
assert report['different_process'] and report['automatic_connection'] and report['actual_mujoco_telemetry']
assert report['movement_mode']=='rest' and not report['token_in_plaintext_preferences']
(root/'secure-restart.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
PYTEST

# Signing/update acceptance runs only on this disposable emulator, after UI integration.
cp apps/t-duck-companion/app/build/outputs/apk/debug/app-debug.apk .tc02/upgrade-before.apk
next_version=$(python -c 'import re,subprocess; text=subprocess.check_output(["adb","shell","dumpsys","package","com.tduck.companion"],text=True); print(int(re.search(r"versionCode=(\d+)",text).group(1))+1)')
gradle -p apps/t-duck-companion --no-daemon assembleDebug -PcompanionVersionCode="$next_version"
python apps/t-duck-companion/scripts/upgrade-acceptance.py --disposable-emulator --historical-optional --reconnect-instrumentation --current-baseline .tc02/reconnect-baseline/app-debug.apk --v01 .tc02/v01/app-debug.apk --v02 .tc02/v02/app-debug.apk --before .tc02/upgrade-before.apk --after apps/t-duck-companion/app/build/outputs/apk/debug/app-debug.apk --apksigner "$ANDROID_HOME/build-tools/35.0.0/apksigner" --output .tc02/evidence/upgrade-acceptance.json
