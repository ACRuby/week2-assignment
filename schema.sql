-- Library Management System schema (SQLite)
--
-- Safe to re-run: every object uses IF NOT EXISTS, so running this against an
-- existing library.db never drops or overwrites tables or data.
--
--   sqlite3 library.db < schema.sql
--
-- Conventions:
--   * PascalCase table and column names; INTEGER PRIMARY KEY ids (auto-generated).
--   * Dates are TEXT in ISO-8601 'YYYY-MM-DD' form. CHECK (date(x, '+0 days') IS x)
--     rejects anything that isn't a real calendar date in that format; the
--     '+0 days' makes older SQLite builds roll e.g. Feb 30 over to Mar 1, so it
--     fails the match. Default dates use the computer's local date, not UTC.
--   * Money is NUMERIC (stored as a number, two decimal places by convention).
--   * Foreign keys use ON DELETE RESTRICT so history (loans, fines, memberships,
--     reservations) can't be deleted out from under a book or member. Retire
--     records with their status column instead of deleting them.
--   * Not declared STRICT, so the file stays readable by older SQLite builds
--     (e.g. Python 3.9's bundled SQLite 3.33).
--
-- SQLite only enforces foreign keys when this is on, and it must be set again
-- on every new connection:
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Lookup / reference tables (no dependencies)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Categories (
    CategoryID   INTEGER PRIMARY KEY,
    CategoryName TEXT    NOT NULL UNIQUE CHECK (length(trim(CategoryName)) > 0),
    Description  TEXT
);

CREATE TABLE IF NOT EXISTS Publishers (
    PublisherID   INTEGER PRIMARY KEY,
    PublisherName TEXT    NOT NULL CHECK (length(trim(PublisherName)) > 0),
    City          TEXT,
    State         TEXT,
    Country       TEXT,
    Website       TEXT
);

CREATE TABLE IF NOT EXISTS Authors (
    AuthorID    INTEGER PRIMARY KEY,
    FirstName   TEXT,
    LastName    TEXT,
    BirthYear   INTEGER,
    DeathYear   INTEGER,
    Nationality TEXT,
    -- An author needs at least one name part (single-name authors, e.g. "Homer").
    CHECK (FirstName IS NOT NULL OR LastName IS NOT NULL),
    CHECK (DeathYear IS NULL OR BirthYear IS NULL OR DeathYear >= BirthYear)
);

CREATE TABLE IF NOT EXISTS Staff (
    StaffID     INTEGER PRIMARY KEY,
    FirstName   TEXT    NOT NULL CHECK (length(trim(FirstName)) > 0),
    LastName    TEXT    NOT NULL CHECK (length(trim(LastName)) > 0),
    Email       TEXT,
    JobTitle    TEXT,
    HireDate    TEXT    CHECK (HireDate IS NULL OR date(HireDate, '+0 days') IS HireDate),
    StaffStatus TEXT    NOT NULL DEFAULT 'Active'
                        CHECK (StaffStatus IN ('Active', 'Inactive'))
);

CREATE TABLE IF NOT EXISTS Members (
    MemberID       INTEGER PRIMARY KEY,
    FirstName      TEXT    NOT NULL CHECK (length(trim(FirstName)) > 0),
    LastName       TEXT    NOT NULL CHECK (length(trim(LastName)) > 0),
    -- Not UNIQUE: family members may share one email address.
    Email          TEXT,
    Phone          TEXT,
    StreetAddress  TEXT,
    City           TEXT,
    State          TEXT,
    PostalCode     TEXT,
    DateRegistered TEXT    NOT NULL DEFAULT (date('now', 'localtime'))
                           CHECK (date(DateRegistered, '+0 days') IS DateRegistered),
    MemberStatus   TEXT    NOT NULL DEFAULT 'Active'
                           CHECK (MemberStatus IN ('Active', 'Inactive', 'Suspended', 'Expired'))
);

-- ---------------------------------------------------------------------------
-- Catalog
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Books (
    BookID          INTEGER PRIMARY KEY,
    ISBN            TEXT    UNIQUE,   -- UNIQUE still allows many NULLs
    Title           TEXT    NOT NULL CHECK (length(trim(Title)) > 0),
    PublicationYear INTEGER CHECK (PublicationYear IS NULL OR PublicationYear > 0),
    PublisherID     INTEGER REFERENCES Publishers (PublisherID) ON DELETE RESTRICT,
    CategoryID      INTEGER REFERENCES Categories (CategoryID)  ON DELETE RESTRICT,
    Edition         TEXT,
    Language        TEXT,
    PageCount       INTEGER CHECK (PageCount IS NULL OR PageCount > 0),
    DateAdded       TEXT    NOT NULL DEFAULT (date('now', 'localtime'))
                            CHECK (date(DateAdded, '+0 days') IS DateAdded)
);

CREATE TABLE IF NOT EXISTS BookAuthors (
    BookID      INTEGER NOT NULL REFERENCES Books (BookID)     ON DELETE RESTRICT,
    AuthorID    INTEGER NOT NULL REFERENCES Authors (AuthorID) ON DELETE RESTRICT,
    AuthorOrder INTEGER NOT NULL DEFAULT 1 CHECK (AuthorOrder > 0),
    PRIMARY KEY (BookID, AuthorID),
    -- Two authors can't both be "first" on the same book.
    UNIQUE (BookID, AuthorOrder)
);

CREATE TABLE IF NOT EXISTS BookCopies (
    CopyID          INTEGER PRIMARY KEY,
    BookID          INTEGER NOT NULL REFERENCES Books (BookID) ON DELETE RESTRICT,
    Barcode         TEXT    NOT NULL UNIQUE CHECK (length(trim(Barcode)) > 0),
    AcquisitionDate TEXT    CHECK (AcquisitionDate IS NULL OR date(AcquisitionDate, '+0 days') IS AcquisitionDate),
    Condition       TEXT,
    ShelfLocation   TEXT,
    ReplacementCost NUMERIC CHECK (ReplacementCost IS NULL OR ReplacementCost >= 0),
    CopyStatus      TEXT    NOT NULL DEFAULT 'Available'
                            CHECK (CopyStatus IN ('Available', 'On Loan', 'Lost',
                                                  'Damaged', 'In Repair', 'Reserved'))
);

-- ---------------------------------------------------------------------------
-- Membership and circulation
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Memberships (
    MembershipID     INTEGER PRIMARY KEY,
    MemberID         INTEGER NOT NULL REFERENCES Members (MemberID) ON DELETE RESTRICT,
    MembershipType   TEXT    NOT NULL
                             CHECK (MembershipType IN ('Adult', 'Senior', 'Student', 'Child',
                                                       'Family', 'Free Community Membership')),
    StartDate        TEXT    NOT NULL CHECK (date(StartDate, '+0 days') IS StartDate),
    ExpirationDate   TEXT    CHECK (ExpirationDate IS NULL OR
                                    (date(ExpirationDate, '+0 days') IS ExpirationDate AND ExpirationDate >= StartDate)),
    MembershipStatus TEXT    NOT NULL DEFAULT 'Active'
                             CHECK (MembershipStatus IN ('Active', 'Expired', 'Suspended', 'Cancelled')),
    FeePaid          NUMERIC NOT NULL DEFAULT 0 CHECK (FeePaid >= 0),
    PaymentDate      TEXT    CHECK (PaymentDate IS NULL OR date(PaymentDate, '+0 days') IS PaymentDate)
);

CREATE TABLE IF NOT EXISTS Loans (
    LoanID       INTEGER PRIMARY KEY,
    CopyID       INTEGER NOT NULL REFERENCES BookCopies (CopyID) ON DELETE RESTRICT,
    MemberID     INTEGER NOT NULL REFERENCES Members (MemberID)  ON DELETE RESTRICT,
    CheckoutDate TEXT    NOT NULL DEFAULT (date('now', 'localtime'))
                         CHECK (date(CheckoutDate, '+0 days') IS CheckoutDate),
    DueDate      TEXT    NOT NULL CHECK (date(DueDate, '+0 days') IS DueDate AND DueDate >= CheckoutDate),
    -- NULL while the book is still out.
    ReturnDate   TEXT    CHECK (ReturnDate IS NULL OR
                                (date(ReturnDate, '+0 days') IS ReturnDate AND ReturnDate >= CheckoutDate)),
    RenewalCount INTEGER NOT NULL DEFAULT 0 CHECK (RenewalCount >= 0),
    -- Stored for record-keeping; use the overdue view rather than trusting
    -- 'Overdue' here, since it goes stale as soon as the date changes.
    LoanStatus   TEXT    NOT NULL DEFAULT 'Checked Out'
                         CHECK (LoanStatus IN ('Checked Out', 'Overdue', 'Returned', 'Lost')),
    -- NULL = unknown staff member or self-service checkout/return.
    CheckedOutBy INTEGER REFERENCES Staff (StaffID) ON DELETE RESTRICT,
    ReturnedTo   INTEGER REFERENCES Staff (StaffID) ON DELETE RESTRICT,
    -- A returned loan must have a return date, and an unreturned one must not.
    CHECK ((LoanStatus = 'Returned') = (ReturnDate IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS Fines (
    FineID         INTEGER PRIMARY KEY,
    LoanID         INTEGER NOT NULL REFERENCES Loans (LoanID) ON DELETE RESTRICT,
    FineType       TEXT    NOT NULL
                           CHECK (FineType IN ('Overdue', 'Lost Book', 'Damaged Book', 'Other')),
    FineDate       TEXT    NOT NULL DEFAULT (date('now', 'localtime'))
                           CHECK (date(FineDate, '+0 days') IS FineDate),
    AmountAssessed NUMERIC NOT NULL CHECK (AmountAssessed >= 0),
    -- No credits/refunds: payments can't exceed the charge.
    AmountPaid     NUMERIC NOT NULL DEFAULT 0
                           CHECK (AmountPaid >= 0 AND AmountPaid <= AmountAssessed),
    PaymentStatus  TEXT    NOT NULL DEFAULT 'Unpaid'
                           CHECK (PaymentStatus IN ('Unpaid', 'Partially Paid', 'Paid', 'Waived')),
    PaymentDate    TEXT    CHECK (PaymentDate IS NULL OR
                                  (date(PaymentDate, '+0 days') IS PaymentDate AND PaymentDate >= FineDate)),
    -- Keep the status consistent with the amounts. Waived is allowed at any
    -- paid amount; its outstanding balance is treated as 0.
    CHECK (PaymentStatus = 'Waived'
        OR (PaymentStatus = 'Unpaid'         AND AmountPaid = 0)
        OR (PaymentStatus = 'Partially Paid' AND AmountPaid > 0 AND AmountPaid < AmountAssessed)
        OR (PaymentStatus = 'Paid'           AND AmountPaid = AmountAssessed))
);

CREATE TABLE IF NOT EXISTS Reservations (
    ReservationID     INTEGER PRIMARY KEY,
    MemberID          INTEGER NOT NULL REFERENCES Members (MemberID) ON DELETE RESTRICT,
    BookID            INTEGER NOT NULL REFERENCES Books (BookID)     ON DELETE RESTRICT,
    ReservationDate   TEXT    NOT NULL DEFAULT (date('now', 'localtime'))
                              CHECK (date(ReservationDate, '+0 days') IS ReservationDate),
    ExpirationDate    TEXT    CHECK (ExpirationDate IS NULL OR
                                     (date(ExpirationDate, '+0 days') IS ExpirationDate AND ExpirationDate >= ReservationDate)),
    ReservationStatus TEXT    NOT NULL DEFAULT 'Waiting'
                              CHECK (ReservationStatus IN ('Waiting', 'Ready for Pickup', 'Fulfilled',
                                                           'Cancelled', 'Expired')),
    NotificationDate  TEXT    CHECK (NotificationDate IS NULL OR
                                     (date(NotificationDate, '+0 days') IS NotificationDate AND NotificationDate >= ReservationDate))
);

-- ---------------------------------------------------------------------------
-- Indexes
--
-- Not created because a constraint already provides one:
--   Books.ISBN, BookCopies.Barcode, Categories.CategoryName (UNIQUE)
--   BookAuthors.BookID (leading column of the primary key)
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS IX_Books_Title       ON Books (Title);
CREATE INDEX IF NOT EXISTS IX_Books_CategoryID  ON Books (CategoryID);
CREATE INDEX IF NOT EXISTS IX_Books_PublisherID ON Books (PublisherID);

CREATE INDEX IF NOT EXISTS IX_BookAuthors_AuthorID ON BookAuthors (AuthorID);

CREATE INDEX IF NOT EXISTS IX_BookCopies_BookID     ON BookCopies (BookID);
CREATE INDEX IF NOT EXISTS IX_BookCopies_CopyStatus ON BookCopies (CopyStatus);

CREATE INDEX IF NOT EXISTS IX_Members_LastName ON Members (LastName);
CREATE INDEX IF NOT EXISTS IX_Members_Email    ON Members (Email);

CREATE INDEX IF NOT EXISTS IX_Memberships_MemberID       ON Memberships (MemberID);
CREATE INDEX IF NOT EXISTS IX_Memberships_ExpirationDate ON Memberships (ExpirationDate);

CREATE INDEX IF NOT EXISTS IX_Loans_MemberID     ON Loans (MemberID);
CREATE INDEX IF NOT EXISTS IX_Loans_CopyID       ON Loans (CopyID);
CREATE INDEX IF NOT EXISTS IX_Loans_DueDate      ON Loans (DueDate);
CREATE INDEX IF NOT EXISTS IX_Loans_ReturnDate   ON Loans (ReturnDate);
CREATE INDEX IF NOT EXISTS IX_Loans_CheckedOutBy ON Loans (CheckedOutBy);
CREATE INDEX IF NOT EXISTS IX_Loans_ReturnedTo   ON Loans (ReturnedTo);

CREATE INDEX IF NOT EXISTS IX_Fines_LoanID        ON Fines (LoanID);
CREATE INDEX IF NOT EXISTS IX_Fines_PaymentStatus ON Fines (PaymentStatus);

CREATE INDEX IF NOT EXISTS IX_Reservations_MemberID          ON Reservations (MemberID);
CREATE INDEX IF NOT EXISTS IX_Reservations_BookID            ON Reservations (BookID);
CREATE INDEX IF NOT EXISTS IX_Reservations_ReservationStatus ON Reservations (ReservationStatus);

-- ---------------------------------------------------------------------------
-- Business rules enforced with partial unique indexes
-- (SQLite's equivalent of SQL Server's filtered indexes)
-- ---------------------------------------------------------------------------

-- A copy can have at most one unreturned loan; returned loans don't count,
-- so the same copy can be borrowed again and again over time.
CREATE UNIQUE INDEX IF NOT EXISTS UX_Loans_OneActivePerCopy
    ON Loans (CopyID) WHERE ReturnDate IS NULL;

-- A member can hold at most one open reservation per title.
CREATE UNIQUE INDEX IF NOT EXISTS UX_Reservations_OneActivePerMemberBook
    ON Reservations (MemberID, BookID)
    WHERE ReservationStatus IN ('Waiting', 'Ready for Pickup');

-- At most one overdue fine per loan, so re-running a fine job can't
-- double-charge. (Increase AmountAssessed on the existing row instead.)
CREATE UNIQUE INDEX IF NOT EXISTS UX_Fines_OneOverduePerLoan
    ON Fines (LoanID) WHERE FineType = 'Overdue';

-- ---------------------------------------------------------------------------
-- Triggers
--
-- A CHECK constraint can't look at another table, so copy availability is
-- enforced with triggers instead.
-- ---------------------------------------------------------------------------

-- Block a new loan for a copy that is On Loan, Lost, Damaged or In Repair.
-- 'Reserved' is allowed: that's the copy being handed to the member who reserved it.
CREATE TRIGGER IF NOT EXISTS TR_Loans_BlockUnavailableCopy
BEFORE INSERT ON Loans
WHEN NEW.ReturnDate IS NULL
 AND (SELECT CopyStatus FROM BookCopies WHERE CopyID = NEW.CopyID)
     IN ('On Loan', 'Lost', 'Damaged', 'In Repair')
BEGIN
    SELECT RAISE(ABORT, 'Copy is not available for loan');
END;

-- Keep BookCopies.CopyStatus in step with loans, so the check above stays accurate.
CREATE TRIGGER IF NOT EXISTS TR_Loans_MarkCopyOnLoan
AFTER INSERT ON Loans
WHEN NEW.ReturnDate IS NULL
BEGIN
    UPDATE BookCopies SET CopyStatus = 'On Loan' WHERE CopyID = NEW.CopyID;
END;

-- On return, put the copy back on the shelf (unless staff already marked it
-- Lost/Damaged/In Repair while it was out).
CREATE TRIGGER IF NOT EXISTS TR_Loans_MarkCopyReturned
AFTER UPDATE OF ReturnDate ON Loans
WHEN OLD.ReturnDate IS NULL AND NEW.ReturnDate IS NOT NULL
BEGIN
    UPDATE BookCopies SET CopyStatus = 'Available'
    WHERE CopyID = NEW.CopyID AND CopyStatus = 'On Loan';
END;

-- A loan marked Lost leaves the copy Lost.
CREATE TRIGGER IF NOT EXISTS TR_Loans_MarkCopyLost
AFTER UPDATE OF LoanStatus ON Loans
WHEN NEW.LoanStatus = 'Lost' AND OLD.LoanStatus <> 'Lost'
BEGIN
    UPDATE BookCopies SET CopyStatus = 'Lost' WHERE CopyID = NEW.CopyID;
END;
