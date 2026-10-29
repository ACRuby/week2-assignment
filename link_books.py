"""Give every book in library.db a made-up publisher and category.

    python link_books.py             # seed 2026
    python link_books.py --seed 7

books.csv doesn't say who published a book or what genre it is, so these are
invented sample values, not real facts about the books. Categories come from
keywords in the title or author when one matches (so "Murder on the..." lands
in Mystery), otherwise a weighted random pick. Publishers are random.

Only fills books whose PublisherID or CategoryID is still empty, so re-running
it never changes a book that already has them.
"""

import argparse
import random
import re
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Checked in order; the first category with a matching keyword wins.
# Keywords are matched as whole words/phrases, case-insensitively, against
# "title | author names" (so 'war' doesn't match 'Edward' or 'award').
CATEGORY_KEYWORDS = [
    ("Children's Literature", ['disney', 'ramona', 'dr. seuss', 'magic tree house', 'junie b',
                               'berenstain', 'beverly cleary', 'roald dahl', 'eric carle', 'curious george',
                               'diary of a wimpy kid', 'mo willems', 'shel silverstein', 'little golden']),
    ('Science Fiction', ['star wars', 'star trek', 'dune', 'robot', 'galaxy', 'mars', 'alien', 'android',
                         'dystopia', 'divergent', 'hunger games', 'philip k. dick', 'isaac asimov',
                         'orson scott card', 'arthur c. clarke', 'ray bradbury']),
    ('Fantasy', ['harry potter', 'dragon', 'magic', 'witch', 'wizard', 'throne', 'sword', 'fae', 'faerie',
                 'vampire', 'vampires', 'sorcerer', 'shadowhunter', 'tolkien', 'percy jackson', 'narnia', 'kingdom',
                 'brandon sanderson', 'terry pratchett', 'neil gaiman']),
    ('Mystery', ['murder', 'mystery', 'detective', 'kill', 'dead', 'death', 'crime', 'alex cross', 'plum',
                 'agatha christie', 'james patterson', 'j.d. robb', 'michael connelly', 'lee child',
                 'harlan coben', 'sherlock', 'thriller', 'gone girl']),
    ('Romance', ['love', 'kiss', 'bride', 'rapture', 'heart', 'wedding', 'nora roberts', 'nicholas sparks',
                 'jude deveraux', 'julia quinn', 'colleen hoover', 'sylvia day', 'e.l. james']),
    ('Biography', ['memoir', 'autobiography', 'biography', 'life of', 'a true story', 'diary of',
                   'my life', 'letters']),
    ('History', ['history', 'war', 'civil', 'empire', 'revolution', 'holocaust', 'ancient', 'century']),
    ('Technology', ['relativity', 'science', 'computer', 'code', 'data', 'physics', 'universe',
                    'engineer', 'internet', 'technology', 'brain']),
    ('Nonfiction', ['how to', 'guide', 'habits', 'power of', 'lessons', 'essays', 'mind',
                    'success', 'money', 'leadership', 'bible', 'god']),
]

# Fallback when no keyword matches: mostly general fiction.
FALLBACK_WEIGHTS = {'Fiction': 10, 'Fantasy': 2, 'Mystery': 2, 'Romance': 2, 'Science Fiction': 1,
                    "Children's Literature": 1, 'Nonfiction': 1, 'Biography': 1, 'History': 1}


def pick_category(text, rng):
    for category, words in CATEGORY_KEYWORDS:
        if any(re.search(r'\b' + re.escape(w) + r'\b', text, re.IGNORECASE) for w in words):
            return category
    return rng.choices(list(FALLBACK_WEIGHTS), list(FALLBACK_WEIGHTS.values()))[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--seed', type=int, default=2026)
    parser.add_argument('--db', default=str(HERE / 'library.db'))
    args = parser.parse_args()
    rng = random.Random(args.seed)

    con = sqlite3.connect(args.db)
    con.execute('PRAGMA foreign_keys = ON')
    categories = dict(con.execute('SELECT CategoryName, CategoryID FROM Categories'))
    publishers = [r[0] for r in con.execute('SELECT PublisherID FROM Publishers ORDER BY PublisherID')]
    if not categories or not publishers:
        print('Need categories and publishers first; run seed.sql and sample_data.py.')
        return

    books = con.execute("""
        SELECT b.BookID, b.Title || ' | ' || coalesce(group_concat(coalesce(a.FirstName || ' ', '') || a.LastName, ', '), ''),
               b.PublisherID, b.CategoryID
        FROM Books b
        LEFT JOIN BookAuthors ba ON ba.BookID = b.BookID
        LEFT JOIN Authors a ON a.AuthorID = ba.AuthorID
        WHERE b.PublisherID IS NULL OR b.CategoryID IS NULL
        GROUP BY b.BookID
        ORDER BY b.BookID""").fetchall()

    with con:
        for book_id, text, publisher_id, category_id in books:
            con.execute('UPDATE Books SET PublisherID = ?, CategoryID = ? WHERE BookID = ?',
                        (publisher_id or rng.choice(publishers),
                         category_id or categories[pick_category(text, rng)],
                         book_id))
    con.close()
    print(f'Linked {len(books)} books to a publisher and category (seed {args.seed}).')


if __name__ == '__main__':
    main()
