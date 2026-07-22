from functools import lru_cache
from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=8)
def load_prompt(name: str) -> str:
    if not name or Path(name).name != name:
        raise ValueError("prompt name must be a plain file name")
    path = PROMPT_DIR / name
    if path.suffix != ".md":
        raise ValueError("prompt files must use the .md extension")
    return path.read_text(encoding="utf-8")
