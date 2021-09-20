"""Test cases for the qbox module."""
from qbox import QBox


class TestQBox:
    """Tests for the QBox container."""

    def test_repr(self) -> None:
        """Test repr syntax."""
        qbox = QBox()
        assert repr(qbox).startswith("<qbox.qbox.QBox object at")
