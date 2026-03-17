from beancount.core import data
import beangulp
from beancount_importers.bank_classifier import payee_to_account_mapping
from beangulp.importers import csv

Col = csv.Col

def categorizer(txn, row):
    narration = txn.narration
    posting_account = payee_to_account_mapping.get(narration)
    if posting_account:
        txn.postings.append(
            data.Posting(posting_account, -txn.postings[0].units, None, None, None, None)
        )
    return txn

def get_importer(account, currency):
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
        categorizer=categorizer,
        date_format="%Y-%m-%d",
    )


if __name__ == "__main__":
    ingest = beangulp.Ingest([get_importer("Assets:TD:Chequing", "CAD")], [])
    ingest()

