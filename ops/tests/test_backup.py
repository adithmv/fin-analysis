import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location("backup",Path(__file__).resolve().parents[1]/"backup.py")
backup=importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def test_connection_uses_temporary_password_file_without_leaking_to_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY","private-example-value")
    with backup.connection("postgresql://reader:p%3Ass@db.example.test:5432/postgres") as env:
        path=Path(env["PGPASSFILE"])
        assert path.exists() and "p\\:ss" in path.read_text()
        assert "PGPASSWORD" not in env and "GEMINI_API_KEY" not in env
        assert env["PGSSLMODE"]=="require"
    assert not path.exists()


def test_repository_destination_is_rejected():
    with pytest.raises(ValueError,match="outside"):
        backup.destination(backup.ROOT/"backups")


def test_backup_checks_both_copies_and_marks_restore_pending(tmp_path,monkeypatch):
    monkeypatch.setenv("DATABASE_URL","postgresql://reader:fixture@db.example.test/postgres")
    monkeypatch.setattr(backup.shutil,"which",lambda name:name)
    def run(args,env=None):
        if args[0]=="pg_dump":
            assert not any("fixture" in arg for arg in args)
            Path(args[-1]).write_bytes(b"fixture dump contents")
            return b""
        return b"TABLE DATA public candles"
    monkeypatch.setattr(backup,"run",run)
    result=backup.backup(tmp_path/"primary",tmp_path/"secondary")
    assert result["restore_verified"] is False and result["cloud_upload_verified"] is False
    assert backup.digest(Path(result["primary"])/"database.dump")==backup.digest(Path(result["secondary"])/"database.dump")
    import zipfile
    with zipfile.ZipFile(Path(result["primary"])/"rebuild-config.zip") as archive:
        assert ".env.example" in archive.namelist() and ".env" not in archive.namelist()


def test_failed_dump_never_creates_success_manifest(tmp_path,monkeypatch):
    monkeypatch.setenv("DATABASE_URL","postgresql://reader:fixture@db.example.test/postgres")
    monkeypatch.setattr(backup.shutil,"which",lambda name:name)
    def fail(*args,**kwargs):
        raise RuntimeError("test failure")
    monkeypatch.setattr(backup,"run",fail)
    with pytest.raises(RuntimeError):
        backup.backup(tmp_path/"primary",tmp_path/"secondary")
    assert not list(tmp_path.rglob("manifest.json"))
