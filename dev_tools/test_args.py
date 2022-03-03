import time
from typing import Union

from arclet.alconna import Args, AnyFloat
from arclet.alconna.analysis import analyse_args

print("\nArgs KVWord construct:")
arg = Args(pak=str, upgrade=bool).default(upgrade=True)
print("arg:", arg)
print(analyse_args(arg, "arclet-alconna True"))

print("\nArgs Magic construct:")
arg1 = Args["round":AnyFloat, "test":bool:True]["aaa":str] << Args["perm":str:...] + ["month", int]
arg1["foo"] = ["bar", ...]
print("arg1:", arg1)

print("\nArgs Feature: Default value")
arg2 = Args["foo":int, "de":bool:True]
print("arg2:", arg2)
print(analyse_args(arg2, "123 False"))
print(analyse_args(arg2, "123"))

print("\nArgs Feature: Choice")
arg3 = Args["choice":("a", "b", "c")]
print("arg3:", arg3)
print(analyse_args(arg3, "a"))  # OK
time.sleep(0.1)
print(analyse_args(arg3, "d"))  # error

print("\nArgs Feature: Multi")
arg4 = Args["*multi":str]
print("arg4:", arg4)
print(analyse_args(arg4, "a b c d"))


print("\nArgs Feature: Anti")
arg5 = Args["!anti":r"(.+?)/(.+?)\.py"]
print("arg5:", arg5)
print(analyse_args(arg5, "a/b.mp3"))  # OK
time.sleep(0.1)
print(analyse_args(arg5, "a/b.py"))  # error

print("\nArgs Feature: Union")
arg6 = Args["bar":Union[float, int]]
print("arg6:", arg6)
print(analyse_args(arg6, "1.2"))  # OK
time.sleep(0.1)
print(analyse_args(arg6, "1"))  # OK
