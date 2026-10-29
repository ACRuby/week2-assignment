"""Fill library.db with sample publishers, staff, members, memberships, copies,
loans, fines and reservations.

    python sample_data.py             # seed 2026
    python sample_data.py --seed 7

Run after schema.sql, seed.sql and load_books.py (it needs the books). People,
addresses, emails (@example.com) and phone numbers (555-01xx) are made up.
Publishers are real companies but aren't linked to any books, since books.csv
doesn't say who published what.

Dates are generated relative to today, going back about 18 months, so a fresh
run always has some loans currently out and some overdue.

Runs once: if the database already has members, staff or loans it changes
nothing, so it can't duplicate or overwrite existing records.
"""

import argparse
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
TODAY = date.today()
HISTORY_START = TODAY - timedelta(days=540)
LOAN_DAYS = 21
MAX_OPEN = 5
FINE_PER_DAY, FINE_CAP = 0.25, 10.00

PUBLISHERS = [
    ('Penguin Random House', 'New York', 'NY', 'United States', 'https://www.penguinrandomhouse.com'),
    ('HarperCollins Publishers', 'New York', 'NY', 'United States', 'https://www.harpercollins.com'),
    ('Simon & Schuster', 'New York', 'NY', 'United States', 'https://www.simonandschuster.com'),
    ('Macmillan Publishers', 'New York', 'NY', 'United States', 'https://us.macmillan.com'),
    ('Hachette Book Group', 'New York', 'NY', 'United States', 'https://www.hachettebookgroup.com'),
    ('Scholastic', 'New York', 'NY', 'United States', 'https://www.scholastic.com'),
    ('Little, Brown and Company', 'New York', 'NY', 'United States', 'https://www.littlebrown.com'),
    ('W. W. Norton & Company', 'New York', 'NY', 'United States', 'https://wwnorton.com'),
    ('Bloomsbury Publishing', 'London', None, 'United Kingdom', 'https://www.bloomsbury.com'),
    ('Oxford University Press', 'Oxford', None, 'United Kingdom', 'https://global.oup.com'),
]

# (first, last, job title, hire date offset in days before today, status)
STAFF = [
    ('Margaret', 'Okafor', 'Library Director', 4200, 'Active'),
    ('Daniel', 'Reyes', 'Circulation Supervisor', 2600, 'Active'),
    ('Priya', 'Natarajan', 'Circulation Clerk', 900, 'Active'),
    ('Tom', 'Becker', 'Circulation Clerk', 400, 'Active'),
    ('Lucy', 'Hammond', "Children's Librarian", 1800, 'Active'),
    ('Victor', 'Salas', 'Reference Librarian', 3000, 'Inactive'),  # left ~a year ago
]
STAFF_LEFT_DAYS_AGO = 365

FIRST_NAMES = ['Olivia', 'Liam', 'Emma', 'Noah', 'Ava', 'Elijah', 'Sophia', 'James', 'Isabella',
               'Lucas', 'Mia', 'Mateo', 'Amelia', 'Ethan', 'Harper', 'Aiden', 'Evelyn', 'Jackson',
               'Aaliyah', 'Wei', 'Fatima', 'Diego', 'Hana', 'Kwame', 'Grace', 'Omar', 'Chloe',
               'Ravi', 'Nora', 'Samuel', 'Zoe', 'Malik', 'Lily', 'Jonah', 'Camila', 'Ines',
               'Arthur', 'Dorothy', 'Harold', 'Beatrice']
LAST_NAMES = ['Smith', 'Johnson', 'Garcia', 'Nguyen', 'Patel', 'Kim', 'Brown', 'Martinez', 'Lopez',
              'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'Lee', 'Harris', 'Clark',
              'Lewis', 'Walker', 'Young', 'Allen', 'Wright', 'Scott', 'Torres', 'Hill', 'Adams',
              'Baker', 'Nelson', 'Carter', 'Mitchell', 'Roberts', 'Chen', 'Okonkwo', 'Haddad']
