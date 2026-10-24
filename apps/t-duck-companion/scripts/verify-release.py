"""Fail closed before distributing a signed release. No signing keys are generated or changed."""
import argparse
import re
import subprocess


def inspect(path,apksigner,aapt):
    sig=subprocess.check_output([apksigner,'verify','--print-certs',path],text=True)
    certificate=re.search(r'Signer #1 certificate SHA-256 digest: ([0-9a-f]+)',sig).group(1)
    metadata=subprocess.check_output([aapt,'dump','badging',path],text=True)
    package=re.search(r"package: name='([^']+)' versionCode='(\d+)'",metadata)
    return certificate,package.group(1),int(package.group(2)),"application-debuggable" in metadata


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['candidate','baseline','expected-certificate-sha256','apksigner','aapt']:p.add_argument('--'+name,required=True)
    args=p.parse_args()
    cert,package,version,debug=inspect(args.candidate,args.apksigner,args.aapt)
    oldcert,oldpackage,oldversion,_=inspect(args.baseline,args.apksigner,args.aapt)
    assert cert==oldcert==args.expected_certificate_sha256.lower(),'Unapproved/different signing identity'
    assert package==oldpackage=='com.tduck.companion','Package changed'
    assert version>oldversion,'versionCode must increase'
    assert not debug,'Never distribute a debug build as stable'
    print('Release signature/package/version preflight passed. Actual adb install -r/data/UI acceptance is still required.')

if __name__=='__main__':main()
