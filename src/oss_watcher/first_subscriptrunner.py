import asyncio
from metagpt.subscription import SubscriptionRunner
from metagpt.roles import Searcher
from metagpt.tools.search_engine import SearchEngine
from metagpt.schema import Message
from metagpt.environment import Environment
from dotenv import load_dotenv,find_dotenv

_ = load_dotenv(find_dotenv())

# test_sleep_interval = 5
test_sleep_interval = 3600 * 24

async def trigger():
    while True:
        yield Message(content="the latest news about OpenAI")
        await asyncio.sleep(test_sleep_interval)

async def callback(msg: Message):
    print(f"Received message: {msg.content}")

async def main():
    env = Environment()
    pb = SubscriptionRunner()
    # await pb.subscribe(SearchEngine(), trigger, callback)
    await pb.subscribe(Searcher(), trigger(), callback)
    await pb.run()

asyncio.run(main())