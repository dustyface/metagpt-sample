import asyncio
import sys
from metagpt.actions import Action, UserRequirement
from metagpt.roles import Role
from metagpt.logs import logger
from metagpt.team import Team
from metagpt.actions.action_node import ActionNode
from metagpt.schema import Message
from metagpt.utils.parse_html import _get_soup
from metagpt.tools.web_browser_engine import WebBrowserEngine
from metagpt.utils.common import CodeParser,any_to_str 
from metagpt.utils.parse_html import WebPage
from metagpt.tools import WebBrowserEngineType
from metagpt.subscription import SubscriptionRunner
from uuid import uuid4

# ActionNode的keyword param的含义，和prompt的6个方面的含义一致；
LANGUAGE = ActionNode(
    key="Language",
    expected_type=str,
    instruction="Provide the language used in the project, typically matching the user's requirements.",
    example="en_US"
)

CRON_EXPRESSION=ActionNode(
    key="Cron Expression",
    expected_type=str,
    instruction="If the user requires scheduled triggering, provide the 5-filed cron expression. Otherwise leave it blank.",
    example=""
)

CRAWLE_URL_LIST=ActionNode(
    key="Crawler URL List",
    expected_type=list[str],
    instruction="List the URL that user wants to crawle, or leave it blank if not provided in the requirements",
    example=["https://www.google.com", "https://www.bing.com"]
)

PAGE_CONENT_EXTRACTION=ActionNode(
    key="Page Content Extraction",
    expected_type=str,
    instruction="Specify the requirements and tips to extract from the crawled web page based on user requirements.",
    example="Retrived the titles and content of the article published today."
)

CRAWLE_POST_PROCESSING=ActionNode(
    key="Crawle Post Processing",
    expected_type=str,
    instruction="Specify the processing to be applied to the crawled content, such as summarizing today's news.",
    example="Generate a summary of today's news articles."
)

INFORMATION_SUPPLEMENT = ActionNode(
    key="Information Supplement",
    expected_type=str,
    instruction="If unable to obtain the Cron Expression, prompt the user to provide the time to receive subscription "
    "messages. If unable to obtain the URL List Crawler, prompt the user to provide the URLs they want to crawl. Keep it "
    "blank if everything is clear",
    example="",
)

NODES = [
    LANGUAGE,
    CRON_EXPRESSION,
    CRAWLE_URL_LIST,
    PAGE_CONENT_EXTRACTION,
    CRAWLE_POST_PROCESSING,
    INFORMATION_SUPPLEMENT
]

# the parent action node to parse requirement
PARSE_SUB_REQUIREMENT_NODE=ActionNode.from_children("Parse Requirements", NODES)

TEMPALTE_PARSE_SUB_REQUIREMENTS = """
### User Requirements
{requirements}
"""

# 订阅的SubAction的行为: 根据parse function执行后的结构，回答用户结构化需求中的Post Processing requirements
TEMPLATE_SUB_ACTION="""
## Requirments
Answer the question based on the provided context {process}. If the question can't be answered, please summarize the content.

## context
{data}
"""
# The action parse the original requirements
class ParseSubRequirement(Action):
    async def run(self, requirements: Message):
        # the user requirement stored in the rc.memory
        requirements = "\n".join(i.content for i in requirements)
        context = TEMPALTE_PARSE_SUB_REQUIREMENTS.format(requirements=requirements)
        node = await PARSE_SUB_REQUIREMENT_NODE.fill(context=context, llm=self.llm)
        return node

# Below function is to get the dict depicting the outline of html crawled
def get_outline(page: WebPage):
    soup = _get_soup(page.html)
    outline = []

    def process_element(element, depth):
        name = element.name
        if not name:
            return
        if name in ["script", "style"]:
            return
        
        element_info = { "name": element.name, "depth": depth }
        if name in ["svg"]:
            element_info["text"] = None
            outline.append(element_info)
            return

        element_info["text"] = element.string
        if "id" in element.attrs:
            element_info["id"] = element["id"]
        if "class" in element.attrs:
            element_info["class"] = element["class"]
        
        outline.append(element_info)
        for child in element.children:
            process_element(child, depth+1)
    
    for element in soup.body.children:
        process_element(element, 1)
    return outline

