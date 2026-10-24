# Public test fixture — never a production identity

`tduck-simulator-test-only.p12` contains an intentionally public RSA private key and self-signed localhost certificate for JVM integration tests only. Its password is `test-fixture-only`; this is a fixture label, not a secret. It is under `src/test/resources` and must never ship in the application or be trusted by physical hardware.

The certificate's sole subject alternative name is DNS `localhost`. Integration tests explicitly trust this one fixture certificate, retain the default hostname verifier, and restore the previous default socket factory after each test. Thus `localhost` succeeds, `127.0.0.1` fails hostname verification, and the platform trust store rejects the fixture by default.

Recreate using OpenSSL (temporary key/cert files must stay out of source):

```sh
openssl req -x509 -newkey rsa:2048 -nodes -keyout /tmp/tduck-test-only.key -out /tmp/tduck-test-only.crt -days 36500 -subj '/CN=localhost/O=T-Duck Test Fixture Only' -addext 'subjectAltName=DNS:localhost'
openssl pkcs12 -export -inkey /tmp/tduck-test-only.key -in /tmp/tduck-test-only.crt -out tduck-simulator-test-only.p12 -name tduck-test -passout pass:test-fixture-only
```
