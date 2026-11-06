"""Package only the standalone project's public source files, never local runtime data."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.2"
FILES = ("README.md", "INSTALL_FOR_AI.md", "LICENSE", "NOTICE.md", "CHANGELOG.md", "CONTRIBUTING.md", "AGENTS.md",
         ".gitignore", ".gitattributes", "profile.json", "requirements.txt", "mcp.example.json",
         "bootstrap.ps1", "install.ps1", "install.cmd", "start.cmd", "doctor.cmd")
DIRECTORIES = ("src", "scripts", "tests", "docs", "skills", "third-party", ".github")
SUFFIXES = {".md", ".py", ".js", ".cjs", ".ps1", ".yml", ".yaml", ".json", ".txt"}


def release_files(root=ROOT):
    paths = [root / name for name in FILES]
    for directory in DIRECTORIES:
        paths += [p for p in (root / directory).rglob("*") if p.is_file()
                  and "__pycache__" not in p.parts and p.suffix in SUFFIXES]
    return sorted(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / f"pvz-scared-ai-bridge-{VERSION}.zip")
    args = parser.parse_args()
    files = release_files()
    manifest = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, "pvz-scared-ai-bridge/" + path.relative_to(ROOT).as_posix())
        archive.writestr("pvz-scared-ai-bridge/manifest.json", json.dumps(
            {"version": VERSION, "files": manifest}, ensure_ascii=False, indent=2) + "\n")
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix(".zip.sha256").write_text(digest + "  " + args.output.name + "\n", encoding="ascii")
    print(json.dumps({"path": str(args.output), "files": len(files) + 1, "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
