"""Android acceptance tests, on a disposable emulator only. Never clears a user's phone.

Requires exact distributed v0.1/v0.2 APKs, plus two candidate builds using one test identity.
This proves the historical installer rejection and same-key/data-preserving upgrade behavior;
it does not turn ephemeral CI debug keys into a stable owner signing identity.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess

PACKAGE='com.tduck.companion'
PREFS='<map><boolean name="voice" value="false" /><string name="trusted_demo">demo-duck-001</string></map>\n'
HISTORICAL={
    'v01':'de7d76571225a9caca8449363efaaddeaf8e52b38ce2cd287dc550bc0e7e19cb',
    'v02':'88fc7d47f9578c38ec6e6dc645ed20b86529f8a5e44a52d238f300628a657267',
}

def command(*args,input=None,check=True):
    r=subprocess.run(list(args),input=input,text=True,capture_output=True)
    if check and r.returncode:raise RuntimeError('Command failed: '+r.stdout+r.stderr)
    return r.stdout+r.stderr

def cert(apksigner,apk):
    output=command(apksigner,'verify','--print-certs',str(apk))
    return next(line.split(': ',1)[1] for line in output.splitlines() if line.startswith('Signer #1 certificate SHA-256 digest:'))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['v01','v02','before','after','output','apksigner']:p.add_argument('--'+name,required=True)
    p.add_argument('--current-baseline')
    p.add_argument('--reconnect-instrumentation',action='store_true',help='CI fixture: verify Keystore record across same-key install -r')
    p.add_argument('--disposable-emulator',action='store_true')
    p.add_argument('--historical-optional',action='store_true',help='CI only: explicitly report unavailable expired fixtures; stable release acceptance must provide its baseline')
    args=p.parse_args()
    if not args.disposable_emulator or '1' != command('adb','shell','getprop','ro.kernel.qemu').strip():
        raise ValueError('Refusing destructive fixture setup except on an explicitly selected disposable emulator')
    historical=all(Path(getattr(args,name)).is_file() for name in HISTORICAL)
    if not historical and not args.historical_optional:raise ValueError('Exact historical APK fixtures required')
    identities={name:cert(args.apksigner,getattr(args,name)) for name in ['before','after']}
    assert identities['before']==identities['after'],'Candidate signing identities differ'
    verifier=Path(__file__).with_name('verify-release.py')
    import sys
    preflight=command(sys.executable,str(verifier),'--candidate',args.after,'--baseline',args.before,
        '--expected-certificate-sha256',identities['before'],'--apksigner',args.apksigner,
        '--aapt',str(Path(args.apksigner).with_name('aapt')),check=False)
    assert 'Never distribute a debug build as stable' in preflight,preflight
    command('adb','uninstall',PACKAGE,check=False)
    if historical:
        for name,digest in HISTORICAL.items():
            if hashlib.sha256(Path(getattr(args,name)).read_bytes()).hexdigest()!=digest:raise ValueError('Historical APK hash mismatch')
            identities[name]=cert(args.apksigner,getattr(args,name))
        assert identities['v01']!=identities['v02'],'Historical signing hypothesis not reproduced'
        command('adb','install',args.v01)
        rejection=command('adb','install','-r',args.v02,check=False)
        assert 'INSTALL_FAILED_UPDATE_INCOMPATIBLE' in rejection,rejection
        command('adb','uninstall',PACKAGE)
        command('adb','install',args.v02)
        candidate_rejection=command('adb','install','-r',args.before,check=False)
        assert 'INSTALL_FAILED_UPDATE_INCOMPATIBLE' in candidate_rejection,candidate_rejection
        command('adb','uninstall',PACKAGE)
    baseline_verified=False
    baseline_certificate=None
    if args.current_baseline and Path(args.current_baseline).is_file():
        digest=hashlib.sha256(Path(args.current_baseline).read_bytes()).hexdigest()
        assert digest=='a92d0388f715302d41dc931fd47dd689c8e978e0e09171d4c39a6657032362dc','Current baseline APK hash mismatch'
        baseline_certificate=cert(args.apksigner,args.current_baseline)
        command('adb','install',args.current_baseline)
        response=command('adb','install','-r',args.before,check=False)
        assert 'INSTALL_FAILED_UPDATE_INCOMPATIBLE' in response,response
        command('adb','uninstall',PACKAGE)
        baseline_verified=True
    command('adb','install',args.before)
    command('adb','shell','run-as',PACKAGE,'mkdir','-p','shared_prefs')
    command('adb','shell',"run-as com.tduck.companion sh -c 'cat > shared_prefs/companion.xml'",input=PREFS)
    if args.reconnect_instrumentation:
        seed=command('adb','shell','am','instrument','-w','-r','-e','class','com.tduck.companion.ProcessRestartTest','-e','reconnectPhase','seed','com.tduck.companion.test/androidx.test.runner.AndroidJUnitRunner')
        assert re.search(r'OK \(1 test\)',seed),'Upgrade credential seed test failed'
        command('adb','shell','am','force-stop',PACKAGE)
    before=command('adb','shell','dumpsys','package',PACKAGE)
    before_version=int(re.search(r'versionCode=(\d+)',before).group(1))
    command('adb','install','-r',args.after)
    after=command('adb','shell','dumpsys','package',PACKAGE)
    after_version=int(re.search(r'versionCode=(\d+)',after).group(1))
    assert after_version>before_version,'Upgrade must increase versionCode'
    preserved=command('adb','shell','run-as',PACKAGE,'cat','shared_prefs/companion.xml')
    assert preserved==PREFS,'Preferences changed during upgrade'
    if args.reconnect_instrumentation:
        restored=command('adb','shell','am','instrument','-w','-r','-e','class','com.tduck.companion.ProcessRestartTest','-e','reconnectPhase','restore','com.tduck.companion.test/androidx.test.runner.AndroidJUnitRunner')
        assert re.search(r'OK \(1 test\)',restored),'Keystore/automatic MuJoCo reconnect after same-key upgrade failed'
    launch=command('adb','shell','am','start','-W','-n',PACKAGE+'/.MainActivity')
    assert 'Status: ok' in launch,launch
    report={'historical_apk_hashes':HISTORICAL,'certificate_sha256':identities,
        'historical_fixtures_verified':historical,
        'historical_blocker':None if historical else 'Exact artifacts unavailable/expired; see archived verification or supply owner-retained APKs',
        'v01_to_v02_installer_error':'INSTALL_FAILED_UPDATE_INCOMPATIBLE' if historical else None,
        'v02_to_candidate_installer_error':'INSTALL_FAILED_UPDATE_INCOMPATIBLE' if historical else None,
        'same_test_key_upgrade':True,'version_before':before_version,'version_after':after_version,'preferences_preserved':True,'launch_after_upgrade':True,
        'baseline_40187307822_verified':baseline_verified,'baseline_40187307822_certificate_sha256':baseline_certificate,
        'baseline_40187307822_installer_error':'INSTALL_FAILED_UPDATE_INCOMPATIBLE' if baseline_verified else None,
        'encrypted_credentials_survived_same_key_upgrade':True if args.reconnect_instrumentation else None,
        'physical_phone_tested':False,'stable_owner_key_provisioned':False,
        'debug_release_preflight_rejected':True,'cases_passed':(5 if historical else 3)+int(baseline_verified)+int(args.reconnect_instrumentation),'cases_blocked':(0 if historical else 2)+int(not baseline_verified),'scope':'Disposable Android emulator; exact historical binaries and same-key candidate pair'}
    Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    command('adb','uninstall',PACKAGE)

if __name__=='__main__':main()
