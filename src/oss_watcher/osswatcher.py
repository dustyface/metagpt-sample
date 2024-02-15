from crawler_trending import fetch, parse_html
from osstrigger import OssInfo, GithubTrendingCronTrigger, GithubTrendingIntervalTrigger
from osscallback import wxpusher_callback
from metagpt.actions import Action
from metagpt.config import CONFIG
from metagpt.schema import Message
from metagpt.subscription import SubscriptionRunner
from metagpt.environment import Environment
from metagpt.logs import logger
from metagpt.roles import Role
from typing import Any
import asyncio

class CrawlOSSTrending(Action):
    async def run(self, url: str="https://github.com/trending"):
        #  html = await fetch(url, proxy=CONFIG.GLOBAL_PROXY)
         html = await fetch(url) 
         repositories = await parse_html(html)
         return repositories

TRENDING_ANALYSIS_PROMPT="""# Requirements
You are a GitHub Trending Analyst, aiming to provide users with insightful and personalized recommendations based on the latest
GitHub Trends. Based on the context, fill in the following missing information, generate engaging and informative titles, 
ensuring users discover repositories aligned with their interests.

# Title: it's about Today's GitHub Trending
## Today's Trends: Uncover the Hottest GitHub Projects Today! Explore the trending programming languages and discover key domains capturing developers' attention. From ** to **, witness the top projects like never before.
## The Trends Categories: Dive into Today's GitHub Trending Domains! Explore featured projects in domains such as ** and **. Get a quick overview of each project, including programming languages, stars, and more.
## Highlights of the List: Spotlight noteworthy projects on GitHub Trending, including new tools, innovative projects, and rapidly gaining popularity, focusing on delivering distinctive and attention-grabbing content for users.

---

below is output formatted example:

```
# GitHub Trending Analytics

## Today's Trends
Today, ** and ** continue to dominate as the most popular programming languages. Key areas of interest include **, ** and **.
The top popular projects are Project1 and Project2.

## The Trends Categories
1. Generative AI
    - [*****](https://github/xx/project1): [detail of the project, such as star total and today, language, ...]
    - [*****](https://github/xx/project2): ...
...

## Highlights of the List
1. [*****](https://github/xx/project1): [provide specific reasons why this project is recommended].
...
```

---
context:

# Github Trending
{trending}
"""

class AnalysisOSSTrending(Action):
     async def run(self, trending: Any):
          return await self._aask(TRENDING_ANALYSIS_PROMPT.format(trending=trending))

class OssWatcher(Role):
    def __init__(self, 
        name: str="Tony",
        profile: str="OssWatcher",
        goal="Generate an insightful GitHub Trending analysis report.",
        constraints="Only analyze based on the provided GitHub Trending data."):
        super().__init__(name=name, profile=profile, goal=goal, constraints=constraints)
        self._init_actions([CrawlOSSTrending, AnalysisOSSTrending])  
        self._set_react_mode(react_mode="by_order")
    
    async def _act(self) -> Message:
        logger.info(f"{self._setting}: prepare to run {self.rc.todo}")
        todo = self.rc.todo
        msg = self.get_memories(k=1)[0]
        result = await todo.run(msg.content)
        msg = Message(content=str(result), role=self.profile, cause_by=type(todo))
        self.rc.memory.add(msg)
        return msg

async def main(spec: str = "0 9 * * *", wxpusher: bool = True):
    env = Environment()
    callbacks = []    
    if wxpusher:
        callbacks.append(wxpusher_callback)

    if not callbacks:
        async def _print(msg: Message):
            print(msg.content)
        callbacks.append(_print)
    
    async def callback(msg):
        await asyncio.gather(*[call(msg) for call in callbacks])
    
    runner = SubscriptionRunner()
    # await runner.subscribe(OssWatcher(), GithubTrendingCronTrigger(spec), callback)
    await runner.subscribe(OssWatcher(), GithubTrendingIntervalTrigger(), callback)
    await runner.run()

asyncio.run(main())