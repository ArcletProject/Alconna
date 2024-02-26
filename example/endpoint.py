from dataclasses import asdict, dataclass

from arclet.alconna import Alconna, Args, KeyWordVar, Option, UnpackVar


@dataclass
class User:
    name: str
    age: int

user_ = Alconna(
    "user",
    Option("list"),
    Option("add", Args["user", UnpackVar(User, kw_only=True)].separate("&"), separators="?"),
    Option("del", Args["name", KeyWordVar(str)], separators="?"),
    separators="/"
)

sends = [
    "user/add?name=abcd&age=16",
    "user/add?name=efgh&age=20",
    "user/list",
    "user/add?name=rtew&age=aa",
    "user/del?name=abcd"
]

users = {}

def handle(send: str):
    res = user_.parse(send)
    if not res.matched:
        return {"result": "Err", "msg": res.error_info}
    if res.find("list"):
        return {"result": "Ok", "msg": "", "data": [asdict(u) for u in users.values()]}
    elif user := res.query[User]("add.user"):
        users[user.name] = user
        return {"result": "Ok", "msg": ""}
    elif name := res.query[str]("del.name"):
        if name not in users:
            return {"result": "Err", "msg": "Unknown target"}
        del users[name]
        return {"result": "Ok", "msg": ""}
    else:
        return {"result": "Err", "msg": "Unknown API"}

for s in sends:
    print(handle(s))
