# week2-assignment

This is my Module 2 assignment for MSAI-5523.

## Library Management System (SQLite)

| File | Purpose |
|---|---|
| `schema.sql` | Creates the 12 tables, foreign keys, CHECK constraints, indexes, triggers and views |
| `seed.sql` | Sample data (currently the 10 book categories) |
| `load_books.py` | Loads a random, reproducible sample of `books.csv` into Books, Authors and BookAuthors (`python load_books.py [count] [--seed N]`; default 300 books, seed 42) |
| `sample_data.py` | Fills the remaining tables with made-up sample data: publishers, staff, members, memberships, copies, loans, fines and reservations (`python sample_data.py [--seed N]`; default seed 2026). Runs once; does nothing if members, staff, copies or loans already exist |
| `link_books.py` | Gives each book a made-up publisher and category (title/author keywords, else random; `python link_books.py [--seed N]`). Only fills books that don't have them yet |
| `library.db` | The SQLite database built from the scripts above |
| `books.csv` | [goodbooks-10k](https://github.com/zygmuntz/goodbooks-10k) book list (10,000 titles) |

Build or update the database (all five are safe to re-run; they never
drop or overwrite existing tables or rows):

```
sqlite3 library.db < schema.sql
sqlite3 library.db < seed.sql
python load_books.py
python sample_data.py
python link_books.py
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

### Views
- **`vw_CurrentOverdueLoans`**: every loan that is overdue today, with the
  member's name, the copy's barcode, the book's title, the due date and
  `DaysOverdue`. A loan counts as overdue when it hasn't been returned
  (`ReturnDate IS NULL`) and its `DueDate` is before today. This is
  recalculated on every query instead of trusting the stored `LoanStatus`.
  Loans marked Lost are left out.

  ```
  SELECT * FROM vw_CurrentOverdueLoans ORDER BY DaysOverdue DESC;
  ```

### Sample data currently in `library.db`
| Table | Rows | Notes |
|---|---|---|
| Categories | 10 | From `seed.sql` |
| Books | 300 | Random sample of goodbooks-10k (seed 42); publisher and category made up by `link_books.py` |
| Authors / BookAuthors | 408 / 442 | From the same books |
| Publishers | 10 | Real publishing companies, randomly assigned to books (not who actually published them) |
| Staff | 6 | 5 Active, 1 Inactive |
| Members | 40 | 30 Active, 4 Expired, 3 Inactive, 3 Suspended |
| Memberships | 93 | Yearly periods, including past renewals |
| BookCopies | 486 | 1–3 per book; a few Lost, Damaged, In Repair or Reserved |
| Loans | 1,040 | About 18 months of history; 47 still out, 11 of them overdue on the day the data was generated, 3 lost |
| Fines | 253 | Overdue, lost-book, damaged-book and other charges, with mixed payment statuses |
| Reservations | 28 | Waiting, Ready for Pickup, Fulfilled, Cancelled and Expired |

People, addresses, emails (`@example.com`) and phone numbers (`555-01xx`)
are made up. Dates were generated relative to the day `sample_data.py` was
run, so `vw_CurrentOverdueLoans` returns more rows as time passes.
