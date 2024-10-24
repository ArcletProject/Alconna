from __future__ import annotations

from sqlite3 import connect
from typing import Optional

from arclet.alconna import Alconna, Args, Option

db = connect('example.db')

cursor = db.cursor()


select = Alconna(
    "SELECT",
    Args.columns(str, multiple=True),
    Option("FROM", Args.table(str, "UNKNOWN")),
    Option("WHERE", Args.conditions(str, multiple=True, kw_only=True)),
)


@select.bind()
def exec_sql(columns: tuple[str, ...], table: str, conditions: Optional[dict[str, str]] = None):
    if table == "UNKNOWN":
        print("Table name is required.")
        return
    if conditions is None:
        conditions = {}
    cursor.execute(f"SELECT {', '.join(columns)} FROM {table} WHERE {' AND '.join(f'{k}={v}' for k, v in conditions.items())}")
    print(cursor.fetchall())


select.parse("SELECT health name FROM entertainment.pets WHERE USERID=MYID()")