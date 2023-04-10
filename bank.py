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
    def __init__(self, balance: float, type: Literal['checking'], member_id: str, id: int | None = None):
        ...

    @overload
    def __init__(self, balance: float, type: Literal['savings'], member_id: str, id: int | None, r: float):
        ...

    @overload
    def __init__(self, balance: float, type: Literal['cd'], member_id: str, id: int | None, r: float, term: float):
        ...

    def __init__(self, balance, type, member_id, id = None, r = None, term = None):
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

    id_space: list[int] = cursor.execute('SELECT id FROM id_space').fetchall()

    def __init__(self, id: str | None, *args) -> None:
        """Member(id: str | None, [f_name: str], [l_name: str], [pass_hash: Callable[[], bytes]])"""
        self.transactions: list[Transaction] = []
        self.loans: list[Loan] = []
        self.accounts: list[Account] = []
        self.balance: float = 0.00

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
                        account[1], account[2], self.id, account[0], account[4], account[5]))  # type: ignore
                for account in self.accounts:
                    if account.type == 'checking':
                        self.checking = account
                        break

                for loan in Member.cursor.execute('SELECT * from loans WHERE member_id = ?;', (id,)):
                    self.loans.append(Loan(loan[1], loan[2], self.id, loan[0]))
                
                self.transactions.sort(key=lambda v: v.id)
                self.sync_balance()
                Member.members.append(self)
        elif len(args) == 3:
            # New member
            self.f_name: str = args[0]
            self.l_name: str = args[1]
            self.pass_hash: Callable[[], bytes] = lambda: args[2]
            self.credit_score = None
            try:
                self.id: str = str(choice(Member.id_space))
            except IndexError:
                raise IndexError("Ran out of available Member IDs.")
            Member.id_space.remove(int(self.id))

            self.checking = Account(0.0, 'checking', self.id)
            self.accounts.append(self.checking)
        else:
            raise IndexError(
                "Incorrect number of arguments for new member (must be 3).")

        self.save()

    def sync_balance(self):
        for account in self.accounts:
            self.balance = 0.00
            self.balance += account.balance if account.type != "cd" else 0.00

    def create_account(self, starting_amount: float, r: float, term: float | None = None):
        if isinstance(term, float):
            # For CD
            self.accounts.append(
                Account(starting_amount, 'cd', self.id, None, r, term))
        else:
            # For Savings Account
            self.accounts.append(
                Account(starting_amount, 'savings', self.id, None, r))
        self.accounts[-1].id = Member.cursor.execute(
            'SELECT id FROM accounts ORDER BY id DESC LIMIT 1;').fetchone()[0]
        self.save()
        self.sync_balance()

    def charge(self, recipient: Member, amount: float, taxable: bool = True) -> float | None:
        self.transactions.append(Transaction(-amount, self.id, recipient.id))
        recipient.transactions.append(Transaction(amount, self.id, recipient.id))
        # In case you don't have enough money, sends as much as you have.
        amount_sent = self.checking.balance if self.checking.balance - amount < 0 else amount
        self.checking.balance = 0 if self.checking.balance - amount < 0 else self.checking.balance - amount
        
        if taxable:
            sales_tax = SALES_TAX_PERCENT * amount
            recipient.checking.balance += amount_sent - sales_tax
            Member.get_member(
                '0000000000').balance += sales_tax  # type: ignore
        else:
            recipient.checking.balance += amount_sent

        self.sync_balance()
        self.save()
        recipient.sync_balance()
        recipient.save()

        self.transactions[-1].id = Member.cursor.execute(
            'SELECT id FROM transactions ORDER BY id DESC LIMIT 1;').fetchone()[0]
        recipient.transactions[-1].id = Member.cursor.execute(
            'SELECT id FROM transactions ORDER BY id DESC LIMIT 1;').fetchone()[0]

        return self.balance - amount

    def save(self):
        Member.cursor.execute('INSERT OR REPLACE INTO members VALUES (?, ?, ?, ?, ?);', (
            self.id, self.f_name, self.l_name, self.credit_score, self.pass_hash()))

        Member.cursor.executemany('INSERT OR REPLACE INTO transactions (id, amount, payer_id, recipient_id, date) VALUES (?, ?, ?, ?, ?);', [
            tuple(t) for t in self.transactions if t.recipient_id == self.id])

        Member.cursor.executemany('INSERT OR REPLACE INTO accounts (id, balance, type, member_id, r, term) VALUES (?, ?, ?, ?, ?, ?);', [
            tuple(a) for a in self.accounts])

        Member.cursor.executemany('INSERT OR REPLACE INTO loans (id, principal, rate, member_id) VALUES (?, ?, ?, ?);', [
            tuple(l) for l in self.loans])

        Member.db.commit()

    @overload
    def calc_r(self, type: Literal['savings', 'loan']) -> float | None:
        ...

    @overload
    def calc_r(self, type: Literal['cd'], term: float) -> float | None:
        ...

    # type: ignore
    def calc_r(self, type, term = None):
        if self.credit_score is None:
            return
        try:
            if type == 'savings':
                return BASE_RATES['savings'] * self.credit_score/850
            elif type == 'cd':
                return BASE_RATES['cd'][str(term)] * self.credit_score/850
            elif type == 'loan':
                return BASE_RATES['loan']
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
