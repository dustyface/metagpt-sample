from metagpt.roles import Role
from metagpt.actions import Action
from metagpt.schema import Message
from metagpt.logs import logger
from typing import ClassVar
import re
import subprocess
import asyncio


class SimpleWriteCode(Action):
    PROMPT_TEMPLATE: ClassVar['str'] = """
    Write a python function that can {instruction} and provide 2 runnable test cases.
    Return ```python your_code_here ``` with NO other texts,
    your code: 
    """

    def __init__(self, name = "SimpleWriteCode", context=None, llm=None):
        super().__init__(name=name, context=context, llm=llm)

    # 被role的_act()方法调用
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

class SimpleRunCode(Action):
    def __init__(self, name = "SimpleRunCode", context=None, llm=None):
        super().__init__(name=name, context=context, llm=llm)

    async def run(self, code):
        result = subprocess.run(['python', '-c', code], capture_output=True, text=True)
        code_result = result.stdout
        logger.info(f"run result: {code_result}")
        return code_result
    
class RunnableCoder(Role):
    def __init__(self, name="Alice", profile="RunnableCoder", **kwargs):
        super().__init__(name=name, profile=profile, **kwargs)
        self._init_actions([SimpleWriteCode, SimpleRunCode])
        self._set_react_mode(react_mode="by_order")

    # 1. 在react_mode是by_order的情况下, 这个_act()方法，会被Role多次调用, 每次在进入它执行之前
    # 通过self._set_state设定action的上下文
    async def _act(self):
        logger.info(f"{self._setting}: prepare to run {self.rc.todo}")
        todo = self.rc.todo
        message = self.get_memories(k=1)[0]
        # 执行action
        result = await todo.run(message.content)
        print(f"runnable result={result}")
        message = Message(content=result, role=self.profile, cause_by=type(todo))
        self.rc.memory.add(message) 
        return message
    
async def main():
    msg = "write a function that calculate the sum of a list"
    logger.info(msg)
    role = RunnableCoder()
    result = await role.run(msg)
    logger.info(f"final result={result}")

asyncio.run(main())