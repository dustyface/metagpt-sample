import asyncio
from metagpt.roles import Role
from metagpt.schema import Message
from metagpt.environment import Environment
from metagpt.actions import Action
from metagpt.subscription import SubscriptionRunner
from metagpt.logs import logger
from typing import ClassVar
from crawler_huggingface import crawle_huggingface_papers
import time

class WriteTableOfContent(Action):
    PROMPT_TEMPLATE: ClassVar["str"] = """
    you are paper analyst, please abstract the context information below and output table of content based on it. the output format is as such:
    ---
    # Table of Content
    ## name of the paper
    ---
    no need to put other extra information, just the table of content.

    context:
    {papers}
    """
    def __init__(self, name: str = "WriteTableOfContent", *args, **kwargs):
        super().__init__(name=name, *args, **kwargs)

    async def run(self, papers: str) -> str:
        prompt = self.PROMPT_TEMPLATE.format(papers=papers)
        rsp = await self._aask(prompt)
        return rsp

class WriteAbstract(Action):
    def __init__(self, name: str = "WriteAbstract", profile: str = "WriteAbstractProfile", **kwargs):
        super().__init__(name=name, profile=profile, **kwargs)
    
    async def run(self, paperList: str) -> str:
        Prompt_template = """
        you are paper analyst, after watching information in the context about the papers, pls output table of content based on it. the output format is as such:

        formate example:

        # Huggingface Papers
        ## Paper Name
        1. authors: xxx, xxx, xxx
        2. abstract: xxx
        3. pdf_url: xxx

        context:
        {paperList}    
        """.format(paperList=paperList)
        rsp = await self._aask(Prompt_template)
        return rsp


class PaperAnalyst(Role):
    def __init__(self, name: str="Alice", profile: str="PaperAnalyst", **kwargs):
        super().__init__(name=name, profile=profile, **kwargs)
        self._init_actions([WriteTableOfContent])
        self._set_react_mode(react_mode="by_order")

    async def _act(self):
        todo = self.rc.todo
        message = self.get_memories(k=1)[0]
        result = await todo.run(message.content)
        message = Message(content=result, role=self.profile, cause_by=type(todo))
        self.rc.memory.add(message)
        return message

async def main():
    local_time = time.localtime()
    prev_date = local_time.tm_mday - 1
    year, month = local_time.tm_year, local_time.tm_mon
    date= f"{year}-{month}-{prev_date}"
    papers_detail = await crawle_huggingface_papers(date, True)
    role = PaperAnalyst()
    result = await role.run(str(papers_detail))
    logger.info(f"final result={result}")

asyncio.run(main())