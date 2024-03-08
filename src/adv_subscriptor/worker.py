from metagpt.actions.action import Action
from metagpt.roles import Role
from metagpt.tools.web_browser_engine import WebBrowserEngine
from metagpt.subscription import SubscriptionRunner
from metagpt.schema import Message
from uuid import uuid4
import sys
import ast
import argparse
import asyncio

# 订阅的SubAction的行为: 根据parse function执行后的结构，回答用户结构化需求中的Post Processing requirements
TEMPLATE_SUB_ACTION="""
## Requirments
Answer the question based on the provided context {process}. If the question can't be answered, please summarize the content.

## context
{data}
"""


class ExecuteSubscriptionRole(Role):
    name: str = "Conner"
    profile: str = "ExecuteSubscriptionRole"

    def __init__(self, *args, **kwargs):
        super().__init__()

class AddSubscriptionTask(Action):
    name: str = "Lao Cang"
    urls: list[str] = []
    code: str = ""
    user_requirement: str = ""

    def __init__(self, urls: list[str], code: str, user_requirement: str):
        super().__init__()
        self.urls = urls
        self.code = code
        self.user_requirement = user_requirement

    async def run(self, *args, **kwargs):
        modules = {}
        for url in self.urls[::-1]:
            # code其实是多个# {url}\n{parse function}的字符串组合
            code = self.code.rsplit(f"# {url}", maxsplit=1)[1]
            name = uuid4().hex
            module = type(sys)(name)
            exec(code, module.__dict__)
            modules[url] = module

        pages = await WebBrowserEngine().run(*self.urls)
        if len(self.urls) == 1:
            pages = [pages]
        data = []
        for url, page in zip(self.urls, pages):
            data.append(getattr(modules[url], "parse")(page.soup))

        # 这里似乎有bug, url和user_requirement, 应该是一一对应
        # SubAction 根据parse 抓取的内容，回答用户的Post Processing requirements
        rsp = await self.llm.aask(TEMPLATE_SUB_ACTION.format(process=self.user_requirement, data=data))
        return rsp

TRIGGER_INTERVAL = 86400
async def CronTrigger(cron_exp: str):
    while True:
        yield Message(content="CroneTrigger")
        await asyncio.sleep(TRIGGER_INTERVAL)

def worker(urls, code, process, spec):
    print("worker start")
    role = ExecuteSubscriptionRole()
    role.init_actions([AddSubscriptionTask(urls, code, process)])
    runner = SubscriptionRunner()

    async def callback(msg):
        print("msg")
    
    async def run():
        await runner.subscribe(role, CronTrigger(spec), callback)
        await runner.run()
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())

def list_str(values):
    try:
        return ast.literal_eval(values)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalide list: {values}")


def main():    
    parser = argparse.ArgumentParser()
    parser.add_argument("urls", type=list_str, help="urls to crawl")
    parser.add_argument("code", type=str, help="parse function")
    parser.add_argument("process", type=str, help="Post Processing requirements")
    parser.add_argument("spec", type=str, help="CronTrigger spec")
    args = parser.parse_args()
    
    print(args.urls)
    worker(args.urls, args.code, args.process, args.spec)

print("main start")
main()