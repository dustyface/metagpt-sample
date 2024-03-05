import time
import asyncio
from pydantic import BaseModel, Field
from pytz import BaseTzInfo
from typing import Optional
from aiocron import crontab
from metagpt.schema import Message


class OssInfo(BaseModel):
    url: str
    timestamp: float = Field(default_factory=time.time)

class GithubTrendingCronTrigger:

    def __init__(self, spec: str, tz: Optional[BaseTzInfo]=None, url: str="https://github.com/trending") -> None:
        self.url = url
        self.crontab = crontab(spec, tz=tz)
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        await self.crontab.next()
        return Message(content=self.url, instruct_content=OssInfo(url=self.url))

async def GithubTrendingIntervalTrigger(url: str="https://github.com/trending"):
    while True:
        yield Message(content=url)
        await asyncio.sleep(3600 * 24)