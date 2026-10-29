"""Consistent SQLite backup, including committed WAL data; never overwrites a file."""
import argparse
from pathlib import Path
import sqlite3
import tempfile
import zipfile
from contextlib import closing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parent/'data'/'shop.sqlite3')
    args = parser.parse_args()
    if not args.source.is_file():
        raise SystemExit('Source database does not exist.')
    if args.destination.exists():
        raise SystemExit('Destination already exists; choose a new backup filename.')
    # Exclusive creation and restrictive permissions before opening SQLite.
    import os
    fd = os.open(args.destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        with closing(sqlite3.connect(args.source.resolve().as_uri()+'?mode=ro', uri=True)) as source:
            if args.destination.suffix.lower()=='.zip':
                with tempfile.TemporaryDirectory() as folder:
                    snapshot=Path(folder)/'shop.sqlite3'
                    with closing(sqlite3.connect(snapshot)) as destination:
                        source.backup(destination)
                        tables={r[0] for r in destination.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                        files=[r[0] for r in destination.execute('SELECT filename FROM media')] if 'media' in tables else []
                    with zipfile.ZipFile(args.destination,'w',zipfile.ZIP_DEFLATED) as archive:
                        archive.write(snapshot,'shop.sqlite3')
                        for filename in files:
                            media=args.source.parent/'media'/filename
                            if media.parent.resolve()!=(args.source.parent/'media').resolve() or not media.is_file():
                                raise RuntimeError('A media file is missing. Pause admin changes and retry the backup.')
                            archive.write(media,'media/'+filename)
            else:
                with closing(sqlite3.connect(args.destination)) as destination:
                    source.backup(destination)
                print('Database-only backup. Use a .zip destination to include uploaded images and videos.')
    except Exception:
        args.destination.unlink(missing_ok=True)
        raise
    print('Backup completed.')


if __name__ == '__main__':
    main()
