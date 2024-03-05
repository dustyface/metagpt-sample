import asyncio
from metagpt.roles import Role
from metagpt.actions import Action
from metagpt.schema import Message
from metagpt.logs import logger


class Print(Action):
    print_number: int = 0

    def __init__(self, name: str = "", print_number: int = 0, *args, **kwargs):
        super().__init__(name=name, *args, **kwargs)
        self.print_number = print_number
    
    async def run(self, n: int) -> str:
        logger.info(f"Hello, Print Action {n}")

class PrintRole(Role):
    
    def add_batch(self, st: int=0, ed: int=3):
        return [Print(print_number=i) for i in range(st, ed)]
    
    def __init__(self, name: str="", profile: str="PrintRole"):
        super().__init__(name=name, profile=profile)
        self._init_actions(self.add_batch(0, 3))
    
    async def _react(self) -> Message:
        while True:
            await self._think()
            if self.rc.todo is None:
                break
            await self._act()
        return Message(content="Print Done")
    
    async def _think(self):
        if self.rc.todo is None:
           return self._set_state(0)

        if self.rc.state + 1 < len(self.states):
            self._set_state(self.rc.state + 1)
        else:
            self.rc.todo = None

    async def _act(self):
        todo = self.rc.todo
        await todo.run(n=todo.print_number)
        if todo.print_number == 2:
            return self.add_extra_actions()
        return Message(content=f"Print Action {todo.print_number}")

    def add_extra_actions(self):
        logger.info("Add extra actions")
        actions = self.actions
        for m in self.add_batch(3, 6):
            actions.append(m)
        self._init_actions(actions)
        return Message(content="Add extra actions")

async def main():
    role = PrintRole("PrintRole")
    # role.run必须提供message，否则在_observe阶段没有观察到新消息，直接退出;
    result = await role.run("printer start")
    logger.info(result)
    
asyncio.run(main())