from metagpt.actions import Action
from metagpt.actions.action_node import ActionNode
from metagpt.roles import Role
from metagpt.schema import Message
from metagpt.logs import logger
import asyncio
import re


SIMPLE_THINK_NODE=ActionNode(
    key="Simple Think Node",
    expected_type=str,
    instruction="""
        Think about what list of number you need to generate.
        """,
    example=""
)

SIMPLE_CHECK_NODE=ActionNode(
    key="Simple Check Node",
    expected_type=str,
    instruction="""
        Please provide the number list for me, strictly following the following requirements:
        1. Answer strictly in the list format like [1,2,3,4]
        2. Do not have space or line breaks
        return the list here:
        """,
    example="[1,2,3,4]"
)

# Parent ActionNode that execute every children ActionNode object.
class THINK_NODES(ActionNode):
    def __init__(self, name="Think Nodes", expected_type=str, instruction="", example=""):
        super().__init__(name, expected_type=expected_type, instruction=instruction, example=example)
        self.add_children([SIMPLE_THINK_NODE, SIMPLE_CHECK_NODE])

    async def fill(self, context, llm, schema="raw", mode="auto", strgy="complex"):
        self.set_llm(llm)
        self.set_context(context)
        if self.schema:
            schema = self.schema
        
        if strgy == "simple":
            return await self.simple_fill(schema=schema, mode=mode)
        elif strgy == "complex":
            child_context = context
            for _, i in self.children.items():
                i.set_context(child_context)
                child = await i.simple_fill(schema=schema,mode=mode)
                child_context = child.content
            # 把最后一个child的content结果，赋给parent actionnode的content
            self.content = child_context
            return self

class SimplePrint(Action):
    input_num: int = 0

    def __init__(self, name="SimplePrint", input_num: int=0):
        super().__init__(name=name, input_num=input_num)
        self.input_num = input_num

    async def run(self, **kwags):
        print(str(self.input_num) + "\n")
        return str(self.input_num)

# the Action object where the ActionNode mount to
class ThinkAction(Action):
    def __init__(self, name="ThinkAction", context=None, llm=None):
        super().__init__(name=name, context=context, llm=llm)
        self.node = THINK_NODES()   # mount the ActionNode to this actoin object

    async def run(self, instruction) -> list:
        PROMPT = """
            you are now a number list generator.follow the instruction {instruction} and 
            generate a number list to be printed please
        """
        prompt = PROMPT.format(instruction=instruction)
        rsp_node = await self.node.fill(context=prompt, llm=self.llm, schema="raw", strgy="complex")
        rsp = rsp_node.content
        rsp_match = self.find_in_brackets(rsp)
        try:
            rsp_list = [int(x.strip()) for x in iter(rsp_match[0].split(','))]
            return rsp_list
        except:
            return []

    @staticmethod
    def find_in_brackets(s):
        pattern = r"\[(.*?)\]"
        match = re.findall(pattern, s)
        return match

class Printer(Role):
    def __init__(self, name="Printer", profile="Printer", **kwargs):
        super().__init__(name=name, profile=profile, **kwargs)
        self._init_actions([ThinkAction])

    async def _think(self):
        if self.rc.todo == None:
            self._set_state(0)
            return        
        if self.rc.state + 1 < len(self.states):
            self._set_state(self.rc.state + 1)
        else:
            self.rc.todo = None

    async def _react(self) -> Message:
        while True:
            await self._think()
            if self.rc.todo == None:
                break
            msg = await self._act()
        return msg

    # 这是Role反复调用的_act
    async def _act(self):
        todo = self.rc.todo

        if type(todo) is ThinkAction:
            msg = self.rc.memory.get(k=1)[0]
            self.goal = msg.content
            rsp = await todo.run(instruction=self.goal)
            return await self._prepare_print(rsp)

        rsp = await todo.run()
        return Message(content=rsp, role=self.profile)

    async def _prepare_print(self, num_list:list) -> Message:
        """Add actions"""
        actions = list()
        for num in num_list:
            actions.append(SimplePrint(input_num=num))
        
        self._init_actions(actions)
        self.rc.todo = None
        return Message(content=str(num_list))

async def main():
    msg = "Provide the first 10 number of the Fibonacci series"
    role = Printer()
    logger.info(msg)
    result = await role.run(msg)
    logger.info(result)

if __name__ == "__main__":
    asyncio.run(main())