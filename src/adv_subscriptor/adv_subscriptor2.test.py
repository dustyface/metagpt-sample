from adv_subscriptor2 import spawn_subprocess, ParseSubRequirement, WriteCrawleCode
from metagpt.schema import Message
from metagpt.actions.action_node import ActionNode
from uuid import uuid4
import sys
from metagpt.tools.web_browser_engine import WebBrowserEngine
import asyncio

def test_spawn_subprocess():
    urls = ['https://pitchhub.36kr.com/financing-flash'] 
    req = "生成今天的融资新闻总结。"
    cron_exp = "55 14 * * *"
    code = """
# https://pitchhub.36kr.com/financing-flash
from bs4 import BeautifulSoup

def parse(page: BeautifulSoup) -> dict:
    results = []
    items = page.select('.css-xle9x')
    for item in items:
        title = item.select_one('.item-title a.title').text
        link = item.select_one('.item-title a.title')['href']
        time = item.select_one('.item-other span.time').text
        results.append({'title': title, 'link': link, 'time': time})
    return results
"""
    spawn_subprocess(urls, code, req, cron_exp, file_path="./src/adv_subscriptor/worker.py")

async def test_parse_sub_requirement():
    action = ParseSubRequirement()
    requirements = [Message(content="从36kr创投平台https://pitchhub.36kr.com/financing-flash 爬取所有初创企业融资的信息，获取标题，链接， 时间，总结今天的融资新闻，然后在中午14:55送给我")]
    result = await action.run(requirements)
    print("sub_requirement=", result.instruct_content.dict())  # instruct_content is a dict
    return result

async def test_generate_parse_code(parsed_req: ActionNode):
    cls = ActionNode.create_model_class("ActionModel", {
        "Cron Expression": (str, ...),
        "Crawler URL List": (list[str], ...),
        "Page Content Extraction": (str, ...),
        "Crawle Post Processing": (str, ...),
    })
    code = await WriteCrawleCode().run([Message(content="", instruct_content=cls(**parsed_req.instruct_content.dict()))])
    print("parsed code=", code)
    return code

async def test_answer_user_req(req: dict, code: str):
    urls = req['Crawler URL List']
    process = req['Crawle Post Processing']
    modules = {}
    for url in urls[::-1]:
        # code是多个# {url}\n{parse function}的字符串组合
        parsed_code = code.rsplit(f"# {url}", maxsplit=1)[1]
        name = uuid4().hex
        # give a name to the module that contain the LLM generated parse function
        module = type(sys)(name)
        exec(parsed_code, module.__dict__)
        modules[url] = module
    pages = await WebBrowserEngine().run(*urls)
    if len(urls) == 1:
        pages = [pages]
    for url, page in zip(urls, pages):
        # call the parse function in the module
        data = getattr(modules[url], "parse")(page.soup)
    print("process=", process, "data=", data)

async def test():
    parsed_node = await test_parse_sub_requirement()
    code = await test_generate_parse_code(parsed_node)
    await test_answer_user_req(parsed_node.instruct_content.dict(), code)
    # test_spawn_subprocess()

asyncio.run(test())
