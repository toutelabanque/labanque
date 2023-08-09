from __future__ import annotations
from datetime import datetime
from random import choice
from sqlite3 import connect
from typing import Callable, Literal, overload
from consts import SALES_TAX_PERCENT, BASE_RATES

__all__ = ['Member']

now = datetime.utcnow


class Transaction:
    def __init__(self, amount: float, payer_id: str, recipient_id: str, id: int | None = None, date: datetime = now()):
        self.id = id
        self.amount = amount
        self.payer_id = payer_id
        self.recipient_id = recipient_id
        self.date = date

    def __iter__(self):
        for x in (self.id, self.amount, self.payer_id, self.recipient_id, self.date):
            yield x


class Loan:
    def __init__(self, principal: float, r: float, member_id: str, id: int | None = None):
        self.id = id
        self.principal = principal
        self.r = r
        self.member_id = member_id

    def pay(self, amount: float):
        interest = amount * self.r
        amount -= interest
        self.r -= interest
        self.principal -= amount

    def __iter__(self):
        for x in (self.id, self.principal, self.r, self.member_id):
            yield x


class Account:

    @overload
    def __init__(self, balance: int, type: Literal['checking'], member_id: str, id: int | None = None):
        ...

    @overload
    def __init__(self, balance: int, type: Literal['savings'], member_id: str, id: int | None, r: float):
        ...

    @overload
    def __init__(self, balance: int, type: Literal['cd'], member_id: str, id: int | None, r: float, term: float):
        ...

    def __init__(self, balance, type, member_id, id=None, r=None, term=None):
        self.id = id
        self.balance = balance
        self.type = type
        self.member_id = member_id
        self.r = r
        self.term = term

        if self.type == 'savings' or self.type == 'cd':
            if self.r == "":
                raise TypeError(
                    "`r` must be a `float` for savings/cd accounts.")
            if self.type == 'cd':
                if self.term == "":
                    raise TypeError(
                        "`term` must be a `float` for savings/cd accounts.")

    def __iter__(self):
        for x in (self.id, self.balance, self.type, self.member_id, self.r, self.term):
            yield x


