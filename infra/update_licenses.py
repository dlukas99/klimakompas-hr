"""Replace the generated dependency section of docs/alati-i-licence.md."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "alati-i-licence.md"
MARKER = "<!-- generated: make licenses -->"


def main() -> None:
    python = (ROOT / "data" / "licenses-python.md").read_text(encoding="utf-8")
    node = (ROOT / "data" / "licenses-node.md").read_text(encoding="utf-8")
    head = DOC.read_text(encoding="utf-8").split(MARKER)[0]
    DOC.write_text(
        f"{head}{MARKER}\n\n### Python\n\n{python.strip()}\n\n### Node\n\n{node.strip()}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
