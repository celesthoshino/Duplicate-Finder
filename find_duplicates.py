"""
Duplicate File Finder
---------------------
Finds files with exactly the same content, even if their names are different.
Put files in the "input" folder (or point it at any folder with -i), run the
script, and it writes a report to the "output" folder. It can also move the
extra copies out of the way. It never deletes anything.

    python find_duplicates.py                    # scan the input folder, then ask what to do
    python find_duplicates.py -i "D:\\Photos"     # scan any folder (and its subfolders)
    python find_duplicates.py --move             # move the extra copies to output/duplicates
    python find_duplicates.py --keep newest      # which copy to keep (default: oldest)

See README.md for all the details.
"""

import argparse
import csv
import hashlib
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# The input/output folders live next to this script, so it works no matter
# which folder you run it from.
BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

SKIP_NAMES = {"thumbs.db", "desktop.ini", ".ds_store"}  # little files the system makes in every folder
QUICK_CHECK_BYTES = 64 * 1024
CHUNK = 1024 * 1024


def size_text(size: float) -> str:
    for unit in ("bytes", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:,.0f} {unit}" if unit == "bytes" else f"{size:,.1f} {unit}"
        size /= 1024
    return ""


def parse_size(text: str) -> int:
    """'500' (bytes), '100KB', '5MB', '1GB' -> bytes."""
    text = text.strip().upper().replace(" ", "")
    for unit, factor in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024), ("B", 1)):
        if text.endswith(unit):
            text, multiplier = text[: -len(unit)], factor
            break
    else:
        multiplier = 1
    try:
        return int(float(text) * multiplier)
    except ValueError:
        raise argparse.ArgumentTypeError("use a size like 500KB, 5MB or 1GB") from None


def scan(folder: Path, skip_folder: Path, min_size: int):
    """Every file in folder and its subfolders: {size: [paths]}. Also returns (count, total bytes)."""
    by_size = defaultdict(list)
    count = total = 0
    for root, dirs, files in os.walk(folder):
        root_path = Path(root)
        # Don't look inside hidden folders (like .git) or this script's own output folder.
        dirs[:] = [d for d in dirs if not d.startswith(".") and (root_path / d).resolve() != skip_folder]
        for name in files:
            if name.startswith(".") or name.lower() in SKIP_NAMES:
                continue
            path = root_path / name
            try:
                if path.is_symlink():
                    continue
                size = path.stat().st_size
            except OSError:
                continue
            if size == 0 or size < min_size:
                continue  # empty files are all "the same", so they're skipped
            by_size[size].append(path)
            count += 1
            total += size
            if count % 5000 == 0:
                print(f"\r  scanned {count:,} files...", end="", flush=True)
    print("\r" + " " * 40 + "\r", end="")
    return by_size, count, total


def fingerprint(path: Path, quick: bool) -> str:
    """A fingerprint (hash) of the file's content. Same content always gives the same fingerprint."""
    digest = hashlib.blake2b(digest_size=20)
    with open(path, "rb") as f:
        if quick:
            digest.update(f.read(QUICK_CHECK_BYTES))
        else:
            while chunk := f.read(CHUNK):
                digest.update(chunk)
    return digest.hexdigest()


def split_by_fingerprint(groups: list, quick: bool, unreadable: list) -> list:
    """Split each group of possible duplicates by fingerprint. Groups of one are dropped."""
    result = []
    total = sum(len(g) for g in groups)
    done = 0
    for group in groups:
        by_print = defaultdict(list)
        for path in group:
            try:
                by_print[fingerprint(path, quick)].append(path)
            except OSError:
                unreadable.append(path)
            done += 1
            if done % 50 == 0 or done == total:
                print(f"\r  {'quick check' if quick else 'full check'}: {done:,}/{total:,} files",
                      end="", flush=True)
        result.extend(g for g in by_print.values() if len(g) > 1)
    print("\r" + " " * 50 + "\r", end="")
    return result


def find_duplicates(by_size: dict, unreadable: list) -> list:
    # Step 1: only files with the same size can be the same.
    groups = [paths for paths in by_size.values() if len(paths) > 1]
    # Step 2: a quick look at the start of each file rules out most of the rest.
    groups = split_by_fingerprint(groups, quick=True, unreadable=unreadable)
    # Step 3: read the whole file to be completely sure.
    return split_by_fingerprint(groups, quick=False, unreadable=unreadable)


COPY_NAME = re.compile(r"\(\d+\)$|[ _-]copy( \(?\d+\)?)?$|^copy of ", re.IGNORECASE)


def choose_keeper(group: list, rule: str) -> list:
    """Order the copies so the one to keep comes first."""
    def modified(p):
        return p.stat().st_mtime

    def tie_break(p):
        # Prefer names that don't look like copies ("photo (1).jpg", "report - Copy.docx",
        # "Copy of notes.txt"), then the shortest path, then alphabetical.
        return (bool(COPY_NAME.search(p.stem)), len(str(p)), str(p).lower())
    if rule == "oldest":
        return sorted(group, key=lambda p: (modified(p), *tie_break(p)))
    if rule == "newest":
        return sorted(group, key=lambda p: (-modified(p), *tie_break(p)))
    return sorted(group, key=tie_break)  # "shortest-path"


