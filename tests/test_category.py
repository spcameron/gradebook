# tests/test_category.py

from models.category import Category


def test_unweighted_category_to_dict(sample_unweighted_category):
    data = sample_unweighted_category.to_dict()

    assert data["id"] == "c001"
    assert data["name"] == "test_category"
    assert data["weight"] == None
    assert data["active"] == True


def test_weighted_category_to_dict(sample_weighted_category):
    data = sample_weighted_category.to_dict()

    assert data["id"] == "c002"
    assert data["name"] == "test_category"
    assert data["weight"] == 100.0
    assert data["active"] == True


def test_unweighted_category_from_dict():
    category = Category.from_dict(
        {
            "id": "c001",
            "name": "test_category",
            "weight": None,
            "active": True,
        }
    )

    assert category.id == "c001"
    assert category.name == "test_category"
    assert category.weight is None


def test_weighted_category_from_dict():
    category = Category.from_dict(
        {
            "id": "c002",
            "name": "test_category",
            "weight": 100.0,
            "active": True,
        }
    )

    assert category.id == "c002"
    assert category.name == "test_category"
    assert category.weight == 100.0


def test_category_to_str(sample_unweighted_category, sample_weighted_category):
    assert (
        sample_unweighted_category.__str__()
        == "CATEGORY: name: test_category, weight: None, id: c001"
    )
    assert (
        sample_weighted_category.__str__()
        == "CATEGORY: name: test_category, weight: 100.0, id: c002"
    )


def test_archive_and_reactivate(sample_unweighted_category):
    category = sample_unweighted_category
    assert not category.is_archived
    assert "ARCHIVED" not in category.name
    assert category.status == "'ACTIVE'"

    category.toggle_archived_status()
    assert category.is_archived
    assert "ARCHIVED" in category.name
    assert category.status == "'ARCHIVED'"
