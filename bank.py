from __future__ import annotations
from datetime import datetime
from random import choice
from sqlite3 import connect
from typing import Callable, Literal, overload
from tax import sales_tax_percent

__all__ = ['Member']

now = datetime.utcnow


class Transaction:
    def __init__(self, amount: float, payer: Member, recipient: Member, id: int | None = None, date: datetime = now()):
        self.id = id
        self.amount = amount
        self.payer = payer
        self.recipient = recipient
        self.date = date

    def __iter__(self):
        for x in (self.id, self.amount, self.payer, self.recipient, self.date):
            yield x


class Loan:
    def __init__(self, principal: float, r: float, id: int | None = None):
        self.id = id
        self.principal = principal
        self.r = r

    def pay(self, amount: float):
        interest = amount * self.r
        amount -= interest
        self.r -= interest
        self.principal -= amount

    def __iter__(self):
        for x in (self.id, self.principal, self.r):
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

    def __init__(self, balance: float, type: Literal['savings', 'checking', 'cd'], member_id: str, id: int | None = None, r: float | str = "", term: float | str = ""):
        self.id = id
        self.balance = balance
        self.type = type
        self.member_id = member_id
        self.r = r if r is not None else ""
        self.term = term if term is not None else ""

        if self.type == 'savings' or self.type == 'cd':
            if self.r == "":
                raise TypeError("`r` must be a `float` for savings/cd accounts.")
            if self.type == 'cd':
                if self.term == "":
                    raise TypeError("`term` must be a `float` for savings/cd accounts.")

    def __iter__(self):
        for x in (self.id, self.balance, self.type, self.member_id, self.r, self.term):
            yield x


class Member:
    db = connect('db.sqlite', check_same_thread=False)
    cursor = db.cursor()

    members: list[Member] = []

    id_space = list(range(1000000000, 1000001001))

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
                self.credit_score: int | None = Member.cursor.execute('SELECT credit_score from members WHERE id = ?', (id,)).fetchone()[0]
                for transaction in Member.cursor.execute('SELECT * from transactions WHERE payer_id = ?', (id,)):
                    self.transactions.append(Transaction(
                        transaction[1], -transaction[2], transaction[3], transaction[0], transaction[4]))
                for transaction in Member.cursor.execute('SELECT * from transactions WHERE recipient_id = ?', (id,)):
                    self.transactions.append(Transaction(
                        transaction[1], transaction[2], transaction[3], transaction[0], transaction[4]))
                for account in Member.cursor.execute('SELECT * from accounts WHERE member_id = ?', (id,)):
                    self.accounts.append(Account(account[1], account[2], account[3], account[0], account[4], account[5]))  # type: ignore
                        
                for loan in Member.cursor.execute('SELECT * from loans WHERE member_id = ?', (id,)):
                    self.loans.append(Loan(loan[1], loan[2]))
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

            self.accounts.append(Account(0.0, 'checking', self.id))
        else:
            raise IndexError(
                "Incorrect number of arguments for new member (must be 3).")

        self.save()

    def sync_balance(self):
        for account in self.accounts:
            self.balance = 0.00
            self.balance += account.balance if account.type != "cd" else 0.00

    def create_account(self, *args):
        """create_account(balance: float, member_id: str, r: float, [term: float])
        `term` is for CDs
        """
        if not 3 <= len(args) <= 4:
            raise TypeError
        try:
            # For CD
            self.accounts.append(
                Account(args[0], 'cd', args[1], None, args[2], args[3]))
        except IndexError:
            # For Savings Account
            self.accounts.append(
                Account(args[0], 'savings', args[1], None, args[2]))

    def charge(self, recipient: Member, amount: float, taxable: bool = True) -> float | None:
        self.transactions.append(Transaction(amount, self, recipient))
        recipient.transactions.append(Transaction(amount, self, recipient))
        self.balance -= amount
        if taxable:
            sales_tax = sales_tax_percent * amount
            recipient.balance += amount - sales_tax
            Member.get_member(
                '0000000000').balance += sales_tax  # type: ignore
        else:
            recipient.balance += amount
        self.save()

    def save(self):
        Member.cursor.execute('INSERT OR REPLACE INTO members VALUES (?, ?, ?, ?, ?);', (
            self.id, self.f_name, self.l_name, self.balance, self.pass_hash()))

        Member.cursor.executemany('INSERT OR REPLACE INTO transactions (id, amount, payer_id, recipient_id, date) VALUES (?, ?, ?, ?, ?);', [
            tuple(t) for t in self.transactions if t.payer.id == self.id])

        Member.cursor.executemany('INSERT OR REPLACE INTO accounts (id, balance, type, member_id, r, term) VALUES (?, ?, ?, ?, ?, ?);', [
            tuple(a) for a in self.accounts])

        Member.cursor.executemany('INSERT OR REPLACE INTO loans (id, principal, rate) VALUES (?, ?, ?)', [
            tuple(l) for l in self.loans])

        Member.db.commit()

    @classmethod
    def get_member(cls, id: str):
        for member in cls.members:
            if member.id == id:
                return member

    @classmethod
    def close(cls):
        cls.db.commit()
        cls.cursor.close()
        cls.db.close()
