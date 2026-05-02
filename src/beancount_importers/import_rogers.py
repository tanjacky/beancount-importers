import csv as csvlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import beangulp
from beancount.core import amount, data, flags
from beancount.core.number import D

from beancount_importers.bank_classifier import payee_to_account_mapping

EXPECTED_HEADER = (
    "Date,Posted Date,Reference Number,Activity Type,Activity Status,Card Number,"
    "Merchant Category Description,Merchant Name,Merchant City,Merchant State or Province,"
    "Merchant Country Code,Merchant Postal Code,Amount,Rewards,Name on Card"
)


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


class RogersImporter(beangulp.Importer):
    def __init__(self, account, currency, recurring_accounts=None):
        self._account = account
        self._currency = currency
        self._recurring_prefixes = tuple(recurring_accounts or [])

    def identify(self, filepath: Path) -> bool:
        try:
            with open(filepath, encoding="utf-8-sig") as f:
                header = f.readline().strip()
            return header == EXPECTED_HEADER
        except Exception:
            return False

    def account(self, filepath: Path) -> str:
        return self._account

    def filename(self, filepath: Path) -> Optional[str]:
        return f"rogers.{filepath.name}"

    def extract(self, filepath: Path, existing: data.Entries) -> data.Entries:
        entries = []
        with open(filepath, encoding="utf-8-sig") as f:
            reader = csvlib.DictReader(f)
            for lineno, row in enumerate(reader, start=2):
                entry = self._make_entry(row, filepath, lineno)
                if entry:
                    entries.append(entry)
        return entries

    def _is_recurring(self, account):
        return any(
            account == p or account.startswith(p + ":")
            for p in self._recurring_prefixes
        )

    def _make_entry(self, row, filepath, lineno):
        if row.get("Activity Status", "").strip() != "APPROVED":
            return None
        if row.get("Activity Type", "").strip() != "TRANS":
            return None

        date_str = row.get("Date", "").strip()
        amt = _parse_amount(row.get("Amount", ""))
        if not date_str or amt is None or amt == 0:
            return None
        try:
            txn_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None

        merchant = row.get("Merchant Name", "").strip()
        category = row.get("Merchant Category Description", "").strip()
        ref = row.get("Reference Number", "").strip()

        meta = data.new_metadata(str(filepath), lineno)
        if category:
            meta["category"] = category
        if ref:
            meta["ref"] = ref

        postings = [
            data.Posting(
                self._account,
                amount.Amount(-amt, self._currency),
                None, None, None, None,
            ),
        ]
        tags = data.EMPTY_SET

        if amt > 0:
            expense_account = payee_to_account_mapping.get(merchant)
            if expense_account:
                postings.append(data.Posting(
                    expense_account,
                    amount.Amount(amt, self._currency),
                    None, None, None, None,
                ))
                if self._is_recurring(expense_account):
                    tags = frozenset({"recurring"})

        return data.Transaction(
            meta=meta,
            date=txn_date,
            flag=flags.FLAG_OKAY,
            payee=merchant or None,
            narration=merchant,
            tags=tags,
            links=data.EMPTY_SET,
            postings=postings,
        )


def get_importer(account, currency, recurring_accounts=None):
    return RogersImporter(account, currency, recurring_accounts=recurring_accounts)


if __name__ == "__main__":
    ingest = beangulp.Ingest(
        [get_importer("Liabilities:CreditCard:Rogers", "CAD")], []
    )
    ingest()
