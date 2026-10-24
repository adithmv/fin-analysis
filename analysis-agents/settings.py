from pathlib import Path
import hashlib
import yaml

ROOT = Path(__file__).resolve().parents[1]


def settings():
    config = {
        name: yaml.safe_load((ROOT / "config" / f"{name}.yaml").read_text(encoding="utf-8"))
        for name in ("agents", "llm", "verification")
    }
    prompts = Path(__file__).resolve().parent / "prompts"
    config["prompt_snapshot"] = {p.stem: p.read_text(encoding="utf-8") for p in sorted(prompts.glob("*.md"))}
    source = hashlib.sha256()
    for p in sorted(Path(__file__).resolve().parent.rglob("*.py")):
        if ".venv" not in p.parts and "tests" not in p.parts:
            source.update(p.relative_to(ROOT).as_posix().encode())
            source.update(p.read_bytes())
    config["source_hash"] = source.hexdigest()
    return config
