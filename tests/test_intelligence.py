from mizansene.crawler.intelligence import analyze_recipe, quantity_in_grams


def test_parse_persian_gram_quantity():
    item = analyze_recipe("برنج عنبربو طلایی 8590 گرم")[0]
    assert item.name == "برنج عنبربو طلایی"
    assert item.quantity == 8590
    assert item.unit == "g"
    assert quantity_in_grams(item) == 8590


def test_parse_kilogram_quantity():
    item = analyze_recipe("2 کیلو گوشت")[0]
    assert item.name == "گوشت"
    assert item.unit == "kg"
    assert quantity_in_grams(item) == 2000


def test_unknown_quantity_is_kept():
    item = analyze_recipe("نمک به میزان لازم")[0]
    assert item.name == "نمک به میزان لازم"
    assert item.quantity is None
