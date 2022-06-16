from arclet.alconna.config import config
from arclet.alconna import Alconna, Args, Option


def test_config():
    config.separators = {";"}
    cfg = Alconna("cfg") + Option("foo")
    assert cfg.parse("cfg foo").matched is False
    assert cfg.parse("cfg;foo").matched is True
    config.separators = {' '}


def test_alconna_config():
    Alconna.config(headers=["!"])
    cfg1 = Alconna("cfg1")
    assert cfg1.parse("cfg1").matched is False
    assert cfg1.parse("!cfg1").matched is True
    Alconna.config(headers=[''])


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, "-vs"])
