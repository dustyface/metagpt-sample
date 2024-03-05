import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re
import time
from metagpt.config import CONFIG 

async def fetch(url):
    # connector = aiohttp.TCPConnector(ssl=True, proxy="http://127.0.0.1:49682")
    async with aiohttp.ClientSession() as session:
        async with session.get(url, proxy=CONFIG.GLOBAL_PROXY) as response:
            response.raise_for_status()
            return await response.text()

async def parse_huggingface_paper(html):
    soup = BeautifulSoup(html, 'html.parser')
    base_url = "https://huggingface.co"
    papers = []
    paper_elements = soup.select('article.rounded-xl.border')
    for paper in paper_elements:
        each_paper = {}
        paper_link = paper.select_one('a.cursor-pointer')
        paper_name = paper.select_one('h3.mb-1.text-lg')
        each_paper['name'] = paper_name.text.strip() if paper_name else None
        each_paper['url'] = base_url + paper_link['href'].strip() if paper_link else None
        papers.append(each_paper)
    return papers

async def parse_huggingface_paper_detail(html):
    soup = BeautifulSoup(html, 'html.parser')
    paper_detail = {}
    base_url = "https://huggingface.co"
    # authors
    authors = []
    authors_element = soup.select('span.contents a.whitespace-nowrap')
    for author in authors_element:
        authors.append({
            'name': author.text.strip(),
            'url': f"{base_url}/{author['href'].strip()}"
        })
    paper_detail['authors'] = authors
    # abstract
    abstract = soup.select_one('p.text-gray-700')
    paper_detail['abstract'] = abstract.text.strip() if abstract else None
    # pdf_url
    pdf_url = soup.find('a', href=re.compile('arxiv.org\/pdf'))
    paper_detail['pdf_url'] = pdf_url['href'] if pdf_url else None
    return paper_detail

def print_each_papaer(paper):
    print(f"论文名: {paper['name']}")
    print(f"论文URL: {paper['url']}")
    print(f"论文摘要: {paper['abstract']}")
    print(f"论文作者: {paper['authors']}")
    print(f"论文PDF地址: {paper['pdf_url']}")
    print("\n\n")

async def crawle_huggingface_papers(date: str, verbose: bool = False):
    html = await fetch(f"https://huggingface.co/papers?date={date}")
    papers = await parse_huggingface_paper(html)
    print(f"Get huggingface {len(papers)} papers")
    # parse each paper's detail
    for paper in papers[:4]:
        paper_detail_html = await fetch(paper['url'])
        paper_detail = await parse_huggingface_paper_detail(paper_detail_html)
        paper['abstract'] = paper_detail['abstract']
        paper['authors'] = paper_detail['authors']
        paper['pdf_url'] = paper_detail['pdf_url']
        if verbose:
            print_each_papaer(paper)
    return papers  

async def main():
    local_time = time.localtime()
    prev_date = local_time.tm_mday - 1
    year, month = local_time.tm_year, local_time.tm_mon
    date= f"{year}-{month}-{prev_date}"
    # parse huggingface papers of the day
    crawle_huggingface_papers(date, verbose=True)
    print("done")

if __name__ == "__main__":
    asyncio.run(main())
