import sys
from io import StringIO

from nepattern import AnyString

from arclet.alconna import Alconna, Args, Arparma, CommandMeta, Field, MultiVar, Option

alc = Alconna(
    "exec",
    Args["code", MultiVar(AnyString), Field(completion=lambda: "print(1+1)")] / "\n",
    Option("--pure-text"),
    Option("--no-output"),
    Option("--out", Args["name", str, "res"]),
    meta=CommandMeta("exec python code", example="exec\\nprint(1+1)"),
)

alc.shortcut(
    "echo",
    {"command": "exec --pure-text\nprint(\\'{*}\\')"},
)

alc.shortcut(
    "sin(\d+)",
    {"command": "exec --pure-text\nimport math\nprint(math.sin({0}*math.pi/180))"},
)


def exec_code(result: Arparma):
    if result.find("pure-text"):
        codes = list(result.code)
    else:
        codes = str(result.origin).split("\n")[1:]
    output = result.query[str]("out.name", "res")
    if not codes:
        return ""
    lcs = {}
    _stdout = StringIO()
    _to = sys.stdout
    sys.stdout = _stdout
    try:
        exec(
            "def rc(__out: str):\n    "
            + "    ".join(_code + "\n" for _code in codes)
            + "    return locals().get(__out)",
            {**globals(), **locals()},
            lcs,
        )
        code_res = lcs["rc"](output)
        sys.stdout = _to
        if result.find("no-output"):
            return ""
        if code_res is not None:
            return f"{output}: {code_res}"
        _out = _stdout.getvalue()
        return f"output: {_out}"
    except Exception as e:
        sys.stdout = _to
        return str(e)
    finally:
        sys.stdout = _to

print(exec_code(alc.parse("echo 1234")))
print(exec_code(alc.parse("sin30")))
print(
    exec_code(
        alc.parse(
"""\
exec
print(
    exec_code(
        alc.parse(
            "exec\\n"
            "import sys;print(sys.version)"
        )
    )
)
"""
        )
    )
)
