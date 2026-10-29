"""Load a random sample of books from books.csv (goodbooks-10k) into library.db.

    python load_books.py              # 300 books, seed 42
    python load_books.py 50 --seed 7  # 50 different books

Fills Books, Authors and BookAuthors. The sample is reproducible for a given
seed. Books already in the database (same ISBN, or same title and year when
there's no ISBN) are skipped, so re-running never creates duplicates. Authors
are matched by first + last name and reused across books.

books.csv has no publisher, category, edition or page-count data, so those
columns are left NULL.
"""

import argparse
import csv
import random
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUFFIXES = {'Jr.', 'Jr', 'Sr.', 'Sr', 'II', 'III', 'IV'}
# Lower-case-style name particles that belong with the surname ("Le Guin", "de Balzac").
PARTICLES = {'de', 'De', 'da', 'Da', 'del', 'della', 'di', 'Di', 'du', 'Du', 'la', 'La',
             'le', 'Le', 'van', 'Van', 'von', 'Von', 'der', 'den', 'ten', 'St.'}


def split_name(full_name):
    """'Ursula K. Le Guin' -> ('Ursula K.', 'Le Guin'); 'Homer' -> (None, 'Homer')."""
    parts = full_name.split()
    if len(parts) == 1:
        return None, parts[0]
    last = [parts.pop()]
    if last[0] in SUFFIXES and len(parts) > 1:
        last.insert(0, parts.pop())
    while len(parts) > 1 and parts[-1] in PARTICLES:
        last.insert(0, parts.pop())
    return ' '.join(parts), ' '.join(last)


def clean_isbn(raw):
    # The CSV stored ISBN-10s as numbers, dropping leading zeros; restore them.
    raw = raw.strip()
    return raw.zfill(10) if raw else None


def clean_year(raw):
    # Ancient works have negative years, which the schema rejects; store as unknown.
    if not raw.strip():
        return None
    year = int(float(raw))
    return year if year > 0 else None


def get_or_create_author(cur, first, last):
    row = cur.execute('SELECT AuthorID FROM Authors WHERE FirstName IS ? AND LastName IS ?',
                      (first, last)).fetchone()
    if row:
        return row[0], False
    cur.execute('INSERT INTO Authors (FirstName, LastName) VALUES (?, ?)', (first, last))
    return cur.lastrowid, True


def book_exists(cur, isbn, title, year):
    if isbn:
        sql, args = 'SELECT 1 FROM Books WHERE ISBN = ?', (isbn,)
    else:
        sql, args = 'SELECT 1 FROM Books WHERE Title = ? AND PublicationYear IS ?', (title, year)
    return cur.execute(sql, args).fetchone() is not None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('count', type=int, nargs='?', default=300)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--db', default=str(HERE / 'library.db'))
    parser.add_argument('--csv', default=str(HERE / 'books.csv'))
    args = parser.parse_args()

    with open(args.csv, encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    sample = random.Random(args.seed).sample(rows, args.count)

    con = sqlite3.connect(args.db)
    con.execute('PRAGMA foreign_keys = ON')
    cur = con.cursor()
    books = skipped = new_authors = links = 0
    with con:  # one transaction: all rows load, or none do
        for r in sample:
            isbn, title, year = clean_isbn(r['isbn']), r['title'].strip(), clean_year(r['original_publication_year'])
            if book_exists(cur, isbn, title, year):
                skipped += 1
                continue
            cur.execute('INSERT INTO Books (ISBN, Title, PublicationYear, Language) VALUES (?, ?, ?, ?)',
                        (isbn, title, year, r['language_code'].strip() or None))
            book_id = cur.lastrowid
            books += 1
            # dict.fromkeys drops names listed twice on one book, keeping order.
            names = dict.fromkeys(n.strip() for n in r['authors'].split(',') if n.strip())
            for order, name in enumerate(names, start=1):
                author_id, created = get_or_create_author(cur, *split_name(name))
                new_authors += created
                # Two different spellings can resolve to the same author; link once.
                cur.execute('INSERT OR IGNORE INTO BookAuthors (BookID, AuthorID, AuthorOrder) '
                            'VALUES (?, ?, ?)', (book_id, author_id, order))
                links += cur.rowcount
    con.close()
    print(f'Sampled {args.count} rows (seed {args.seed}): added {books} books, '
          f'skipped {skipped} already present, {new_authors} new authors, {links} book-author links.')


if __name__ == '__main__':
    main()
