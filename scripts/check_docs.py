"""Check Markdown links and entry points; optionally check local structure notes."""
from pathlib import Path
import re
import tomllib
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def check():
    errors = []
    files = [*ROOT.glob("*.md"), *ROOT.glob("docs/**/*.md")]
    for path in files:
        text = path.read_text(encoding="utf-8")
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            target, _, fragment = link.strip("<>").partition("#")
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            resolved = path.parent / unquote(target) if target else path
            if not resolved.exists():
                errors.append(f"{path.relative_to(ROOT)}: missing link {target}")
            elif fragment and resolved.suffix == ".md":
                destination = resolved.read_text(encoding="utf-8")
                anchors = set(re.findall(r'<a\s+id="([^"]+)"', destination))
                counts = {}
                for heading in re.findall(r"^#{1,6}\s+(.+)$", destination, re.MULTILINE):
                    slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
                    count = counts.get(slug, 0)
                    counts[slug] = count + 1
                    anchors.add(slug + (f"-{count}" if count else ""))
                if unquote(fragment) not in anchors:
                    errors.append(f"{path.relative_to(ROOT)}: missing anchor {link}")
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["project"]["scripts"]["aseprite-mcp"] == "aseprite_mcp.__main__:main"
    structure_path = ROOT / "docs/PROJECT_STRUCTURE.md"
    if structure_path.is_file():
        structure = structure_path.read_text(encoding="utf-8")
        for folder in ("aseprite_mcp/core", "aseprite_mcp/backends", "extension", "scripts"):
            for path in (ROOT / folder).iterdir():
                if path.is_file() and path.suffix in {".py", ".lua"} and path.name not in structure:
                    errors.append(f"Undocumented module: {path.relative_to(ROOT)}")
    assert not errors, "\n".join(errors)
    return len(files)


if __name__ == "__main__":
    print(f"Checked {check()} Markdown files and entry point (local structure notes if present)")
