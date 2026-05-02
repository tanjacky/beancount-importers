from beancount.core import data
import beangulp
from beancount_importers.bank_classifier import payee_to_account_mapping
from beangulp.importers import csv

Col = csv.Col

def make_categorizer(recurring_accounts):
    recurring_prefixes = tuple(recurring_accounts or [])

    def is_recurring(account):
        return any(
            account == prefix or account.startswith(prefix + ":")
            for prefix in recurring_prefixes
        )

    def categorizer(txn, row):
        narration = txn.narration
        posting_account = payee_to_account_mapping.get(narration)
        if posting_account:
            txn.postings.append(
                data.Posting(posting_account, -txn.postings[0].units, None, None, None, None)
            )
            if is_recurring(posting_account):
                txn = txn._replace(tags=txn.tags | {"recurring"})
        return txn

    return categorizer


def get_importer(account, currency, recurring_accounts=None):
    return csv.CSVImporter(
        {
            Col.DATE: 0,
            Col.NARRATION: 1,
            Col.AMOUNT_DEBIT: 2,
            Col.AMOUNT_CREDIT: 3,
            Col.BALANCE: 4,
        },
        account,
        currency,
        categorizer=make_categorizer(recurring_accounts),
        date_format="%Y-%m-%d",
    )


if __name__ == "__main__":
    ingest = beangulp.Ingest([get_importer("Assets:TD:Chequing", "CAD")], [])
    ingest()