# this template is used to generate the parse user's requirement in the crawled html
# {requirement}: e.g. the PAGE_CONTENT_EXTRACTION in the parsed requirements
# {outline}: e.g. the outline of the html page
TEMPLATE_PROMPT="""
Please complete the web page crawler parse function to achieve the user requirements. 
The parser function should take a BeautifulSoup object as input, which correspond to the HTML outline in the Context.

```
form bs4 import BeautifulSoup

#only complete the parse function
def parse(page: BeautifulSoup) -> dict:
    # Return the object that the user wants to retrieve, don't print content.

```

## User Requirements
{requirements}

## Context
The outline of the HTML page is as follows:

```tree
{outline}
```
"""

# After the ParseSubRequirement action. this action generate the parse function that can extract the user's requirement
class WriteCrawleCode(Action):
    async def run(self, requirements) -> str:
        requirement: Message = requirements[-1]
        data = requirement.instruct_content.dict()
        urls = data['Crawler URL List']
        query = data['Page Content Extraction']

        codes = {}
        for url in urls:
            codes[url] = await self._write_code(url, query)
        return "\n".join(f"# {url}\n{code}" for url, code in codes.items())

    async def _write_code(self, url, query):
        page = await WebBrowserEngine(WebBrowserEngineType.PLAYWRIGHT).run(url)
        outline = get_outline(page)
        outline = "\n".join(f"{' '*i['depth']}{'.'.join([i['name'], *i.get('class', [])])}:{i['text'] if i['text'] else ''}" for i in outline)
        # logger.info(f"outline: {outline}")

        code_rsp = await self._aask(TEMPLATE_PROMPT.format(requirements=query, outline=outline))
        code = CodeParser.parse_code(block="", text=code_rsp)
        return code

# 这个action的执行，是在ParseSubRequirement action和WriteCrawleCode action之后,
# 是在得到结构化需求和生成extract用户所需的content的爬虫代码parse之后，它生成订阅Runner所执行的任务，即爬取url, 执行parse得到用户关心的需求内容, 并和LLM交互得到总结后的答案;
class RunSubscription(Action):
    # @message: Role.rc.history, 是list[Message]类型
    async def run(self, messages: list[Message]):
        code = messages[-1].content  # last message: WriteCrawleCode run return "{url}\n{parsed code}"
        req = messages[-2].instruct_content.dict()
        urls = req['Crawler URL List']
        process = req['Crawle Post Processing']
        spec = req['Cron Expression']
        # SubscriptionRunner所执行到action
        SubAction = self.create_sub_action_cls(urls, code, process)
        # type(name: str, bases: Tuple[Type], namespace: Dict[str, Any]), can create a type dynamically
        # Note: 不能在namespace 参数里定义属性，否则报错, 参考: https://docs.pydantic.dev/2.5/errors/usage_errors/#model-field-overridden
        SubRole = type("SubRole", (Role,), {})
        role = SubRole()
        role._init_actions([SubAction])
        runner = SubscriptionRunner()

        async def callback(msg):
            print(msg)

        await runner.subscribe(role, CronTrigger(spec), callback)
        await runner.run()
    
    @staticmethod
    def create_sub_action_cls(urls: list[str], code, process):
        print(f"create_sub_action_cls urls={urls}, code={code}, process={process}")
        modules = {}
        for url in urls[::-1]:
            code, current = code.rsplit(f"# {url}", maxsplit=1)
            name = uuid4().hex
            module = type(sys)(name)
            # 把parse function定义为moduled的function
            exec(current, module.__dict__)
        modules[url] = module

        class SubAction(Action):
            async def run(self, *args, **kwargs):
                pages = await WebBrowserEngine().run(*urls)
                if len(urls) == 1:
                    pages = [pages]
                
                data = []
                for url, page in zip(urls, pages):
                    # getattr 是builtin.pyi中function, 
                    data.append(getattr(modules[url], "parse")(page.soup))
                # SubAction 根据parse 抓取的内容，回答用户的Post Processing requirements
                return await self.llm.aask(TEMPLATE_SUB_ACTION.format(process=process, data=data))

        return SubAction

