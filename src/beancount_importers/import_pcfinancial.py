import csv as csvlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import beangulp
from beancount.core import amount, data, flags
from beancount.core.number import D

from beancount_importers.bank_classifier import payee_to_account_mapping

EXPECTED_HEADER = '"Description","Type","Card Holder Name","Date","Time","Amount"'


def _parse_amount(s):
    s = (s or "").strip()
    if not s:
        return None
    sign = -1 if s.startswith("-") else 1
    cleaned = s.lstrip("-").lstrip("$").replace(",", "")
    try:
        return D(cleaned) * sign
    except Exception:
        return None


class PCFinancialImporter(beangulp.Importer):
    def __init__(self, account, currency, card_holder, recurring_accounts=None):
        self._account = account
        self._currency = currency
        self._card_holder = card_holder.upper()
        self._recurring_prefixes = tuple(recurring_accounts or [])

    def identify(self, filepath: Path) -> bool:
        try:
            with open(filepath, encoding="utf-8-sig") as f:
                header = f.readline().strip()
                if header != EXPECTED_HEADER:
                    return False
                reader = csvlib.DictReader(f, fieldnames=[
                    "Description", "Type", "Card Holder Name", "Date", "Time", "Amount"
                ])
                for row in reader:
                    if row.get("Card Holder Name", "").strip().upper() == self._card_holder:
                        return True
        except Exception:
            pass
        return False

    def account(self, filepath: Path) -> str:
        return self._account

    def filename(self, filepath: Path) -> Optional[str]:
        return f"pcfinancial.{filepath.name}"

    def extract(self, filepath: Path, existing: data.Entries) -> data.Entries:
        entries = []
        with open(filepath, encoding="utf-8-sig") as f:
            reader = csvlib.DictReader(f)
            for lineno, row in enumerate(reader, start=2):
                if row.get("Card Holder Name", "").strip().upper() != self._card_holder:
                    continue
                entry = self._make_entry(row, filepath, lineno)
                if entry:
                    entries.append(entry)
        return entries

    def _is_recurring(self, acct):
        return any(
            acct == p or acct.startswith(p + ":")
            for p in self._recurring_prefixes
        )

    def _make_entry(self, row, filepath, lineno):
        txn_type = row.get("Type", "").strip()
        if txn_type not in ("PURCHASE", "PAYMENT"):
            return None

        date_str = row.get("Date", "").strip()
        amt = _parse_amount(row.get("Amount", ""))
        if not date_str or amt is None or amt == 0:
            return None
        try:
            txn_date = datetime.strptime(date_str, "%m/%d/%Y").date()
        except ValueError:
            return None

        description = row.get("Description", "").strip()
        meta = data.new_metadata(str(filepath), lineno)

        # Purchases: amt is negative (CSV convention); payments: positive.
        # Post amt directly so liability balance moves in the correct direction.
        postings = [
            data.Posting(
                self._account,
                amount.Amount(amt, self._currency),
                None, None, None, None,
            ),
        ]
        tags = data.EMPTY_SET

        if txn_type == "PURCHASE":
            expense_account = payee_to_account_mapping.get(description)
            if expense_account:
                postings.append(data.Posting(
                    expense_account,
                    amount.Amount(-amt, self._currency),
                    None, None, None, None,
                ))
                if self._is_recurring(expense_account):
                    tags = frozenset({"recurring"})

        return data.Transaction(
            meta=meta,
            date=txn_date,
            flag=flags.FLAG_OKAY,
            payee=description or None,
            narration=description,
            tags=tags,
            links=data.EMPTY_SET,
            postings=postings,
        )


def get_importer(account, currency, card_holder, recurring_accounts=None):
    return PCFinancialImporter(
        account, currency, card_holder, recurring_accounts=recurring_accounts
    )


if __name__ == "__main__":
    ingest = beangulp.Ingest(
        [get_importer("Liabilities:CreditCard:PC", "CAD", card_holder="JACKY")], []
    )
    ingest()
