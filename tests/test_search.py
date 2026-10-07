from mizansene.crawler.search import extract_products, rank_products


def test_extract_products_normalizes_okala_like_payload():
    payload = {
        "data": [
            {"id": 1, "name": "شیر کم چرب", "price": 42000, "imageUrl": "https://x/a.jpg", "isAvailable": True},
            {"id": 2, "productName": "برنج", "sellingPrice": "900000", "isAvailable": False},
        ]
    }
    products = extract_products(payload, store_id=12)
    assert [p.name for p in products] == ["شیر کم چرب"]
    assert products[0].image_url == "https://x/a.jpg"


def test_unrelated_products_are_not_returned():
    payload = {"data": [
        {"id": 1, "name": "روغن"},
        {"id": 2, "name": "روغن مایع آفتابگردان"},
        {"id": 3, "name": "برنج"},
    ]}
    products = rank_products(extract_products(payload), "روغن")
    assert [p.name for p in products] == ["روغن", "روغن مایع آفتابگردان"]


def test_persian_variants_match():
    payload = {"data": [{"id": 1, "name": "کیک یزدی"}]}
    products = rank_products(extract_products(payload), "کیک یزدی")
    assert products[0].name == "کیک یزدی"
