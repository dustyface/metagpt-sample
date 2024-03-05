import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re

async def fetch(url, proxy: str=None):
    async with aiohttp.ClientSession() as session:
        if not proxy is None:
            async with session.get(url, proxy=proxy) as response:
                response.raise_for_status()
                return await response.text()
        else:
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.text()

async def parse_html(html):
    soup = BeautifulSoup(html, 'html.parser')

    repositories = []
    repo_elements = soup.find_all('article', class_='Box-row')

    # https://beautiful-soup-4.readthedocs.io/en/latest/#searching-by-css-class
    for repo_element in repo_elements:
        name_element = repo_element.find('h2', class_='h3')
        url_element = name_element.find('a')
        description_element = repo_element.find('p', class_='col-9')
        star_element = repo_element.find('a', href=re.compile('stargazers'))
        fork_element = repo_element.find('a', href=re.compile('fork'))
        language_element = repo_element.select_one('span[itemprop="programmingLanguage"]')
        today_start_element = repo_element.select_one('span.d-inline-block.float-sm-right')

        name = name_element.text.strip()
        url = 'https://github.com' + url_element['href'].strip()
        description = description_element.text.strip() if description_element else None
        star_count = star_element.text.strip()
        fork_count = fork_element.text.strip()
        language = language_element.text.strip() if language_element else None
        today_starts = today_start_element.text.strip() if today_start_element else None

        repositories.append({
            'name': name,
            'url': url,
            'description': description,
            'star_count': star_count,
            'fork_count': fork_count,
            'language': language,
            'today_starts': today_starts
        })

    return repositories

async def main():
    url = 'https://github.com/trending'
    html = await fetch(url)
    repositories = await parse_html(html)

    for repo in repositories:
        print(f"仓库名: {repo['name']}")
        print(f"仓库URL: {repo['url']}")
        print(f"仓库描述: {repo['description']}")
        print(f"Star数: {repo['star_count']}")
        print(f"Fork数: {repo['fork_count']}")
        print(f"语言类型: {repo['language']}")
        print(f"今日Star数: {repo['today_starts']}")
        print("\n")

if __name__ == '__main__':
    asyncio.run(main())