from mizansene.crawler.search import extract_products, rank_products


def test_extract_products_normalizes_okala_like_payload():
    payload = {
        "data": [
            {
                "id": 1,
                "name": "شیر کم چرب",
                "price": 42000,
                "imageUrl": "https://x/a.jpg",
                "isAvailable": True,
            },
            {
                "id": 2,
                "productName": "برنج",
                "sellingPrice": "900000",
                "isAvailable": False,
            },
        ]
    }
    products = extract_products(payload, store_id=12)
    assert [p.name for p in products] == ["شیر کم چرب"]
    assert products[0].image_url == "https://x/a.jpg"


def test_unrelated_products_are_not_returned():
    payload = {
        "data": [
            {"id": 1, "name": "روغن"},
            {"id": 2, "name": "روغن مایع آفتابگردان"},
            {"id": 3, "name": "برنج"},
        ]
    }
    products = rank_products(extract_products(payload), "روغن")
    assert [p.name for p in products] == ["روغن", "روغن مایع آفتابگردان"]


def test_persian_variants_match():
    payload = {"data": [{"id": 1, "name": "کیک یزدی"}]}
    products = rank_products(extract_products(payload), "کیک یزدی")
    assert products[0].name == "کیک یزدی"


def test_quantity_filtered_payload_can_assume_available():
    payload = {
        "entities": [
            {
                "products": [
                    {"id": 10, "name": "شیر", "price": 50000},
                    {"id": 11, "name": "برنج", "price": 900000},
                ]
            }
        ]
    }
    products = extract_products(
        payload,
        store_id=42,
        available_only=True,
        assume_available=True,
    )
    assert [product.name for product in products] == ["شیر", "برنج"]
    assert all(product.available is True for product in products)


def test_stock_status_is_respected():
    payload = {
        "data": [
            {"id": 1, "name": "شیر", "stockQuantity": 4},
            {"id": 2, "name": "برنج", "stockQuantity": 0},
            {"id": 3, "name": "روغن", "stockStatus": "OUT_OF_STOCK"},
        ]
    }
    products = extract_products(payload)
    assert [product.name for product in products] == ["شیر"]
