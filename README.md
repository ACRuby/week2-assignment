# week2-assignment

This is my Module 2 assignment for MSAI-5523.

## Library Management System (SQLite)

| File | Purpose |
|---|---|
| `schema.sql` | Creates the 12 tables, foreign keys, CHECK constraints, indexes and triggers |
| `seed.sql` | Sample data (currently the 10 book categories) |
| `load_books.py` | Loads a random, reproducible sample of `books.csv` into Books, Authors and BookAuthors (`python load_books.py [count] [--seed N]`; default 300 books, seed 42) |
| `library.db` | The SQLite database built from the scripts above (currently 300 books, 408 authors) |
| `books.csv` | [goodbooks-10k](https://github.com/zygmuntz/goodbooks-10k) book list (10,000 titles) |

Build or update the database (all three are safe to re-run; they never
drop or overwrite existing tables or rows):

```
sqlite3 library.db < schema.sql
sqlite3 library.db < seed.sql
python load_books.py
```

Tables: Categories, Publishers, Authors, Staff, Members, Books, BookAuthors,
BookCopies, Memberships, Loans, Fines, Reservations.

### SQLite-specific notes
- **Foreign keys are off by default in SQLite.** Run `PRAGMA foreign_keys = ON;`
  at the start of every session/connection, or they won't be enforced.
- Dates are stored as `YYYY-MM-DD` text and validated by CHECK constraints.
  Defaults use the local date.
- Deleting a book, member, staff member, category or publisher that still has
  related records is blocked (`ON DELETE RESTRICT`). Change its status instead.
- Rules that need another table or apply to only some rows use SQLite
  equivalents instead of plain constraints:
  - Partial unique indexes (SQLite's version of filtered indexes) allow at most
    one unreturned loan per copy, one open reservation per member per title,
    and one overdue fine per loan.
  - Triggers block a new loan when the copy is On Loan, Lost, Damaged or In
    Repair. They also keep `BookCopies.CopyStatus` up to date: On Loan at
    checkout, Available on return, Lost when a loan is marked Lost.
