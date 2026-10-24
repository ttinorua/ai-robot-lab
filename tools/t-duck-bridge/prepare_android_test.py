"""Generate only ephemeral instrumentation assets; never included in the normal app APK."""
from pathlib import Path
import json
import secrets
import subprocess

root = Path(__file__).resolve().parents[2]
work = root / ".tc02"
assets = root / "apps/t-duck-companion/app/src/androidTest/assets"
work.mkdir(exist_ok=True); assets.mkdir(parents=True, exist_ok=True)
fixture = root / "apps/t-duck-companion/app/src/test/resources/tls/tduck-simulator-test-only.p12"
for args, output in [(["-clcerts", "-nokeys"], work / "ca.pem"), (["-nocerts", "-nodes"], work / "key.pem")]:
    subprocess.run(["openssl", "pkcs12", "-in", str(fixture), "-passin", "pass:test-fixture-only", *args, "-out", str(output)], check=True)
    output.chmod(0o600)
# Android CertificateFactory requires a PEM beginning at the certificate header, not PKCS12 bag attributes.
subprocess.run(["openssl", "x509", "-in", str(work / "ca.pem"), "-out", str(assets / "tc02-ca.pem")], check=True)
(assets / "tc02-bridge.json").write_text(json.dumps({"endpoint": "https://localhost:8443", "token": secrets.token_urlsafe(32)}))
(assets / "tc02-bridge.json").chmod(0o600)
print("Ephemeral test CA and owner token prepared (instrumentation assets only)")
