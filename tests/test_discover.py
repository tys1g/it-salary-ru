"""Тесты фильтра IT-профессий по slug."""

import pytest

from hhparser.discover import is_it_slug


@pytest.mark.parametrize("slug", [
    "python-razrabotchik", "golang-razrabotchik", "frontend-razrabotchik",
    "devops-inzhener", "ml-inzhener", "data-scientist", "testirovshchik",
    "programmist-1c", "administrator-baz-dannyh-postgresql", "product-manager",
    "qa-inzhener", "analitik-dannyh",
])
def test_it_slugs(slug):
    assert is_it_slug(slug)


@pytest.mark.parametrize("slug", [
    "administrator-produktovogo-magazina",  # раньше ловился через «produkt»
    "prodavec-kassir", "povar", "voditel", "html-verstalshchik-magazina",
    "himik-laborant",  # содержит «ml»-подобные буквы, но не слово ml
])
def test_not_it_slugs(slug):
    assert not is_it_slug(slug)
