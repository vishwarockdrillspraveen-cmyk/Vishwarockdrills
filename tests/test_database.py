from database import get_companies, initialize_database


def test_get_companies_excludes_demo_legacy_names():
    initialize_database()
    names = [name.lower().strip() for _, name in get_companies()]
    assert "demo company" not in names
    assert "abc" not in names
