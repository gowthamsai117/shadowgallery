# ShadowGallery — Web Exploitation CTF

A deliberately vulnerable, intermediate web-exploitation machine for an isolated Ubuntu Server 24.04 VM.

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
├── build.sh
├── .gitignore
└── README.md
```

## Intended attack path

1. **Enumeration:** scan the target with Nmap; identify SSH and HTTP, then enumerate the web application routes.
2. **Account:** register a normal account and sign in.
3. **IDOR:** inspect document API records and identify the missing ownership check at `/api/documents/<id>`.
4. **Internal information:** read the internal worker notes record to find the upload token and legacy worker details.
5. **Initial foothold:** exploit the intentionally unsafe shell invocation in the upload workflow to obtain a limited `www-data` shell in the isolated VM.
6. **Privilege escalation:** inspect `sudo -l`; discover that `www-data` can run `/usr/local/bin/gallery-maintenance` as root. The utility sources the writable `/opt/gallery/maintenance.conf` file.
7. **Root flag:** use the lab's privilege-escalation misconfiguration to read `/root/proof.txt`.

## Deploy on a disposable Ubuntu Server 24.04 VM

1. Create an Ubuntu Server VM and use a **host-only/private network**.
2. Clone this repository onto that VM.
3. Run:

   ```bash
   chmod +x build.sh
   sudo ./build.sh
   ```

4. Find the VM IP with `ip -br addr`.
5. From Kali on the same private lab network, browse to `http://<TARGET-IP>/`.

The provisioning script configures Nginx, a systemd service, the upload worker, a lab-only sudo rule, and the root flag. The application upload token is stored in `/etc/shadowgallery.env`; discover it through the intended application path rather than reading target configuration directly.

## Local development

Python 3.11+:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export SG_UPLOAD_DIR="$PWD/uploads"
python run.py
```

The development server binds to `127.0.0.1:5000`. The production-like VM service is started by `build.sh` behind Nginx.

## Safety

This lab deliberately includes IDOR, command injection, and a privileged configuration-file weakness. Run it only on a disposable private VM. Never expose it to the public internet, and never reuse real secrets or passwords.
