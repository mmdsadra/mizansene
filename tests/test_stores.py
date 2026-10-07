from mizansene.crawler.stores import extract_stores


def test_extract_stores():
    payload = {"data": [{"storeId": "123", "storeName": "Test Store"}]}
    assert extract_stores(payload) == [(123, "Test Store")]
