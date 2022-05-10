from arclet.alconna import Alconna, Args, Option, Subcommand
from arclet.alconna.components.visitor import AlconnaNodeVisitor
from arclet.alconna.builtin.formatter import DefaultTextFormatter, ArgParserTextFormatter


alc = Alconna("test_line", main_args="line:'...'")
print(alc.parse("test_line\nfoo\nbar\n"))
b = AlconnaNodeVisitor(
    Alconna(
        command="test",
        help_text="test_help",
        options=[
            Option("test", Args.foo[str], help_text="test_option"),
            Subcommand(
                "sub",
                options=[
                    Option("suboption", Args.foo[str], help_text="sub_option"),
                    Option("suboption2", Args.foo[str], help_text="sub_option2"),
                ]
            )
        ]
    )
)
print(b.format_node(DefaultTextFormatter(), b.require([])))
print(b.format_node(ArgParserTextFormatter(), b.require([])))
