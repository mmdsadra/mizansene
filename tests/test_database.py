def test_imports():
    from mizansene.database import ProductStore
    from mizansene.models import Product
    assert ProductStore is not None
    assert Product is not None
