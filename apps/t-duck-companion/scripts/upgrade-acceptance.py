"""Android acceptance tests, on a disposable emulator only. Never clears a user's phone.

Requires exact distributed v0.1/v0.2 APKs, plus two candidate builds using one test identity.
This proves the historical installer rejection and same-key/data-preserving upgrade behavior;
it does not turn ephemeral CI debug keys into a stable owner signing identity.
"""
import argparse
import hashlib
import json
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
    p.add_argument('--disposable-emulator',action='store_true')
    args=p.parse_args()
    if not args.disposable_emulator or '1' != command('adb','shell','getprop','ro.kernel.qemu').strip():
        raise ValueError('Refusing destructive fixture setup except on an explicitly selected disposable emulator')
    for name,digest in HISTORICAL.items():
        if hashlib.sha256(Path(getattr(args,name)).read_bytes()).hexdigest()!=digest:raise ValueError('Historical APK hash mismatch')
    identities={name:cert(args.apksigner,getattr(args,name)) for name in ['v01','v02','before','after']}
    assert identities['v01']!=identities['v02'],'Historical signing hypothesis not reproduced'
    assert identities['before']==identities['after'],'Candidate signing identities differ'
    command('adb','uninstall',PACKAGE,check=False)
    command('adb','install',args.v01)
    rejection=command('adb','install','-r',args.v02,check=False)
    assert 'INSTALL_FAILED_UPDATE_INCOMPATIBLE' in rejection,rejection
    command('adb','uninstall',PACKAGE)
    command('adb','install',args.v02)
    candidate_rejection=command('adb','install','-r',args.before,check=False)
    assert 'INSTALL_FAILED_UPDATE_INCOMPATIBLE' in candidate_rejection,candidate_rejection
    command('adb','uninstall',PACKAGE)
    command('adb','install',args.before)
    command('adb','shell','run-as',PACKAGE,'mkdir','-p','shared_prefs')
    command('adb','shell',"run-as com.tduck.companion sh -c 'cat > shared_prefs/companion.xml'",input=PREFS)
    before=command('adb','shell','dumpsys','package',PACKAGE)
    assert 'versionCode=3 ' in before
    command('adb','install','-r',args.after)
    after=command('adb','shell','dumpsys','package',PACKAGE)
    assert 'versionCode=4 ' in after
    preserved=command('adb','shell','run-as',PACKAGE,'cat','shared_prefs/companion.xml')
    assert preserved==PREFS,'Preferences changed during upgrade'
    launch=command('adb','shell','am','start','-W','-n',PACKAGE+'/.MainActivity')
    assert 'Status: ok' in launch,launch
    report={'historical_apk_hashes':HISTORICAL,'certificate_sha256':identities,
        'v01_to_v02_installer_error':'INSTALL_FAILED_UPDATE_INCOMPATIBLE',
        'v02_to_candidate_installer_error':'INSTALL_FAILED_UPDATE_INCOMPATIBLE',
        'same_test_key_upgrade_3_to_4':True,'preferences_preserved':True,'launch_after_upgrade':True,
        'physical_phone_tested':False,'stable_owner_key_provisioned':False,
        'cases_passed':4,'scope':'Disposable Android emulator; exact historical binaries and same-key candidate pair'}
    Path(args.output).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    command('adb','uninstall',PACKAGE)

if __name__=='__main__':main()
