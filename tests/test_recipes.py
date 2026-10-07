from mizansene.crawler.recipes import ingredients_for


def test_known_recipe():
    assert "عدس" in ingredients_for("عدس پلو")


def test_unknown_recipe_falls_back_to_product_search():
    assert ingredients_for("something unknown") is None