def write_reports(groups: list, folder: Path, out_dir: Path, scanned: int):
    wasted = sum(g[0].stat().st_size * (len(g) - 1) for g in groups)
    extras = sum(len(g) - 1 for g in groups)
    txt_path, csv_path = out_dir / "duplicates_report.txt", out_dir / "duplicates_report.csv"

    lines = [f"Duplicate files in: {folder}",
             f"Checked on {datetime.now():%Y-%m-%d %H:%M}. {scanned:,} files checked.",
             f"Found {len(groups)} group(s) of identical files. The {extras} extra copies use {size_text(wasted)}.",
             "",
             'In each group, the copy marked "keep" stays where it is, and the ones marked "extra"',
             "are moved if you choose to move them.", ""]
    for number, group in enumerate(groups, start=1):
        size = group[0].stat().st_size
        lines.append(f"Group {number}: {len(group)} copies of {size_text(size)} each "
                     f"({size_text(size * (len(group) - 1))} wasted)")
        for i, path in enumerate(group):
            stamp = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            lines.append(f"  {'keep ' if i == 0 else 'extra'}  {stamp}  {path}")
        lines.append("")
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["group", "action", "size_bytes", "modified", "path"])
        for number, group in enumerate(groups, start=1):
            for i, path in enumerate(group):
                stamp = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow([number, "keep" if i == 0 else "extra", path.stat().st_size, stamp, str(path)])
    return txt_path, csv_path, extras, wasted


def move_extras(groups: list, folder: Path, out_dir: Path) -> int:
    """Move every extra copy into out_dir/duplicates, keeping its folder structure so it's easy to put back."""
    target_root = out_dir / "duplicates"
    log_path = out_dir / "moved_files.csv"
    new_log = not log_path.exists()
    moved = 0
    with open(log_path, "a", newline="", encoding="utf-8-sig") as f:
        log = csv.writer(f)
        if new_log:
            log.writerow(["moved_on", "original_location", "moved_to"])
        for group in groups:
            for path in group[1:]:
                dest = target_root / path.relative_to(folder)
                candidate, number = dest, 2
                while candidate.exists():
                    candidate = dest.with_name(f"{dest.stem} ({number}){dest.suffix}")
                    number += 1
                try:
                    candidate.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(path), str(candidate))
                except OSError as error:
                    print(f"  [fail] couldn't move {path}: {error}")
                    continue
                log.writerow([f"{datetime.now():%Y-%m-%d %H:%M:%S}", str(path), str(candidate)])
                moved += 1
    return moved


def main():
    parser = argparse.ArgumentParser(description="Find files with exactly the same content, even with different names.",
                                     epilog="Nothing is ever deleted. --move only moves extra copies aside.")
    parser.add_argument("--move", action="store_true",
                        help="move the extra copies to output/duplicates without asking")
    parser.add_argument("--report-only", action="store_true", help="only write the report, don't ask about moving")
    parser.add_argument("--keep", choices=["oldest", "newest", "shortest-path"], default="oldest",
                        help="which copy in each group stays where it is (default: oldest)")
    parser.add_argument("--min-size", type=parse_size, default=1, metavar="SIZE",
                        help="ignore files smaller than this, e.g. 100KB or 1MB (default: check everything)")
    parser.add_argument("-i", "--input", type=Path, default=INPUT_DIR,
                        help="folder to check, including subfolders (default: the input folder)")
    parser.add_argument("-o", "--output", type=Path, default=OUTPUT_DIR,
                        help="folder for the report and moved copies (default: the output folder)")
    args = parser.parse_args()

    args.input.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    folder = args.input.resolve()

    print(f"Checking: {folder} (and its subfolders)")
    by_size, scanned, total = scan(folder, args.output.resolve(), args.min_size)
    if not scanned:
        print("No files found. Put the files you want checked in that folder (or use -i), then run this again.")
        return
    print(f"Found {scanned:,} files ({size_text(total)}). Comparing...")

    unreadable = []
    groups = find_duplicates(by_size, unreadable)
    for path in unreadable:
        print(f"  [skip] couldn't read {path}")
    if not groups:
        print("\nNo duplicates found. Every file is unique.")
        return

    groups = [choose_keeper(g, args.keep) for g in groups]
    groups.sort(key=lambda g: g[0].stat().st_size * (len(g) - 1), reverse=True)  # biggest waste first
    txt_path, csv_path, extras, wasted = write_reports(groups, folder, args.output, scanned)

    print(f"\nFound {len(groups)} group(s) of identical files: {extras} extra copies using {size_text(wasted)}.")
    for group in groups[:10]:
        size = group[0].stat().st_size
        print(f"\n  {len(group)} copies of {size_text(size)}:")
        for i, path in enumerate(group):
            shown = path.relative_to(folder)
            print(f"    {'keep ' if i == 0 else 'extra'}  {shown}")
    if len(groups) > 10:
        print(f"\n  ... and {len(groups) - 10} more group(s). See the full report.")
    print(f"\nFull report: {txt_path}\n(also as a spreadsheet: {csv_path.name})")

    if not args.move:
        if args.report_only:
            return
        answer = input(f"\nMove the {extras} extra copies ({size_text(wasted)}) to "
                       f"{args.output / 'duplicates'}? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Nothing was moved.")
            return
    moved = move_extras(groups, folder, args.output)
    print(f"\nDone: {moved} extra copies moved to {args.output / 'duplicates'}.")
    print("They keep their folder structure, so you can see where each came from. Delete them when you're sure,")
    print("or move them back. Every move is listed in moved_files.csv.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(1)
