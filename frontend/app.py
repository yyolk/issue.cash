import os
import pathlib

from functools import reduce
from datetime import datetime

import boto3

from jinja2 import Environment, FileSystemLoader, select_autoescape
from xrpl.clients import JsonRpcClient
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.models.transactions import Payment, Memo
from xrpl.wallet import Wallet
from xrpl.transaction import (
    XRPLReliableSubmissionException,
    safe_sign_and_autofill_transaction,
    send_reliable_submission,
)


testnet_client = JsonRpcClient("https://s.altnet.rippletest.net:51234")
dynamodb = boto3.resource("dynamodb")

ISSUERS_TABLE_NAME = os.environ["ISSUERS_TABLE_NAME"]
# in seconds
CACHE_MAX_AGE = 900

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


def get_issuers():
    issuers_table_scan_resp = issuers_table.scan()
    issuers = issuers_table_scan_resp["Items"]
    issuers_map = reduce(
        lambda a, b: {**a, b["issuer_currency"]: b["seed"]}, issuers, dict()
    )
    print("issuers are", issuers)
    print("issuers_map are", issuers_map)
    return issuers, issuers_map


CACHE_START = datetime.utcnow()
ISSUERS, ISSUERS_MAP = get_issuers()

satirical_branding = Memo(
    memo_data=(
        b"Need cash now (on the testnet)?"
        b" Get cash now (on the testnet)!"
        b" go to: https://issue.cash"
    ).hex()
)


def handler(event, context):
    # debug...
    # print("##EVENT")
    # print(event)
    # print("##CONTEXT")
    # print(context)

    # we utilize the execution container's garbage collection and want to
    # overwrite it when we bust the cache
    global CACHE_START
    global ISSUERS
    global ISSUERS_MAP

    execution_start_time = datetime.utcnow()

    # bust cache?
    if (cached_length := execution_start_time - CACHE_START).seconds > CACHE_MAX_AGE:
        ISSUERS, ISSUERS_MAP = get_issuers()
        CACHE_START = execution_start_time

    path = event["requestContext"]["http"]["path"]
    method = event["requestContext"]["http"]["method"]
    querystring_dict = event.get("queryStringParameters")

    # detect favicon request
    if path == "/favicon.ico":
        return {"statusCode": 404}
    # Remember this is testnet, these scans include
    # the ephemeral secret seed for this round marketplaces are infinite

    if path == "/get-cash" and method == "GET" and querystring_dict is not None:
        for currency, account in querystring_dict.items():
            currency_request_seed = ISSUERS_MAP[currency]

            issuer_wallet = Wallet(seed=currency_request_seed, sequence=None)
            issued_cash = IssuedCurrencyAmount(
                currency=currency,
                issuer=issuer_wallet.classic_address,
                value="1" + "0" * 6,
            )
            issue_tx_missing = Payment(
                account=issuer_wallet.classic_address,
                destination=account,
                amount=issued_cash,
                memos=[
                    satirical_branding,
                ],
            )
            retried_count = 0
            while retried_count < 5:
                try:
                    issue_tx = safe_sign_and_autofill_transaction(
                        issue_tx_missing,
                        wallet=issuer_wallet,
                        client=testnet_client,
                    )
                    issue_tx_resp = send_reliable_submission(issue_tx, testnet_client)

                    # TODO re-render template with details and txn link
                    print(issue_tx_resp)
                    return {
                        "statusCode": 200,
                        "headers": {"Content-Type": "text/plain"},
                        "body": f"Successfully sent $$ to {account}",
                    }
                except XRPLReliableSubmissionException as err:
                    if "tecPATH_DRY" in str(err):
                        return {
                            "statusCode": 400,
                            "headers": {"Content-Type": "text/plain"},
                            "body": """
                            You'll need to set a Trustline first!
                            Go back and use the link under the issuer :)
                            """,
                        }

                    print("err is", err)
                    retried_count += 1
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "text/plain"},
                "body": "Try again in a few moments!",
            }

    if path == "/":
        index_html = index_template.render(
            issuers=ISSUERS,
            cached_length=cached_length.seconds,
            cache_max_age=CACHE_MAX_AGE,
        )
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "text/html"},
            "body": index_html,
        }

    return {"statusCode": 404}
