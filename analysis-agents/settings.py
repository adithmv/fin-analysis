from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def settings():
    return {
        name: yaml.safe_load((ROOT / "config" / f"{name}.yaml").read_text(encoding="utf-8"))
        for name in ("agents", "llm", "verification")
    }
