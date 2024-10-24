from arclet.alconna import Alconna, ArgsBase, Args, Option


class User(ArgsBase, kw_only=True, seps="&"):
    name: str
    age: int


user_ = Alconna(
    "user",
    Option("list"),
    Option("add", User, separators="?"),
    Option("del", Args.name(str, kw_only=True), separators="?"),
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
        return {"result": "Ok", "msg": "", "data": [u.dump() for u in users.values()]}
    elif user := res.query[dict]("add.args"):
        _user = User(**user)
        users[_user.name] = _user
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
