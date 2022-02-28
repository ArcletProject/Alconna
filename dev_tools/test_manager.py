from dev_tools.test_alconna_1 import *
from dev_tools.test_alconna_2 import *

print("\n\n## ------------- Test Manager -------------## \n\n")
print(command_manager.all_command_help(max_length=6, page=3, pages="[%d/%d]"))
print("\n")
print(command_manager.broadcast("cmd.北京天气"))
print(command_manager.require("/pip"))
print(command_manager.command_help("/pip"))