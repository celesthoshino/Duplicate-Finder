# Duplicate File Finder

Finds files with exactly the same content, even when they have different names or are in different folders. For
example, the same photo saved as `IMG_0001.jpg`, `IMG_0001 (1).jpg` and `backup/holiday.jpg`. It writes a report,
and if you want, moves the extra copies out of the way so you can free up space.

**It never deletes anything.** Extra copies are only moved to the `output` folder, where you can check them before
deleting them yourself.

## Folder layout

```
duplicate_finder/
├── find_duplicates.py   the script
├── requirements.txt     nothing to install, but here for consistency
├── README.md            this file
├── input/               put files here to check them (or check any folder with -i)
└── output/              the report, and the extra copies if you move them
    ├── duplicates_report.txt
    ├── duplicates_report.csv
    ├── moved_files.csv
    └── duplicates/
```

## Setup (one time)

Install **Python 3.9 or newer** from https://www.python.org/downloads/
(on Windows, tick "Add Python to PATH" during install). Nothing else is needed. The script only uses what comes with
Python.

## How to use

1. Either copy files into the `input` folder, or check a folder where it is with `-i` (see below).
2. Open a terminal in the `duplicate_finder` folder and run:

   ```
   python find_duplicates.py
   ```

   or, to check a folder somewhere else (including all its subfolders):

   ```
   python find_duplicates.py -i "D:\Photos"
   ```

3. It shows the biggest groups of duplicates and writes the full list to `output/duplicates_report.txt`.
4. It asks whether to move the extra copies. Type `y` to move them to `output/duplicates`, or press Enter to leave
   everything as it is.
5. Look through `output/duplicates`. When you're happy, delete it to free up the space.

| Command | What it does |
|---|---|
| `python find_duplicates.py` | Checks the `input` folder, then asks what to do |
| `python find_duplicates.py -i "D:\Photos"` | Checks any folder and its subfolders |
| `python find_duplicates.py --report-only` | Only writes the report, doesn't ask about moving |
| `python find_duplicates.py --move` | Moves the extra copies without asking |
| `python find_duplicates.py --keep newest` | Keeps the newest copy of each file instead of the oldest |
| `python find_duplicates.py --min-size 1MB` | Ignores files smaller than 1 MB (faster, and skips little files) |
| `python find_duplicates.py --help` | Shows all options |

## Options

| Option | Default | Meaning |
|---|---|---|
| `--move` | off | Move the extra copies to `output/duplicates` without asking |
| `--report-only` | off | Only write the report |
| `--keep` | `oldest` | Which copy in each group stays where it is: `oldest`, `newest`, or `shortest-path` (the one in the least deep folder) |
| `--min-size` | everything | Ignore files smaller than this, like `500KB`, `1MB` or `1GB` |
| `-i`, `--input` | `input` folder | Folder to check. Subfolders are checked too |
| `-o`, `--output` | `output` folder | Where the report and moved copies go |

## Which copy is kept

In each group of identical files, one copy stays where it is and the others are the "extra" copies. By default the
**oldest** one is kept (by the date it was last changed), since that's usually the original. If the dates are the same,
it prefers:

1. a name that doesn't look like a copy. `photo.jpg` is kept over `photo (1).jpg`, `photo - Copy.jpg` or
   `Copy of photo.jpg`;
2. then the copy in the least deep folder;
3. then alphabetical order.

The report shows which copy is `keep` and which are `extra` before anything is moved.

## The report

- **`duplicates_report.txt`** lists every group, biggest wasted space first, with the date and full location of each
  copy.
- **`duplicates_report.csv`** has the same thing as a spreadsheet, to sort and filter in Excel.
- **`moved_files.csv`** records every file that was moved: where it was and where it went.

## Good to know

- **Nothing is ever deleted.** Moving is the most it does, and only when you say yes (or use `--move`).
- **Only exact copies count.** Files must be identical byte for byte. A photo saved again at a different size or
  quality is a different file, even if it looks the same.
- **Names don't matter.** Files are compared by their content, not their names or dates.
- **Moved copies keep their folders.** A copy from `D:\Photos\2023\beach.jpg` goes to
  `output/duplicates/2023/beach.jpg`, so you can always tell where it came from and move it back.
- **It's fast on big folders.** Only files of exactly the same size are compared, and those are first checked by
  their beginning before reading the whole file.
- **Skipped:** empty files, hidden files and folders (starting with `.`, like `.git`), and little system files like
  `Thumbs.db` and `desktop.ini`. The `output` folder is skipped too if it's inside the folder being checked.
- **Running it again after moving** finds nothing new, because the extra copies are gone from the checked folder.

## Troubleshooting

**`No files found`**

Put files in the `input` folder, or use `-i` with the folder you want to check. With `--min-size`, smaller files are
ignored.

**`couldn't read ...`**

The file is open in another program, or you don't have permission to read it. It's skipped, and the rest are still
checked.

**`couldn't move ...`**

The file is open in another program, or it's read-only. Close the program and run it again. Files already moved
stay moved.

**It's slow**

Very large folders, especially with many big files of the same size (like videos), take a while because those have to
be read completely. `--min-size` can speed it up by skipping small files.

**`'python' is not recognized`**

Python isn't on your PATH. On Windows, try `py find_duplicates.py` instead, or reinstall Python with "Add Python to PATH" ticked.
