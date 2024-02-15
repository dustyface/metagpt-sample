from metagpt.roles import Role
from metagpt.actions import Action
from metagpt.schema import Message
from metagpt.logs import logger
from typing import ClassVar
import asyncio
import re

class SimpleWriteCode(Action):
    PROMPT_TEMPLATE: ClassVar['str'] = """
    Write a python function that can {instruction} and provide 2 runnable test cases.
    Return ```python your_code_here ``` with NO other texts,
    your code: 
    """

    def __init__(self, name = "SimpleWriteCode", context=None, llm=None):
        super().__init__(name=name, context=context, llm=llm)

    async def run(self, instruction):
        prompt = self.PROMPT_TEMPLATE.format(instruction=instruction)
        rsp = await self._aask(prompt)
        code_text = SimpleWriteCode.parse_code(rsp)
        return code_text
    
    @staticmethod
    def parse_code(text):
        pattern = r"```python(.*?)```"
        code = re.search(pattern, text, re.DOTALL)
        code_text = code.group(1) if code else text
        return code_text
    
class SimpleCoder(Role):
    def __init__(self, name="Alice", profile="SimpleCoder", **kwargs):
        super().__init__(name=name, profile=profile, **kwargs)
        self._init_actions([SimpleWriteCode])
        # self._set_react_mode(react_mode="by_order")

    async def _act(self):
        logger.info(f"{self._setting}: prepare to run {self.rc.todo}")
        todo = self.rc.todo
        message = self.get_memories(k=1)[0]
        result = await todo.run(message.content)
        message = Message(content=result, role=self.profile, cause_by=type(todo))
        self.rc.memory.add(message)
        return message

async def main():
    msg = "write a function that calculate the sum of a list"
    logger.info(msg)
    role = SimpleCoder()
    result = await role.run(msg)
    logger.info(f"final result={result}")

asyncio.run(main())