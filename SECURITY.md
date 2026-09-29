# Security Policy

## Reporting a vulnerability

Email **security@civicactions.com** with the subject `keychain-cli`. Do not open a public
issue for a suspected leak of secret material. Include the command you ran and the output
you saw, with any secret values removed.

A security defect takes priority over all feature work (project constitution, "Vulnerability
response"). You will receive an acknowledgement within two working days.

## Supported versions

| Version | Supported |
|---|---|
| Latest minor release on the `main` branch | yes |
| Anything older | no; upgrade with `uv tool upgrade keychain-cli` |

## Documented exceptions

Every deliberate departure from the rule that secrets never surface is recorded in
[SECURITY-EXCEPTIONS.md](SECURITY-EXCEPTIONS.md). The threat model is in
[docs/threat-model.md](docs/threat-model.md).
