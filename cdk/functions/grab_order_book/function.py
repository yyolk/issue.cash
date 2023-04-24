from glom import glom, Coalesce, Literal, SKIP
from xrpl.clients import JsonRpcClient
from xrpl.models.currencies import IssuedCurrency, XRP
from xrpl.models.requests.book_offers import BookOffers
from xrpl.wallet import Wallet

MAINNET_BITSTAMP = "rvYAfWj5gh67oV6fW32ZzP3Aw4Eubs59B"
MAINNET_GATEHUB = "rhub8VRN55s94qWKDv6jmDy1pUykJzF3wq"

USD_bitstamp = IssuedCurrency(currency="USD", issuer=MAINNET_BITSTAMP)
EUR_bitstamp = IssuedCurrency(currency="EUR", issuer=MAINNET_BITSTAMP)
JPY_bitstamp = IssuedCurrency(currency="JPY", issuer=MAINNET_BITSTAMP)
USD_gatehub = IssuedCurrency(currency="USD", issuer=MAINNET_GATEHUB)
EUR_gatehub = IssuedCurrency(currency="EUR", issuer=MAINNET_GATEHUB)

gatehub_currency_map = dict(USD=USD_gatehub, EUR=EUR_gatehub, JPY=JPY_bitstamp)
bitstamp_currency_map = dict(USD=USD_bitstamp, EUR=EUR_bitstamp)

testnet_client = JsonRpcClient("https://s.altnet.rippletest.net:51234")
mainnet_client = JsonRpcClient("https://xrplcluster.com")


def get_book_offers(taker_gets, taker_pays):
    book_offers_request = BookOffers(
        taker_gets=taker_gets, taker_pays=taker_pays, limit=500
    )
    book_offers_response = mainnet_client.request(book_offers_request)
    book_offers = book_offers_response.result["offers"]
    return book_offers


glom_spec_xrp_any = {
    "Account": "Account",
    "TakerGetsAmount": "TakerGets",
    "TakerGetsCurrency": Literal("XRP"),
    "TakerPaysAmount": ("TakerPays", "value"),
    "TakerPaysCurrency": ("TakerPays", "currency"),
}

glom_spec_any_xrp = {
    # "TakerGetsValue": "TakerGets",
    # "TakerGets": Literal("XRP"),
    # "TakerPaysValue": ("TakerPays", "value"),
    # "TakerPays": ("TakerPays", "currency"),
    "Account": "Account",
    "TakerPaysAmount": "TakerPays",
    "TakerPaysCurrency": Literal("XRP"),
    "TakerGetsAmount": ("TakerGets", "value"),
    "TakerGetsCurrency": ("TakerGets", "currency"),
}

glom_spec_any_any = {
    "Account": "Account",
    "TakerGetsAmount": ("TakerGets", "value"),
    "TakerGetsCurrency": ("TakerGets", "currency"),
    "TakerPaysAmount": ("TakerPays", "value"),
    "TakerPaysCurrency": ("TakerPays", "currency"),
}


def handler(event, context):

    print("##EVENT##")
    print(event)
    # issuer_currency = "USD"
    # issuer_seed = event["issuers"][issuer_currency]["seed"]
    #
    #
    #     bitstamp_usd__xrp_offers = get_book_offers(XRP(), USD_bitstamp)
    #     bitstamp_xrp__usd_offers = get_book_offers(USD_bitstamp, XRP())
    #     gatehub_usd__xrp_offers = get_book_offers(XRP(), USD_gatehub)
    #     gatehub_xrp__usd_offers = get_book_offers(USD_gatehub, XRP())
    #
    #     minimal_usd_offers = [
    #         offer
    #         for glommed in [
    #             glom(offers, [glom_spec_xrp_any])
    #             for offers in [
    #                 bitstamp_usd__xrp_offers,
    #                 gatehub_usd__xrp_offers,
    #             ]
    #         ]
    #         + [
    #             glom(offers, [Coalesce(glom_spec_any_xrp, SKIP)])
    #             for offers in [
    #                 bitstamp_xrp__usd_offers,
    #                 gatehub_xrp__usd_offers,
    #             ]
    #         ]
    #         for offer in glommed
    #     ]

    all_offers = []
    issuers = event["issuers"]

    # issuer_currency = "USD"
    for issuer_currency, wallet_meta in issuers.items():
        issuer_seed = wallet_meta["seed"]

        any__xrp_offers = []
        xrp__any_offers = []
        bitstamp_any__xrp_offers = []
        bitstamp_xrp__any_offers = []
        gatehub_any__xrp_offers = []
        gatehub_xrp__any_offers = []
        if issuer_currency in bitstamp_currency_map:
            bitstamp_any__xrp_offers = get_book_offers(XRP(), bitstamp_currency_map[issuer_currency])
            # any__xrp_offers += get_book_offers(
            #     XRP(), bitstamp_currency_map[issuer_currency]
            # )
            bitstamp_xrp__any_offers = get_book_offers(bitstamp_currency_map[issuer_currency], XRP())
            # xrp__any_offers += get_book_offers(
            #     XRP(), bitstamp_currency_map[issuer_currency]
            # )

        if issuer_currency in gatehub_currency_map:
            gatehub_any__xrp_offers = get_book_offers(XRP(), gatehub_currency_map[issuer_currency])
            # any__xrp_offers += get_book_offers(
            #     XRP(), gatehub_currency_map[issuer_currency]
            # )
            gatehub_xrp__any_offers = get_book_offers(gatehub_currency_map[issuer_currency], XRP())
            # xrp__any_offers += get_book_offers(
            #     gatehub_currency_map[issuer_currency], XRP()
            # )

        all_offers += [
            offer
            for glommed in [
                glom(offers, [glom_spec_xrp_any])
                # for offers in [any__xrp_offers]
                for offers in [
                    bitstamp_any__xrp_offers,
                    gatehub_any__xrp_offers,
                ]
            ]
            + [
                glom(offers, [Coalesce(glom_spec_any_xrp, SKIP)])
                # for offers in [xrp__any_offers]
                for offers in [
                    bitstamp_xrp__any_offers,
                    gatehub_xrp__any_offers,
                ]
            ]
            for offer in glommed
        ]

    return {
        # "offers": minimal_usd_offers,
        "distinct_accounts": [
            {
                "issuer": {
                    "seed": issuer_seed,
                    "code": issuer_currency,
                },
                "account": account,
                "offers": [
                    {
                        "tgv": inner_offer["TakerGetsAmount"],
                        "tg": inner_offer["TakerGetsCurrency"],
                        "tpv": inner_offer["TakerPaysAmount"],
                        "tp": inner_offer["TakerPaysCurrency"],
                    }
                    for inner_offer in list(
                        # filter(lambda x: x["Account"] == account, minimal_usd_offers)
                        filter(lambda x: x["Account"] == account, all_offers)
                    )
                ],
            }
            # for account in list({offer["Account"] for offer in minimal_usd_offers})
            for account in list({offer["Account"] for offer in all_offers})
        ],
    }
