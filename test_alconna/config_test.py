from arclet.alconna import Alconna, Option, namespace, config, Namespace, command_manager


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
    with namespace("cfg3") as np:
        np.builtin_option_name['help'] = {"帮助"}
        cfg2 = Alconna("cfg2")
        assert cfg2.options[0].name == "帮助"
        print('')
        print('\n', cfg2.parse("cfg2 帮助"))
        print(command_manager.all_command_help())


def test_namespace():
    config.default_namespace.headers = [...]

    np = Namespace("xxx", headers=[...])
    config.default_namespace = np

    with namespace(config.default_namespace.name) as np:
        np.headers = [...]

    config.default_namespace.headers = []


if __name__ == '__main__':
    import pytest

    pytest.main([__file__, "-vs"])
