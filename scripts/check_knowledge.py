"""Run from the repository root: python scripts/check_knowledge.py (no AI/config)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.knowledge_base import load_knowledge

if __name__ == '__main__':
    try:
        entries = load_knowledge()
    except ValueError as exc:
        print(f'Invalid knowledge base: {exc}')
        raise SystemExit(1)
    print(f'Knowledge base valid: {len(entries)} sections, {len({item["file"] for item in entries})} files')
