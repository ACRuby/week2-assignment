-- Sample data for library.db. Run after schema.sql:
--
--   sqlite3 library.db < seed.sql
--
-- INSERT OR IGNORE skips rows that already exist (matched on the UNIQUE
-- CategoryName), so re-running this never duplicates or overwrites data.
PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO Categories (CategoryName, Description) VALUES
    ('Fiction',               'Imaginative narrative prose'),
    ('Fantasy',               'Fiction featuring magic or supernatural worlds'),
    ('Science Fiction',       'Fiction based on imagined science or technology'),
    ('Mystery',               'Crime, detective, and suspense stories'),
    ('Biography',             'Accounts of real people''s lives'),
    ('History',               'Accounts and analysis of past events'),
    ('Nonfiction',            'Factual works not covered by a more specific category'),
    ('Romance',               'Stories centered on romantic relationships'),
    ('Children''s Literature', 'Books written for young readers'),
    ('Technology',            'Computing, engineering, and applied science');
