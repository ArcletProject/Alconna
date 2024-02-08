from arclet.alconna import Alconna, Namespace, Option, command_manager, config, namespace


def test_config():
    with namespace("cfg1") as np:
        np.separators = (";",)
        cfg = Alconna("cfg") + Option("foo")
        assert cfg.parse("cfg foo").matched is False
        assert cfg.parse("cfg;foo").matched is True
    with namespace("cfg2") as np:
        np.prefixes = ["!"]
        cfg1 = Alconna("cfg1")
        assert cfg1.parse("cfg1").matched is False
        assert cfg1.parse("!cfg1").matched is True
    with namespace("cfg3") as np:
        np.builtin_option_name["help"] = {"帮助"}
        cfg2 = Alconna("cfg2")
        assert cfg2.options[0].name == "帮助"
        print("")
        print("\n", cfg2.parse("cfg2 帮助"))
        print(command_manager.all_command_help())


def test_namespace():
    np = Namespace("xxx", prefixes=[...])
    config.default_namespace = np

    assert config.default_namespace == np
    assert config.default_namespace.prefixes == [...]

    cfg3 = Alconna("cfg3")
    assert cfg3.parse("cfg3").matched is False
    assert cfg3.parse([..., "cfg3"]).matched is True

    config.default_namespace = "Alconna"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-vs"])
