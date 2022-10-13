from arclet.alconna import Alconna, Option, namespace, config, Namespace


def test_config():
    with namespace("cfg1") as np:
        np.separators = {';'}
        cfg = Alconna("cfg") + Option("foo")
        assert cfg.parse("cfg foo").matched is False
        assert cfg.parse("cfg;foo").matched is True
    with namespace("cfg2") as np:
        np.headers = ["!"]
        cfg1 = Alconna("cfg1")
        assert cfg1.parse("cfg1").matched is False
        assert cfg1.parse("!cfg1").matched is True


def test_alconna_config():
    Alconna.config()


def test_namespace():
    config.default_namespace.headers = [...]

    np = Namespace("xxx", headers=[...])
    config.default_namespace = np

    with namespace(config.default_namespace.name) as np:
        np.headers = [...]


if __name__ == '__main__':
    import pytest

    pytest.main([__file__, "-vs"])
