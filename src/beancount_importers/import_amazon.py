import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

import beangulp
from beancount.core import amount, data, flags
from beancount.core.number import D

from beancount_importers.bank_classifier import payee_to_account_mapping

EXPECTED_HEADER = "order id,order url,items,to,date,total,shipping,shipping_refund,gift,VAT,GST,PST,subscribe & save,refund,payments"


class AmazonImporter(beangulp.Importer):
    def __init__(self, account, currency, importer_params=None):
        self._account = account
        self._currency = currency
        self._params = importer_params or {}

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
        return f"amazon.{filepath.name}"

    def extract(self, filepath: Path, existing: data.Entries) -> data.Entries:
        entries = []
        with open(filepath, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for lineno, row in enumerate(reader, start=2):
                entry = self._make_entry(row, filepath, lineno)
                if entry:
                    entries.append(entry)
        return entries

    def _make_entry(self, row, filepath, lineno):
        order_id = row["order id"].strip()
        items = row["items"].strip().rstrip(";").strip()
        date_str = row["date"].strip()
        total_str = row["total"].strip()
        payments_str = row.get("payments", "").strip()

        if not total_str or not date_str:
            return None

        try:
            txn_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None

        try:
            total_amount = D(total_str)
        except Exception:
            return None

        if total_amount == 0:
            return None

        meta = data.new_metadata(str(filepath), lineno)
        meta["order_id"] = order_id
        order_url = row.get("order url", "").strip()
        if order_url:
            meta["url"] = order_url
        if payments_str:
            meta["payment"] = payments_str

        narration = items[:80] + "..." if len(items) > 80 else items

        postings = [
            data.Posting(
                self._account,
                amount.Amount(-total_amount, self._currency),
                None, None, None, None,
            ),
        ]

        expense_account = payee_to_account_mapping.get("Amazon")
        if expense_account:
            postings.insert(0, data.Posting(
                expense_account,
                amount.Amount(total_amount, self._currency),
                None, None, None, None,
            ))

        return data.Transaction(
            meta=meta,
            date=txn_date,
            flag=flags.FLAG_OKAY,
            payee="Amazon",
            narration=narration,
            tags=data.EMPTY_SET,
            links={f"amazon-{order_id}"},
            postings=postings,
        )


def get_importer(account, currency, importer_params=None):
    return AmazonImporter(account, currency, importer_params=importer_params)


if __name__ == "__main__":
    ingest = beangulp.Ingest([get_importer("Liabilities:Amazon:Orders", "CAD", {})], [])
    ingest()
