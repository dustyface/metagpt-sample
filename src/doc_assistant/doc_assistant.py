import asyncio
from metagpt.roles import Role
from metagpt.actions import Action
from metagpt.schema import Message
from metagpt.logs import logger
from typing import Dict 
from metagpt.utils.common import OutputParser
from datetime import datetime
from metagpt.const import METAGPT_ROOT
from metagpt.utils.file import File

class WriteDirectory(Action):
    language: str = ""

    def __init__(self, name:str="", language:str="Chinese", *args, **kwargs):
        super().__init__(name=name, *args, **kwargs)
        self.language = language

    async def run(self, topic:str, *args, **kwargs) -> Dict:
        COMMON_PROMPT = """
        You are a seasoned techincal professional in the field of internet,
        we need you to write technical tutorial with the topic "{topic}".
        """
        DIRECTORY_PROMPT = COMMON_PROMPT + """
        Please provide the specific table of contents for this tutorial, strictly following the following requirements:
        1. The output must be strictly in the specified language, {language}.
        2. Answer strictly in the dictionary format like {{"title": "xxx", "directory": [{{"dir 1": ["sub dir 1", "sub dir 2"]}}, {{"dir 2": ["sub dir 3", "sub dir 4"]}}]}}. keep the title and directory property of the dictionary in English, as to others, use the specified language. take below as an example:
        ```
        {{ "title": "Git教程", "directory": [{{"MySQL简介": ["1.1 什么是MySQL", "1.2 MySQL的优点"]}}, {{ "安装和配置MySQL": ["安装MySQL", "配置MySQL"]}}] }}
        ``` 
        3. The directory should be as specific and sufficient as possible, with a primary and secondary directory.The secondary directory is in the array.
        4. Make sure the output strictly comform to the format of JSON. 
        5. Make sure the punctuation appeared in the output JSON, such as comma, curly brace, double quote, etc, is in English
        6. Do not have extra spaces or line breaks.
        7. Each directory title has practical significance.
        """

        prompt = DIRECTORY_PROMPT.format(topic=topic, language=self.language)
        rsp = await self._aask(prompt=prompt)
        try:
            return OutputParser.extract_struct(rsp, dict)
        except Exception as e:
            logger.error(f"Failed to parse the directory: {e}")
            return None


class WriteContent(Action):
    language: str = ""
    directory: str = ""

    def __init__(self, name:str = "", directory: str = "", language: str = "Chinese", *args, **kwargs):
        super().__init__(name=name, *args, **kwargs)
        self.language = language
        self.directory = directory

    async def run(self, topic: str, *args, **kwargs) -> str:
        COMMON_PROMPT = """
        You are now a seasoned technical professional in the field of the internet. 
        We need you to write a technical tutorial with the topic "{topic}".
        """
        CONTENT_PROMPT = COMMON_PROMPT +  """
        Now I will give you the module directory titles for the topic. 
        Please output the detailed principle content of this title in detail. 
        If there are code examples, please provide them according to standard code specifications. 
        Without a code example, it is not necessary.

        The module directory titles for the topic is as follows:
        {directory}

        Strictly limit output according to the following requirements:
        1. Follow the Markdown syntax format for layout.
        2. If there are code examples, they must follow standard syntax specifications, have document annotations, and be displayed in code blocks.
        3. The output must be strictly in the specified language, {language}.
        4. Do not have redundant output, including concluding remarks.
        5. Strict requirement not to output the topic "{topic}".
        """
        prompt = CONTENT_PROMPT.format(topic=topic, language=self.language, directory=self.directory)
        return await self._aask(prompt=prompt)

class TutorialAssitant(Role):
    """Tutorial assistant, input one sentence to generate a tutorial document in markup format."""
    topic: str = ""
    main_title: str = ""
    total_content: str = ""
    language: str = ""

    def __init__(self, name: str="Stitch", profile: str="Tutorial Asistant", goal: str="Generate tutorial documents", constraints: str = "Strictly follow Markdown's syntax, with neat and standardized layout", language: str = "Chinese"):
        super().__init__(name=name, profile=profile, goal=goal, constraints=constraints)
        self._init_actions([WriteDirectory(language=language)])
        self.topic = ""
        self.main_title = ""
        # 全部topic的全部内容
        self.total_content = ""
        self.language = language

    # TutorialAsisatnt Role需要重写Role base class的_react
    # 1. 由于本例的第一个action是WriteDirectory, 生成的内容是动态的，不确定长度的；Role原有的_react, while的条件是`actions_taken < self.rc.max_react_loop`, 是固定的步数, 不适用本例；
    # 2. 当think-act loop完成后，本例需要输出由writeContent写的全部内容到文件；
    # 3. 注意, 每一步的think完成后, self.rc.todo为None是没有需要执行剩余动作的标识 
    async def _react(self) -> Message:
        while True:
            await self._think()
            if self.rc.todo is None:
                break
            msg = await self._act()
        output_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        root_path = METAGPT_ROOT / f"generated_doc/{output_date}"
        await File.write(root_path, f"{self.main_title}.md", self.total_content.encode('utf-8'))
        return msg
    
    async def _think(self) -> None:
        """Determine the next action to be taken by the role"""
        if self.rc.todo is None:
            self._set_state(0)
            return
        # 推进执行下一个action，或者执行完之后，设定rc.todo = None
        if self.rc.state + 1 < len(self.states):
            self._set_state(self.rc.state + 1)
        else:
            self.rc.todo = None
    
    # 在react_mode模式下, _think->_act loop, _act被多次执行；第一次是WriteDirectory；后续的action是根据WriteDirectory动态返回的
    async def _act(self) -> Message:
        todo = self.rc.todo
        if type(todo) is WriteDirectory:
            msg = self.rc.memory.get(k=1)[0]
            self.topic = msg.content
            rsp = await todo.run(topic=self.topic)
            logger.info(self.topic, rsp)
            # handle_directory会将WriteDirectory生成的目录一级标题对应的action添加到self.actions列表中；
            msg = await self._handle_directory(rsp)
            return msg
        # below branch is for WriteContent
        rsp = await todo.run(topic=self.topic)
        logger.info(rsp)
        # 把根据每个一级标题生成的内容加到total_content
        if self.total_content != "":
            self.total_content += "\n\n\n"
        self.total_content += rsp
        return Message(content=rsp, role=self.profile)

    async def _handle_directory(self, titles: Dict) -> Message:
        """
        Handle the directories for the tutorial document.
        
        Args:
            title: A dictionary containing the titles and directory structure, such as
            {"title": "xxx", "directory": [{"dir 1": ["sub dir 1", "sub dir 2"]}, {"dir 2": ["sub dir 3", "sub dir 4"]}]}

        """
        self.main_title = titles.get("title")
        directory = f"{self.main_title}"
        self.total_content += f"# {self.main_title}"
        actions = list()
        for first_level_dir in titles.get("directory"):
            # 根据directory的个数情况，append WriteContent
            actions.append(WriteContent(directory=first_level_dir, language=self.language))
            key = list(first_level_dir.keys())[0]
            directory += f" - {key}\n"
            for second_level_dir in first_level_dir.get(key):
                directory += f" - {second_level_dir}\n"
        self._init_actions(actions)
        self.rc.todo = None
        # 把directory的目录返回
        return Message(content=directory)

async def main():
    # msg = "MySQL 教程"
    msg_list = ["Git-lab 教程"]
    # msg_list = ["Git 教程", "Git-lab 教程", "Docker 教程"]
    for msg in msg_list:
        role = TutorialAssitant()
        result = await role.run(msg)
        logger.info(result)


asyncio.run(main())