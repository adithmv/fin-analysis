"""Create a custom-format dump and checksum-verified second filesystem copy."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit,unquote
from uuid import uuid4
import zipfile
from dotenv import load_dotenv
from shared.db import get_client
from shared.logbook import log_event

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    with open(path,"rb") as source:
        return hashlib.file_digest(source,"sha256").hexdigest()


def destination(path):
    resolved=Path(path).expanduser().resolve()
    if resolved==ROOT or ROOT in resolved.parents:
        raise ValueError("Backups must be outside the repository")
    return resolved


@contextmanager
def connection(url):
    parsed=urlsplit(url)
    values=[parsed.hostname,str(parsed.port or 5432),unquote(parsed.path.lstrip("/")),
            unquote(parsed.username or ""),unquote(parsed.password or "")]
    if parsed.scheme not in ("postgres","postgresql") or not all(values) or any("\n" in v or "\r" in v for v in values):
        raise ValueError("DATABASE_URL must contain a valid PostgreSQL host, database, user and password")
    with tempfile.TemporaryDirectory(prefix="fin-backup-") as folder:
        password=Path(folder)/"pgpass"
        password.write_text(":".join(v.replace("\\","\\\\").replace(":","\\:") for v in values)+"\n",encoding="utf-8")
        password.chmod(0o600)
        # Credentials stay out of command arguments and are removed with the temporary directory.
        env={k:v for k,v in os.environ.items() if k.upper() in
             {"PATH","SYSTEMROOT","WINDIR","TEMP","TMP","HOME","APPDATA","LOCALAPPDATA"}}
        env.update(PGHOST=values[0],PGPORT=values[1],PGDATABASE=values[2],PGUSER=values[3],
                   PGPASSFILE=str(password),PGSSLMODE="require",PGCONNECT_TIMEOUT="20")
        yield env


def run(args,env=None):
    result=subprocess.run(args,env=env,capture_output=True,timeout=3600,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    if result.returncode:
        raise RuntimeError("PostgreSQL backup tool failed; check credentials, connectivity and client/server versions")
    return result.stdout


def backup(primary,secondary):
    primary,secondary=destination(primary),destination(secondary)
    if primary==secondary or primary in secondary.parents or secondary in primary.parents:
        raise ValueError("Choose separate backup destinations")
    if not os.environ.get("DATABASE_URL"):
        raise ValueError("DATABASE_URL is not configured locally")
    executables={name:shutil.which(name) for name in ("pg_dump","pg_restore")}
    if not all(executables.values()):
        raise ValueError("Install PostgreSQL client tools and add them to PATH")
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid4().hex[:8]
    folder=primary/stamp
    folder.mkdir(parents=True)
    dump=folder/"database.dump.partial"
    with connection(os.environ["DATABASE_URL"]) as env:
        run([executables["pg_dump"],"--no-password","--format=custom","--no-owner","--no-acl","--file",str(dump)],env)
    toc=run([executables["pg_restore"],"--list",str(dump)])
    if not dump.stat().st_size or b"TABLE DATA" not in toc:
        raise RuntimeError("Dump does not contain table data")
    dump=dump.rename(folder/"database.dump")
    (folder/"archive-list.txt").write_bytes(toc)
    with zipfile.ZipFile(folder/"rebuild-config.zip","w",zipfile.ZIP_DEFLATED) as archive:
        for pattern in ("config/*.yaml","db/migrations/*.sql",".env.example"):
            for source in ROOT.glob(pattern):
                archive.write(source,source.relative_to(ROOT))
    checksums={p.name:digest(p) for p in folder.iterdir() if p.is_file()}
    manifest={"created_at":datetime.now(timezone.utc).isoformat(),"sha256":checksums,
              "restore_verified":False,"cloud_upload_verified":False}
    (folder/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    secondary.mkdir(parents=True,exist_ok=True)
    copy=secondary/stamp
    shutil.copytree(folder,copy)
    if any(digest(copy/name)!=checksum for name,checksum in checksums.items()):
        raise RuntimeError("Second backup copy checksum mismatch")
    return {"primary":str(folder),"secondary":str(copy),**manifest}


def main():
    load_dotenv(ROOT/".env")
    parser=argparse.ArgumentParser()
    parser.add_argument("--primary",default=str(ROOT.parent/"fin-analysis-backups"))
    parser.add_argument("--secondary",default=os.environ.get("BACKUP_SECONDARY_DIR"))
    args=parser.parse_args()
    if not args.secondary:
        parser.error("Configure BACKUP_SECONDARY_DIR outside the repository")
    run_id=str(uuid4())
    try:
        result=backup(args.primary,args.secondary)
        get_client().table("health_checks").insert({"check_key":"backup_complete","subject":"database",
            "status":"ok","detail":result}).execute()
        log_event(run_id,"ops","backup","success",output_summary="Dump and second filesystem copy verified; restore/cloud receipt remain separate checks")
        print(json.dumps(result,indent=2)); return 0
    except Exception:
        log_event(run_id,"ops","backup","failed",error="Backup failed; check local configuration, disk and PostgreSQL tools")
        print("Backup failed. Check local configuration, disk and PostgreSQL tools."); return 1


if __name__=="__main__":
    raise SystemExit(main())
