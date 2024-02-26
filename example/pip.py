from pathlib import Path
from typing import Tuple

from nepattern import URL

from arclet.alconna import Alconna, Args, MultiVar, Option, Subcommand, count, store_true

pip = Alconna(
    "/pip",
    Subcommand(
        "install",
        Args["requirements", MultiVar(str, "*")],
        Option("-r|--requirement", Args["rfile", Path]),
        Option("-c|--constraint", Args["cfile", Path]),
        Option("--no-deps", default=False, action=store_true),
        Option("--pre", default=False, action=store_true),
        Option("-e|--editable", Args["path_or_url", [URL, Path]]),
        Option("--dry-run"),
        Option("-t|--target", Args["dir", Path]),
        Option("--platform", Args["plat", str]),
        Option("--python-version", Args["python_version", str]),
        Option("--implementation", Args["impl", ["pp", "jy", "cp", "ip", "py"]]),
        Option("--abi", Args["abi", str]),
        Option("-U|--upgrade", default=False, action=store_true),
        Option("--force-reinstall", default=False, action=store_true),
        Option("-i|--index-url", Args["url", URL])
        # and more ....
    ),
    Subcommand("download"),
    Subcommand("uninstall"),
    Subcommand("freeze"),
    Subcommand("inspect"),
    Subcommand("list"),
    Subcommand("show"),
    Subcommand("check"),
    Subcommand("config"),
    Subcommand("search"),
    Subcommand("cache"),
    Subcommand("wheel"),
    Subcommand("hash"),
    Subcommand("completion"),
    Subcommand("debug"),
    Subcommand("help"),
    Option("--debug", default=False, action=store_true),
    Option("--isolated", default=False, action=store_true),
    Option("--require-virtualenv", default=False, action=store_true),
    Option("--python", Args["python", str]),
    Option("-v|--verbose", action=count, default=0),
    Option("-V|--version"),
    Option("-q|--quiet", default=False, action=store_true),
    Option("--log", Args["log_path", Path]),
    Option("--no-input", default=False, action=store_true),
    Option("--proxy", Args["proxy", str]),
    Option("--retries", Args["count", int]),
    Option("--timeout", Args["sec", float]),
    Option("--exists-action", Args["action", ["s", "i", "w", "b", "a"]]),
    Option("--trusted-host", Args["hostname", str]),
    Option("--cert", Args["cert_path", Path]),
    Option("--client-cert", Args["client_path", Path]),
    Option("--cache-dir", Args["dir", Path]),
    Option("--no-cache-dir", default=False, action=store_true),
    Option("--disable-pip-version-check", default=False, action=store_true),
    Option("no-color", default=False, action=store_true),
    Option("no-python-version-warning", default=False, action=store_true),
    Option("--use-feature", Args["feature", MultiVar(str)]),
    Option("--use-deprecated", Args["feature", MultiVar(str)]),
)

res = pip.parse("/pip install arclet-alconna -U -vvv")
print(res.query[bool]("install.upgrade.value"))
print(res.query[Tuple[str, ...]]("install.args.requirements"))
print(res.query[int]("verbose.value"))