STREETS = ['Maple Ave', 'Oak St', 'Cedar Ln', 'Elm St', 'Pine Rd', 'Birch Way', 'Willow Dr',
           'Lake Shore Blvd', 'Hillcrest Rd', 'Main St', 'Park Pl', 'River Rd']
CITIES = [('Springfield', 'OH', '45501'), ('Fairview', 'OH', '44126'), ('Riverside', 'OH', '45431'),
          ('Greenville', 'OH', '45331')]

# Membership type -> (weight, annual fee)
MEMBERSHIP_TYPES = {'Adult': (10, 25.00), 'Senior': (4, 10.00), 'Student': (4, 10.00),
                    'Child': (3, 0.00), 'Family': (3, 40.00), 'Free Community Membership': (2, 0.00)}

CONDITIONS = ['New', 'Good', 'Good', 'Good', 'Fair', 'Fair', 'Worn']


def iso(d):
    return d.isoformat() if d else None


def add_year(d):
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # Feb 29
        return d.replace(year=d.year + 1, day=28)


class Generator:
    def __init__(self, con, seed):
        self.con, self.cur = con, con.cursor()
        self.rng = random.Random(seed)
        self.counts = {}

    def insert(self, table, **cols):
        names = ', '.join(cols)
        marks = ', '.join('?' for _ in cols)
        self.cur.execute(f'INSERT INTO {table} ({names}) VALUES ({marks})', tuple(cols.values()))
        self.counts[table] = self.counts.get(table, 0) + 1
        return self.cur.lastrowid

    def rand_date(self, start, end):
        return start + timedelta(days=self.rng.randint(0, max(0, (end - start).days)))

    # -- people --------------------------------------------------------------

    def publishers(self):
        for name, city, state, country, site in PUBLISHERS:
            self.insert('Publishers', PublisherName=name, City=city, State=state,
                        Country=country, Website=site)

    def staff(self):
        self.staff_rows = []  # (StaffID, hired, left)
        for first, last, title, hired_ago, status in STAFF:
            hired = TODAY - timedelta(days=hired_ago)
            sid = self.insert('Staff', FirstName=first, LastName=last, JobTitle=title,
                              Email=f'{first[0].lower()}{last.lower()}@library.example.com',
                              HireDate=iso(hired), StaffStatus=status)
            left = TODAY - timedelta(days=STAFF_LEFT_DAYS_AGO) if status == 'Inactive' else None
            self.staff_rows.append((sid, hired, left))

    def staff_on(self, d):
        """A staff member working on date d, or None (self-service) about 1 time in 8."""
        if self.rng.random() < 0.125:
            return None
        working = [sid for sid, hired, left in self.staff_rows if hired <= d and (left is None or d < left)]
        return self.rng.choice(working) if working else None

    def members(self, n=40):
        # Status mix: mostly Active, plus a few of each other status.
        statuses = ['Active'] * 30 + ['Expired'] * 4 + ['Inactive'] * 3 + ['Suspended'] * 3
        self.rng.shuffle(statuses)
        types = list(MEMBERSHIP_TYPES)
        weights = [MEMBERSHIP_TYPES[t][0] for t in types]
        used_names = set()
        self.member_rows = {}  # MemberID -> dict(registered, periods=[(start, end, status)])
        for status in statuses[:n]:
            while True:
                first, last = self.rng.choice(FIRST_NAMES), self.rng.choice(LAST_NAMES)
                if (first, last) not in used_names:
                    used_names.add((first, last))
                    break
            city, state, postal = self.rng.choice(CITIES)
            registered = self.rand_date(TODAY - timedelta(days=4 * 365), TODAY - timedelta(days=45))
            mtype = self.rng.choices(types, weights)[0]
            mid = self.insert(
                'Members', FirstName=first, LastName=last,
                Email=f'{first.lower()}.{last.lower()}@example.com' if self.rng.random() < 0.9 else None,
                Phone=f'555-01{self.rng.randint(0, 99):02d}',
                StreetAddress=f'{self.rng.randint(10, 9999)} {self.rng.choice(STREETS)}',
                City=city, State=state, PostalCode=postal,
                DateRegistered=iso(registered), MemberStatus=status)
            self.member_rows[mid] = {'registered': registered, 'status': status,
                                     'periods': self.memberships(mid, registered, status, mtype)}

    def memberships(self, mid, registered, member_status, mtype):
        """Back-to-back yearly periods from registration. Active/Suspended members renew
        up to today; Expired/Inactive members stopped renewing at some point."""
        fee = MEMBERSHIP_TYPES[mtype][1]
        periods, start = [], registered
        while True:
            end = add_year(start) - timedelta(days=1)
            if end >= TODAY:
                break
            periods.append([start, end, 'Expired'])
            start = end + timedelta(days=1)
        if member_status in ('Active', 'Suspended'):
            # Renewed through today.
            periods.append([start, end, member_status])
        else:
            # Lapsed: keep only some of the past periods. A member who joined less
            # than a year ago gets one period that ended early.
            if periods:
                periods = periods[:self.rng.randint(1, len(periods))]
            else:
                periods = [[start, self.rand_date(start, TODAY - timedelta(days=1)), 'Expired']]
            if member_status == 'Inactive':
                periods[-1][2] = 'Cancelled'
        for start, end, status in periods:
            self.insert('Memberships', MemberID=mid, MembershipType=mtype, StartDate=iso(start),
                        ExpirationDate=iso(end), MembershipStatus=status, FeePaid=fee,
                        PaymentDate=iso(start))
        return periods

    def members_who_can_borrow(self, d):
        """Members holding a valid (not suspended/cancelled) membership on date d."""
        ok = []
        for mid, m in self.member_rows.items():
            for start, end, status in m['periods']:
                if start <= d <= end and status in ('Active', 'Expired'):
                    ok.append(mid)
                    break
        return ok

    # -- copies and circulation ----------------------------------------------

    def copies(self):
        self.copy_rows = []  # (CopyID, BookID, acquired, cost)
        book_ids = [r[0] for r in self.cur.execute('SELECT BookID FROM Books ORDER BY BookID')]
        barcode = 100000
        for book_id in book_ids:
            for _ in range(self.rng.choices([1, 2, 3], [5, 3, 2])[0]):
                barcode += 1
                acquired = self.rand_date(TODAY - timedelta(days=6 * 365), TODAY - timedelta(days=60))
                cost = round(self.rng.uniform(8, 35), 2)
                cid = self.insert('BookCopies', BookID=book_id, Barcode=f'LIB{barcode}',
                                  AcquisitionDate=iso(acquired), Condition=self.rng.choice(CONDITIONS),
                                  ShelfLocation=f'{self.rng.choice("ABCDEFGH")}-{self.rng.randint(1, 30):02d}',
                                  ReplacementCost=cost)
                self.copy_rows.append((cid, book_id, acquired, cost))

    def loans(self):
        """Walk each copy forward through time, lending it out with gaps in between.
        Loans that would come back after today are left open (still checked out)."""
        self.returned_loans, self.open_loans = [], []
        open_count = {}
        for cid, book_id, acquired, cost in self.copy_rows:
            if self.rng.random() < 0.4:
                continue  # some copies just sit on the shelf
            t = max(acquired, HISTORY_START) + timedelta(days=self.rng.randint(0, 150))
            while t <= TODAY:
                borrowers = self.members_who_can_borrow(t)
                if not borrowers:
                    t += timedelta(days=30)
                    continue
                renewals = self.rng.choices([0, 1, 2], [7, 2, 1])[0]
                due = t + timedelta(days=LOAN_DAYS * (1 + renewals))
                # Most come back on time; some are late.
                if self.rng.random() < 0.75:
                    back = t + timedelta(days=self.rng.randint(3, (due - t).days))
                else:
                    back = due + timedelta(days=self.rng.randint(1, 45))
                status = 'Returned' if back <= TODAY else ('Overdue' if due < TODAY else 'Checked Out')
                returned = back if back <= TODAY else None
                if returned is None:
                    # Nobody keeps more than MAX_OPEN books out at once.
                    borrowers = [m for m in borrowers if open_count.get(m, 0) < MAX_OPEN]
                    if not borrowers:
                        break
                mid = self.rng.choice(borrowers)
                lid = self.insert('Loans', CopyID=cid, MemberID=mid, CheckoutDate=iso(t), DueDate=iso(due),
                                  ReturnDate=iso(returned), RenewalCount=renewals, LoanStatus=status,
                                  CheckedOutBy=self.staff_on(t),
                                  ReturnedTo=self.staff_on(returned) if returned else None)
                loan = (lid, cid, book_id, mid, t, due, returned, cost)
                if returned is None:
                    self.open_loans.append(loan)
                    open_count[mid] = open_count.get(mid, 0) + 1
                    break
                self.returned_loans.append(loan)
                t = returned + timedelta(days=self.rng.randint(10, 200))

    def fines(self):
        # Overdue fines for loans that came back late.
        for lid, cid, book_id, mid, out, due, returned, cost in self.returned_loans:
            late = (returned - due).days
            if late <= 0:
                continue
            amount = min(FINE_CAP, round(late * FINE_PER_DAY, 2))
            self.fine(lid, 'Overdue', returned, amount)

        # A few long-overdue open loans are declared lost: the copy becomes Lost
        # (via trigger) and the member is charged its replacement cost.
        overdue = [l for l in self.open_loans if (TODAY - l[5]).days > 21]
        for lid, cid, book_id, mid, out, due, returned, cost in self.rng.sample(overdue, min(3, len(overdue))):
            self.cur.execute("UPDATE Loans SET LoanStatus = 'Lost' WHERE LoanID = ?", (lid,))
            self.fine(lid, 'Lost Book', due + timedelta(days=21), cost)
            self.open_loans = [l for l in self.open_loans if l[0] != lid]

        # Some copies came back damaged: charge the last borrower, take the copy
        # off the shelf. Only copies with no open loan are eligible.
        open_copies = {l[1] for l in self.open_loans} | {
            r[0] for r in self.cur.execute("SELECT CopyID FROM BookCopies WHERE CopyStatus <> 'Available'")}
        last_loan_per_copy = {}
        for loan in self.returned_loans:
            if loan[1] not in open_copies:
                last_loan_per_copy[loan[1]] = loan
        damaged = self.rng.sample(sorted(last_loan_per_copy.values()), 4)
        for i, (lid, cid, book_id, mid, out, due, returned, cost) in enumerate(damaged):
            new_status = 'Damaged' if i < 2 else 'In Repair'
            self.cur.execute('UPDATE BookCopies SET CopyStatus = ?, Condition = ? WHERE CopyID = ?',
                             (new_status, 'Damaged', cid))
            self.fine(lid, 'Damaged Book', returned, round(cost * 0.5, 2))

        # A one-off charge, e.g. a lost barcode label or replacement case.
        lid, cid, book_id, mid, out, due, returned, cost = self.rng.choice(self.returned_loans)
        self.fine(lid, 'Other', returned, 2.00)

    def fine(self, lid, ftype, fine_date, amount):
        r = self.rng.random()
        if r < 0.55:
            status, paid = 'Paid', amount
        elif r < 0.70 and amount >= 1:
            status, paid = 'Partially Paid', round(amount * self.rng.uniform(0.2, 0.8), 2)
        elif r < 0.88:
            status, paid = 'Unpaid', 0
        else:
            status, paid = 'Waived', 0
        paid_on = None
        if status == 'Paid':
            paid_on = min(TODAY, fine_date + timedelta(days=self.rng.randint(0, 21)))
        self.insert('Fines', LoanID=lid, FineType=ftype, FineDate=iso(fine_date),
                    AmountAssessed=amount, AmountPaid=paid, PaymentStatus=status, PaymentDate=iso(paid_on))

    def reservations(self):
        borrowers_now = [m for m in self.members_who_can_borrow(TODAY)
                         if self.member_rows[m]['status'] == 'Active']
        open_pairs = set()

        def open_reservation(book_id, status, placed, notified=None, expires=None):
            for _ in range(20):
                mid = self.rng.choice(borrowers_now)
                if (mid, book_id) not in open_pairs:
                    open_pairs.add((mid, book_id))
                    return self.insert('Reservations', MemberID=mid, BookID=book_id,
                                       ReservationDate=iso(placed), ExpirationDate=iso(expires),
                                       ReservationStatus=status, NotificationDate=iso(notified))

        # Waiting: titles with every copy currently out.
        statuses = dict(self.cur.execute(
            "SELECT BookID, group_concat(DISTINCT CopyStatus) FROM BookCopies GROUP BY BookID"))
        all_out = [b for b, s in statuses.items() if s == 'On Loan']
        for book_id in self.rng.sample(all_out, min(8, len(all_out))):
            open_reservation(book_id, 'Waiting', TODAY - timedelta(days=self.rng.randint(0, 20)))

        # Ready for Pickup: an available copy is set aside (copy status Reserved)
        # and the member has been notified; they have 7 days to collect it.
        available = list(self.cur.execute(
            "SELECT CopyID, BookID FROM BookCopies WHERE CopyStatus = 'Available'"))
        for cid, book_id in self.rng.sample(available, 4):
            placed = TODAY - timedelta(days=self.rng.randint(3, 15))
            notified = TODAY - timedelta(days=self.rng.randint(0, 2))
            open_reservation(book_id, 'Ready for Pickup', placed, notified, notified + timedelta(days=7))
            self.cur.execute("UPDATE BookCopies SET CopyStatus = 'Reserved' WHERE CopyID = ?", (cid,))

        # History. Fulfilled: the member reserved the title shortly before borrowing it.
        for lid, cid, book_id, mid, out, due, returned, cost in self.rng.sample(self.returned_loans, 10):
            placed = max(self.member_rows[mid]['registered'], out - timedelta(days=self.rng.randint(3, 20)))
            notified = max(placed, out - timedelta(days=self.rng.randint(0, 2)))
            self.insert('Reservations', MemberID=mid, BookID=book_id, ReservationDate=iso(placed),
                        ExpirationDate=iso(notified + timedelta(days=7)),
                        ReservationStatus='Fulfilled', NotificationDate=iso(notified))
        # Cancelled by the member, or Expired after notification without pickup.
        book_ids = [r[0] for r in self.cur.execute('SELECT BookID FROM Books')]
        for status in ['Cancelled'] * 3 + ['Expired'] * 3:
            mid = self.rng.choice(list(self.member_rows))
            placed = self.rand_date(max(self.member_rows[mid]['registered'], HISTORY_START),
                                    TODAY - timedelta(days=30))
            notified = placed + timedelta(days=self.rng.randint(2, 10)) if status == 'Expired' else None
            self.insert('Reservations', MemberID=mid, BookID=self.rng.choice(book_ids),
                        ReservationDate=iso(placed),
                        ExpirationDate=iso((notified or placed) + timedelta(days=7)),
                        ReservationStatus=status, NotificationDate=iso(notified))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--seed', type=int, default=2026)
    parser.add_argument('--db', default=str(HERE / 'library.db'))
    args = parser.parse_args()

    con = sqlite3.connect(args.db)
    con.execute('PRAGMA foreign_keys = ON')
    existing = {t: con.execute(f'SELECT count(*) FROM {t}').fetchone()[0]
                for t in ('Members', 'Staff', 'Loans', 'BookCopies')}
    if any(existing.values()):
        print('Sample data already present, nothing changed:', existing)
        return
    if not con.execute('SELECT count(*) FROM Books').fetchone()[0]:
        print('No books yet; run load_books.py first.')
        return

    g = Generator(con, args.seed)
    with con:  # one transaction: everything loads, or nothing does
        g.publishers()
        g.staff()
        g.members()
        g.copies()
        g.loans()
        g.fines()
        g.reservations()
    con.close()
    print(f'Seed {args.seed}, as of {TODAY}: ' + ', '.join(f'{n} {t}' for t, n in g.counts.items()))


if __name__ == '__main__':
    main()
