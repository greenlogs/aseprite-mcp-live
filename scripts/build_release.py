"""Build and inspect a local release candidate; never upload anything."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXTENSION_FILES = ("package.json", "main.lua", "bridge.lua", "editor.lua", "preview.lua", "animation.lua")


def version():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def inspect_artifacts(directory):
    release_version = version()
    wheel = directory / f"aseprite_mcp-{release_version}-py3-none-any.whl"
    source = directory / f"aseprite_mcp-{release_version}.tar.gz"
    extension = directory / f"aseprite-mcp-live-{release_version}.aseprite-extension"
    with zipfile.ZipFile(wheel) as archive:
        wheel_files = archive.namelist()
        assert "aseprite_mcp/backends/cli.lua" in wheel_files
        assert "aseprite_mcp/__main__.py" in wheel_files
        assert any(name.endswith("/licenses/LICENSE") for name in wheel_files)
        entry = next(name for name in wheel_files if name.endswith("/entry_points.txt"))
        assert "aseprite-mcp = aseprite_mcp.__main__:main" in archive.read(entry).decode()
    with tarfile.open(source) as archive:
        members = archive.getmembers()
        assert all(member.isfile() or member.isdir() for member in members), "Links are not distributed"
        source_files = [member.name for member in members]
        assert any(name.endswith("/extension/package.json") for name in source_files)
        assert any(name.endswith("/docs/INSTALL.md") for name in source_files)
    with zipfile.ZipFile(extension) as archive:
        extension_files = archive.namelist()
        assert set(extension_files) == {*EXTENSION_FILES, "LICENSE", "NOTICE.md"}
        manifest = json.loads(archive.read("package.json"))
        assert manifest["version"] == release_version
        assert manifest["contributes"]["scripts"] == [{"path": "./main.lua"}]
        assert archive.read("LICENSE") == (ROOT / "LICENSE").read_bytes()
    forbidden = {"aseprite", ".env", ".venv", ".work", ".git", ".codex", ".agents", "__pycache__"}
    for name in [*wheel_files, *source_files, *extension_files]:
        parts = Path(name).parts
        assert not Path(name).is_absolute() and ".." not in parts, name
        assert not forbidden.intersection(part.lower() for part in parts), name
        assert not name.lower().endswith((".exe", ".dll", ".pyc", ".aseprite-crash", ".aseprite-recovery")), name
    requirements = directory / "requirements.txt"
    assert requirements.is_file() and "-e ." not in requirements.read_text(encoding="utf-8")
    return {path.name: {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in (wheel, source, extension, requirements)}


def build(directory):
    directory.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "extension/package.json").read_text(encoding="utf-8"))
    assert manifest["version"] == version(), "Service and extension versions must match"
    assert f'local EXTENSION_VERSION = "{version()}"' in (ROOT / "extension/bridge.lua").read_text(encoding="utf-8")
    assert f'SERVICE_VERSION = "{version()}"' in (ROOT / "aseprite_mcp/core/protocol.py").read_text(encoding="utf-8")
    subprocess.run(["uv", "build", "--out-dir", str(directory)], cwd=ROOT, check=True)
    subprocess.run(["uv", "export", "--locked", "--no-dev", "--no-emit-project", "--no-header",
                    "--output-file", str(directory / "requirements.txt")], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    target = directory / f"aseprite-mcp-live-{version()}.aseprite-extension"
    sources = {name: ROOT / "extension" / name for name in EXTENSION_FILES}
    sources.update({"LICENSE": ROOT / "LICENSE", "NOTICE.md": ROOT / "extension/NOTICE.md"})
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(sources.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    artifacts = inspect_artifacts(directory)
    (directory / "SHA256SUMS").write_text("".join(f"{data['sha256']}  {name}\n" for name, data in artifacts.items()), encoding="utf-8")
    (directory / "manifest.json").write_text(json.dumps({"version": version(), "protocol_version": 1,
        "artifacts": artifacts}, indent=2) + "\n", encoding="utf-8")
    return artifacts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    directory = args.out_dir.resolve()
    if args.check_only:
        artifacts = inspect_artifacts(directory)
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        assert manifest == {"version": version(), "protocol_version": 1, "artifacts": artifacts}
        expected = "".join(f"{data['sha256']}  {name}\n" for name, data in artifacts.items())
        assert (directory / "SHA256SUMS").read_text(encoding="utf-8") == expected
    else:
        artifacts = build(directory)
    print(json.dumps(artifacts, indent=2))
