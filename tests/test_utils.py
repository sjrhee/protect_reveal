import pytest
from protect_reveal.utils import increment_numeric_string


def test_increment_basic():
    assert increment_numeric_string("000") == "001"
    assert increment_numeric_string("009") == "010"
    assert increment_numeric_string("199") == "200"


def test_increment_raises_on_non_numeric():
    with pytest.raises(ValueError):
        increment_numeric_string("abc123")


def test_increment_preserves_width():
    assert increment_numeric_string("0099") == "0100"
