import os
import pathlib

from functools import reduce


import boto3

from jinja2 import Environment, FileSystemLoader, select_autoescape
from xrpl.clients import JsonRpcClient
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.transactions import Payment
from xrpl.wallet import Wallet
from xrpl.transaction import (
    XRPLReliableSubmissionException,
    safe_sign_and_autofill_transaction,
    send_reliable_submission,
)


testnet_client = JsonRpcClient("https://s.altnet.rippletest.net:51234")
dynamodb = boto3.resource("dynamodb")

ISSUERS_TABLE_NAME = os.environ["ISSUERS_TABLE_NAME"]

issuers_table = dynamodb.Table(ISSUERS_TABLE_NAME)

# index_html = pathlib.Path("index.html").read_text()

jinja_env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(),
)

index_template = jinja_env.get_template("index.html")

# Remember this is testnet, these scans include
# the ephemeral secret seed for this round marketplaces are infinite
# this is cached outside the execution, to limit executions
# issuers_table_scan_resp = issuers_table.scan()
# issuers = issuers_table_scan_resp["Items"]
# issuers_map = reduce(lambda a, b: {**a, b["issuer_currency"]: b["seed"]}, issuers, dict())


def handler(event, context):
    print("##EVENT")
    print(event)
    # print("##CONTEXT")
    # print(context)

    path = event["requestContext"]["http"]["path"]
    method = event["requestContext"]["http"]["method"]
    querystring_dict = event.get("queryStringParameters")

    # detect favicon request
    if path == "/favicon.ico":
        return {"statusCode": 404}
    # Remember this is testnet, these scans include
    # the ephemeral secret seed for this round marketplaces are infinite
    issuers_table_scan_resp = issuers_table.scan()
    issuers = issuers_table_scan_resp["Items"]
    issuers_map = reduce(
        lambda a, b: {**a, b["issuer_currency"]: b["seed"]}, issuers, dict()
    )
    print("issuers are", issuers)
    print("issuers_map are", issuers_map)


    if path == "/get-cash" and method == "GET" and querystring_dict is not None:
        for currency, account in querystring_dict.items():
            currency_request_seed = issuers_map[currency]

            issuer_wallet = Wallet(seed=currency_request_seed, sequence=None)
            issued_cash = IssuedCurrencyAmount(
                currency=currency,
                issuer=issuer_wallet.classic_address,
                value="1" + "0" * 6,
            )
            issue_tx_missing = Payment(
                account=issuer_wallet.classic_address,
                # destination=temp_wallet.classic_address,
                destination=account,
                amount=issued_cash,
                # memos=[satirical_branding],
            )
            count = 0
            while count < 5:
                try:
                    issue_tx = safe_sign_and_autofill_transaction(
                        issue_tx_missing,
                        wallet=issuer_wallet,
                        client=testnet_client,
                    )
                    issue_tx_resp = send_reliable_submission(issue_tx, testnet_client)
                    # TODO re-render template with details and txn link
                    print(issue_tx_resp)
                    break
                except XRPLReliableSubmissionException as err:
                    print("err is", err)
                    pass

    index_html = index_template.render(issuers=issuers)
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html"},
        "body": index_html,
    }
