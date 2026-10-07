from mizansene.crawler.stores import extract_stores


def test_extract_stores_requires_store_specific_ids():
    payload = {
        "data": [
            {"id": 999, "name": "Not a store"},
            {"storeId": 12, "storeName": "Store B", "distance": 4.2},
            {"storeId": 7, "storeName": "Store A", "distance": 1.1},
        ]
    }
    assert extract_stores(payload) == [(7, "Store A"), (12, "Store B")]
