"""Pure inventory-rendering checks; these are not container security evidence."""

import pytest
from container_audit_support import inventory_requirements


def test_inventory_is_pinned_sorted_and_excludes_only_our_project() -> None:
    assert (
        inventory_requirements(
            [
                {"name": "zipp", "version": "4.1.0"},
                {"name": "predictive-maintenance-mlops", "version": "0.1.0"},
                {"name": "aiohttp", "version": "3.14.5"},
            ]
        )
        == "aiohttp==3.14.5\nzipp==4.1.0\n"
    )


@pytest.mark.parametrize(
    "packages",
    [
        [],
        [{"name": "bad\nname", "version": "1"}],
        [{"name": "safe", "version": "1\n--ignore-vuln=all"}],
    ],
)
def test_inventory_rejects_empty_or_unbounded_entries(
    packages: list[dict[str, str]],
) -> None:
    with pytest.raises(ValueError):
        inventory_requirements(packages)
