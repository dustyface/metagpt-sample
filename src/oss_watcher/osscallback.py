from typing import Optional
import aiohttp
import os
from dotenv import load_dotenv, find_dotenv
from metagpt.schema import Message

_ = load_dotenv(find_dotenv())

class WxPusherClient:
    def __init__(self, token: Optional[str] = None, base_url: str = "http://wxpusher.zjiecode.com"):
        self.base_url = base_url
        self.token = token or os.environ["WXPUSHER_TOKEN"]

    # 使用wxpusher的实质是给wxpuser的api发POST请求
    async def send_message(
        self,
        content,
        summary: Optional[str] = None,
        content_type: int = 1,
        topic_ids: Optional[list[int]] = None,
        uids: Optional[list[int]] = None,
        verify: bool = False,
        url: Optional[str] = None,
    ):
        payload = {
            "appToken": self.token,
            "content": content,
            "summary": summary,
            "contentType": content_type,
            "topicIds": topic_ids or [],
            "uids": uids or os.environ["WXPUSHER_UIDS"].split(","),
            "verify": verify,
            "url": url
        }
        url = f"{self.base_url}/api/send/message"
        return await self._request("POST", url, json=payload)
    
    async def _request(self, method, url, **kwargs):
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()

# callback是将Role执行后的message发送到wxpusher
async def wxpusher_callback(msg: Message):
    client = WxPusherClient()
    await client.send_message(msg.content)