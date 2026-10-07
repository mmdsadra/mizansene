from mizansene.crawler.search import extract_products, rank_products


def test_extract_products_normalizes_okala_like_payload():
    payload = {
        "data": [
            {"id": 1, "name": "شیر کم چرب", "price": 42000, "imageUrl": "https://x/a.jpg"},
            {"id": 2, "productName": "برنج", "sellingPrice": "900000"},
        ]
    }
    products = extract_products(payload, store_id=12)
    assert [p.name for p in products] == ["شیر کم چرب", "برنج"]
    assert products[0].image_url == "https://x/a.jpg"
    assert products[1].price == 900000


def test_rank_prefers_name_match():
    payload = {"data": [
        {"id": 1, "name": "روغن"},
        {"id": 2, "name": "روغن مایع آفتابگردان"},
        {"id": 3, "name": "برنج"},
    ]}
    products = rank_products(extract_products(payload), "روغن")
    assert products[0].name == "روغن"
    assert "روغن" in products[1].name
