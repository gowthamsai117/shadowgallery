# ShadowGallery — Web Exploitation CTF

A deliberately vulnerable web-exploitation application intended for an isolated Ubuntu Server 24.04 VM.

## Repository architecture

```text
shadowgallery/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── routes.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── documents.html
│   │   └── upload.html
│   └── static/
│       └── css/site.css
├── run.py
├── requirements.txt
├── .gitignore
└── README.md
```

The target provisioning script (`build.sh`) is intentionally **not stored in this repository**. Create and keep it separately on your own system.

## Intended attack path

1. **Enumeration:** scan the target with Nmap and enumerate HTTP routes.
2. **Account:** register a normal account and sign in.
3. **IDOR:** identify the missing document-ownership check at `/api/documents/<id>`.
4. **Internal information:** retrieve the worker notes record and discover the lab upload token.
5. **Initial foothold:** exercise the intentionally unsafe legacy upload-worker invocation to obtain a limited service-user shell in the isolated VM.
6. **Privilege escalation:** enumerate local permissions and discover the intentionally misconfigured privileged maintenance utility and its writable configuration file.
7. **Root flag:** retrieve `/root/proof.txt`.

The separate local provisioning script must configure the worker, service, privileged maintenance utility, and root flag. The web application source repository does not contain that script.

## Local development

Python 3.11+:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export SG_UPLOAD_DIR="$PWD/uploads"
python run.py
```

The development server binds to `127.0.0.1:5000`.

## Safety

This app intentionally contains IDOR and command-injection vulnerabilities. Run it only on a disposable VM or private host-only network. Do not expose it to the public internet or use real credentials.