class CrawleEngineer(Role):
    name: str = "Henter"
    profile: str = "CrawleEngineer"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([WriteCrawleCode])
        self._watch([ParseSubRequirement])

class SubscriptionAssistant(Role):
    name: str = "Machial"
    profile: str = "Subscrition Assistant"
    goal: str = "analyze user subscription requirements to provide personalized subscription services."
    constraints: str = "use the same language as the user's requirements."

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([ParseSubRequirement, RunSubscription])
        self._watch([UserRequirement, WriteCrawleCode])
    
    async def _think(self) -> bool:
        cause_by = self.rc.history[-1].cause_by
        if cause_by == any_to_str(UserRequirement):
            state = 0   # execute ParseSubRequirement action?
        elif cause_by == any_to_str(WriteCrawleCode):
            state = 1   # when WriteCrawleCode action is executed, execute RunSubscription action
        
        logger.debug(f"role: {self._setting}, _think: rc.history={self.rc.history}, cause_by={cause_by}, state={state}")
        if self.rc.state == state:
            self.rc.todo = None
            return False
        self._set_state(state)
        return True
    
    async def _act(self):
        response = await self.rc.todo.run(self.rc.history)
        message = Message(
            content = response.content,
            instruct_content = response.instruct_content,
            role = self.profile,
            cause_by = self.rc.todo,
            sent_from = self
        )
        self.rc.memory.add(message)
        return message

# TRIGGER_INTERVAL = 10
TRIGGER_INTERVAL = 86400

async def CronTrigger(cron_exp: str):
    while True:
        yield Message(content="CroneTrigger")
        await asyncio.sleep(TRIGGER_INTERVAL)

if __name__ == "__main__":
    async def test():
        action = ParseSubRequirement()
        requirements = [Message(content="从36kr创投平台https://pitchhub.36kr.com/financing-flash 爬取所有初创企业融资的信息，获取标题，链接， 时间，总结今天的融资新闻，然后在晚上七点半送给我")]
        result = await action.run(requirements)
        print(result.instruct_content.dict())  # instruct_content is a dict

        cls = ActionNode.create_model_class("ActionModel", {
            "Cron Expression": (str, ...),
            "Crawler URL List": (list[str], ...),
            "Page Content Extraction": (str, ...),
            "Crawle Post Processing": (str, ...),
        })
        code = await WriteCrawleCode().run([Message(content="", instruct_content=cls(**result.instruct_content.dict()))])
        print("code=", code)
        # check the code execution
        urls = result.instruct_content.dict()['Crawler URL List']
        process = result.instruct_content.dict()['Crawle Post Processing']
        modules = {}
        for url in urls[::-1]:
            parse_code = code.rsplit(f"# {url}", maxsplit=1)[1]
            name = uuid4().hex
            module = type(sys)(name)
            # 把parse function定义为moduled的function
            exec(parse_code, module.__dict__)
            modules[url] = module
        # load the page
        pages = await WebBrowserEngine().run(*urls)
        if len(urls) == 1:
            pages = [pages]
        for url, page in zip(urls, pages):
            # getattr 是builtin.pyi中function, 
            data = getattr(modules[url], "parse")(page.soup)
            print("data=", data, "process=", process)

    async def main():
        team = Team()
        team.hire([SubscriptionAssistant(), CrawleEngineer()])
        requirement = "从36kr创投平台https://pitchhub.36kr.com/financing-flash爬取所有初创企业融资的信息，获取标题，链接， 时间，总结今天的融资新闻，然后在14:55发送给我"
        team.run_project(requirement)
        await team.run()

    # asyncio.run(test())
    asyncio.run(main())
