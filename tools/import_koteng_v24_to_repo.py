#!/usr/bin/env python3
"""Import the exact Koteng V2.4 archive into a local ministaut Git checkout.

No network, scanner execution, database writes, or Git push.
Requires the original ZIP downloaded from the ChatGPT conversation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ZIP_SHA256 = "b0ea10aacd80da2d2acf323dc2aadb5268cd9c6c8e0476bc6afa9cd0401d5d6a"
SOURCE_PREFIX = "Koteng_V2.4/"
TARGET = Path("baselines/koteng/v2.4")
ALLOWED = {".py", ".json", ".md", ".txt", ".bat", ".ps1", ".html", ".png"}
REQUIRED = {"koteng_scanner.py", "profile_lock.py", "anchor_scan.py",
            "anchor_training.py", "koteng_profile.json", "ankerpunkter_koteng.json",
            "hourly_koteng.py", "sync_koteng.py", "preflight_v24.py",
            "sjekk_skjerm_v24.py", "01_INSTALLER.bat",
            "04_START_LIVE_TIMEVIS.bat", "07_SJEKK_SKJERM.bat",
            "reference/reference_edge_approved_20261026.png",
            "reference/anchor_overlay_approved_20261026.png"}

def source_name(path: str) -> str | None:
    if not path.startswith(SOURCE_PREFIX):
        raise ValueError("Unexpected archive directory: " + path)
    rel = path[len(SOURCE_PREFIX):]
    if not rel or path.endswith("/"):
        return None
    p = PurePosixPath(rel)
    if p.is_absolute() or ".." in p.parts or "\\" in rel:
        raise ValueError("Unsafe relative path: " + path)
    if rel == ".gitignore":
        return None
    if any(part.startswith(".") for part in p.parts):
        raise ValueError("Hidden/private source file: " + rel)
    if p.suffix.lower() not in ALLOWED:
        raise ValueError("Unexpected source type: " + rel)
    if any(phrase in p.name.lower() for phrase in ("secret", "cookie", "password", "browser_profile")):
        raise ValueError("Potential sensitive source: " + rel)
    return rel

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--zip", type=Path, required=True)
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    repo = args.repo.resolve()
    if not (repo / ".git").exists() or not (repo / "scanner" / "match_config.py").exists():
        raise SystemExit("STOP: --repo must be GoalPulzdev/ministaut Git working tree")
    if not args.zip.exists():
        raise SystemExit("STOP: Koteng V2.4 source ZIP not found")
    sha = hashlib.sha256(args.zip.read_bytes()).hexdigest()
    if sha != ZIP_SHA256:
        raise SystemExit("STOP: wrong archive SHA256 " + sha)
    files = {}
    with zipfile.ZipFile(args.zip) as archive:
        for item in archive.infolist():
            name = source_name(item.filename)
            if name is None:
                continue
            if name in files or item.file_size > 1500000:
                raise SystemExit("STOP: invalid or duplicate source " + name)
            files[name] = archive.read(item)
    missing = REQUIRED - set(files)
    if missing:
        raise SystemExit("STOP: incomplete package " + ", ".join(sorted(missing)))
    out = repo / TARGET
    for name, data in files.items():
        target = out / name
        if target.exists() and target.read_bytes() != data:
            raise SystemExit("STOP: archived baseline differs " + str(target))
    print("Verified Koteng V2.4 ZIP: " + sha + "; source files: " + str(len(files)))
    if not args.apply:
        print("DRY RUN. Re-run with --apply to write baseline.")
        return
    for name, data in files.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest = {"source_zip_sha256": ZIP_SHA256,
                "source_archive": "RBK_Koteng_V2_4_NY_SKJERM_KOMPLETT.zip",
                "status": "immutable reference; not production-deployed from this path",
                "files": {k: hashlib.sha256(v).hexdigest() for k, v in sorted(files.items())}}
    (out / "ARCHIVE_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Done: " + str(out) + "; review git status, test, then commit on agent branch.")

if __name__ == "__main__":
    main()