class Member:
    db = connect('db.sqlite', check_same_thread=False)
    cursor = db.cursor()

    members: list[Member] = []

    id_space: list[tuple[int]] = cursor.execute('SELECT id FROM id_space').fetchall()

    def __init__(self, id: str | None, *args) -> None:
        """Member(id: str | None, [f_name: str], [l_name: str], [pass_hash: Callable[[], bytes]])"""
        self.transactions: list[Transaction] = []
        self.loans: list[Loan] = []
        self.accounts: list[Account] = []
        self.balance: int = 0

        if len(args) == 0:
            # Existing member
            if id is None:
                raise ValueError
            else:
                self.id: str = id
                self.f_name: str = Member.cursor.execute(
                    'SELECT f_name FROM members WHERE id = ?;', (id,)).fetchone()[0]
                self.l_name: str = Member.cursor.execute(
                    'SELECT l_name FROM members WHERE id = ?;', (id,)).fetchone()[0]
                self.pass_hash: Callable[[], bytes] = lambda: Member.cursor.execute(
                    'SELECT pass_hash FROM members WHERE id = ?;', (id,)).fetchone()[0]
                self.pin_hash: Callable[[], bytes | None] = lambda: Member.cursor.execute(
                    'SELECT pin_hash FROM members WHERE id = ?;', (id,)).fetchone()[0]
                self.credit_score: int | None = Member.cursor.execute(
                    'SELECT credit_score from members WHERE id = ?', (id,)).fetchone()[0]

                for transaction in Member.cursor.execute('SELECT * from transactions WHERE payer_id = ?;', (id,)):
                    self.transactions.append(Transaction(
                        -transaction[1], self.id, transaction[3], transaction[0], transaction[4]))
                for transaction in Member.cursor.execute('SELECT * from transactions WHERE recipient_id = ?;', (id,)):
                    self.transactions.append(Transaction(
                        transaction[1], transaction[2], self.id, transaction[0], transaction[4]))

                for account in Member.cursor.execute('SELECT * from accounts WHERE member_id = ?;', (id,)):
                    self.accounts.append(Account(
                        account[1], account[2], self.id, account[0], account[4], account[5]))

                # First Checking Account is main checking account used for DTs, etc.
                self.accounts.sort(key=lambda a: a.id)
                for account in self.accounts:
                    if account.type == 'checking':
                        self.checking = account
                        break

                for loan in Member.cursor.execute('SELECT * from loans WHERE member_id = ?;', (id,)):
                    self.loans.append(Loan(loan[1], loan[2], self.id, loan[0]))

                self.transactions.sort(key=lambda t: t.id)
                self.sync_balance()
                Member.members.append(self)
        elif len(args) == 3:
            # New member
            self.f_name: str = args[0]
            self.l_name: str = args[1]
            self.pass_hash: Callable[[], bytes] = lambda: args[2]
            self.pin_hash = lambda: None
            self.credit_score = None
            try:
                self.id: str = str(choice(Member.id_space)[0])
            except IndexError:
                raise IndexError("Ran out of available Member IDs.")
            Member.id_space.remove((int(self.id),))
            Member.cursor.execute('DELETE FROM id_space;')
            Member.cursor.executemany('INSERT INTO id_space VALUES (?);', Member.id_space)

            # Make main Checking Account to be used for DTs, etc. Starts with $1,000.
            self.checking = Account(100000, 'checking', self.id)
            self.accounts.append(self.checking)
        else:
            raise IndexError(
                "Incorrect number of arguments for new member (must be 3).")

        self.save()

    def sync_balance(self):
        self.balance = 0
        for account in self.accounts:
            self.balance += account.balance if account.type != "cd" else 0

    def create_account(self, starting_amount: float, r: float | None = None, term: float | None = None):
        if self.checking.balance >= starting_amount:
            self.checking.balance -= starting_amount
        else:
            raise ValueError
        if isinstance(r, float) and isinstance(term, float):
            # For CD
            self.accounts.append(
                Account(starting_amount, 'cd', self.id, None, r, term))
        elif isinstance(r, float):
            # For Savings Account
            self.accounts.append(
                Account(starting_amount, 'savings', self.id, None, r))
        elif r is None and term is None:
            # For Checking Account
            self.accounts.append(
                Account(starting_amount, 'checking', self.id)
            )
        self.save()
        self.accounts[-1].id = Member.cursor.execute(
            'SELECT id FROM accounts ORDER BY id DESC LIMIT 1;').fetchone()[0]
        self.sync_balance()
        return self.accounts[-1].id

    def charge(self, recipient: Member, amount: float, taxable: bool = True) -> tuple[float, float, float]:
        if taxable:
            sales_tax = SALES_TAX_PERCENT * amount
            Member.get_member(
                '0000000000').checking.balance += sales_tax
        else:
            sales_tax = 0.0


        if self.checking.balance >= amount + sales_tax:
            self.checking.balance -= amount + sales_tax
            recipient.checking.balance += amount - sales_tax
        # In case you don't have enough money, bounce.
        else:
            return (amount, self.checking.balance - amount, sales_tax)

        self.transactions.append(Transaction(-amount-sales_tax, self.id, recipient.id))
        recipient.transactions.append(
            Transaction(amount, self.id, recipient.id))

        self.sync_balance()
        self.save()
        recipient.sync_balance()
        recipient.save()

        self.transactions[-1].id = Member.cursor.execute(
            'SELECT id FROM transactions ORDER BY id DESC LIMIT 1;').fetchone()[0]
        recipient.transactions[-1].id = Member.cursor.execute(
            'SELECT id FROM transactions ORDER BY id DESC LIMIT 1;').fetchone()[0]

        return (amount, self.balance, sales_tax)

    def save(self):
        Member.cursor.execute('INSERT OR REPLACE INTO members VALUES (?, ?, ?, ?, ?, ?);', (
            self.id, self.f_name, self.l_name, self.credit_score, self.pass_hash(), self.pin_hash()))

        Member.cursor.executemany('INSERT OR REPLACE INTO transactions (id, amount, payer_id, recipient_id, date) VALUES (?, ?, ?, ?, ?);', [
            tuple(t) for t in self.transactions if t.recipient_id == self.id])

        # Since they can be deleted
        Member.cursor.execute('DELETE FROM accounts WHERE member_id = ?', (self.id,))
        Member.cursor.executemany('INSERT INTO accounts (id, balance, type, member_id, r, term) VALUES (?, ?, ?, ?, ?, ?);', [
            tuple(a) for a in self.accounts])

        Member.cursor.execute('DELETE FROM loans WHERE member_id = ?', (self.id,))
        Member.cursor.executemany('INSERT INTO loans (id, principal, rate, member_id) VALUES (?, ?, ?, ?);', [
            tuple(l) for l in self.loans])

        Member.db.commit()

    @overload
    def calc_r(self, type: Literal['savings', 'loan']) -> float | None:
        ...

    @overload
    def calc_r(self, type: Literal['cd'], term: float) -> float | None:
        ...

    def calc_r(self, type, term=None):
        if self.credit_score is None:
            return
        try:
            if type == 'savings':
                return BASE_RATES['savings']/100 * self.credit_score/850
            elif type == 'cd':
                return BASE_RATES['cd'][str(term)]/100 * self.credit_score/850
            elif type == 'loan':
                return BASE_RATES['loan']/100
            else:
                raise ValueError
        except KeyError:
            raise TypeError

    @classmethod
    def get_member(cls, id: str):
        for member in cls.members:
            if member.id == id:
                return member

    @classmethod
    def close(cls):
        for member in cls.members:
            member.save()
        cls.db.commit()
        cls.cursor.close()
        cls.db.close()
