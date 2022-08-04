import sys, os, multiprocessing as mp

import requests, asyncio
from aiohttp import ClientSession
from bs4 import BeautifulSoup as BS
from alive_progress import alive_it

from config import HEADERS, ROOT_DIR


class Singleton(type):
    def __init__(self, *args, **kwargs):
        self.__instance = None
        super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        if self.__instance is None:
            self.__instance = super().__call__(*args, **kwargs)
            return self.__instance
        
        return self.__instance

class WallpaperFlareParser(metaclass=Singleton):
    __slots__ = ('__tag', '__prog_path', '_img_path', 'headers', 'check_tag')

    def __init__(self) -> None:
        self.__tag = input('Enter search tag or press enter to download all image from main_page: ').strip().lower()
        self.__prog_path = ROOT_DIR
        if not self.__tag:
            self.__tag = 'Main page image'

        if sys.platform == 'win32':
            self._img_path = f'{self.__prog_path}\\image\\{self.__tag}\\'
        else:
            self._img_path = f'{self.__prog_path}/image/{self.__tag}/'

        os.makedirs(self._img_path, exist_ok=True)
        self.headers = HEADERS
        self.check_tag = self.checks_tag()

    def checks_tag(self) -> bool:
        '''Check entering data'''
        return True if self.__tag != 'Main page image' else False

    async def _get_page_source(self, url, session) -> bytes:
        '''Getiing response from every url came from'''
        async with session.get(url) as response:
            if response.status == 200:
                return await response.read()

    async def _collect_tasks(self, urls, session) -> tuple:
        '''Make tasks'''
        tasks = (asyncio.create_task(self._get_page_source(url, session)) for url in alive_it(urls))
        return await asyncio.gather(*tasks)

    async def collect_data(self, urls) -> tuple:
        '''Collect response data'''
        async with ClientSession(headers=self.headers) as session:
            return await self._collect_tasks(urls, session)

    async def __get_pagination(self) -> set:
        '''Return links response as bytes'''
        page = 1
        while True:
            if self.check_tag:
                response = await self.collect_data(urls=[f'https://www.wallpaperflare.com/search?wallpaper={self.__tag}&page={page}'])
                if not response[0]:
                    break 
                page += 1
                yield response[0]
            else:
                response = await self.collect_data(urls=[f'https://www.wallpaperflare.com/index.php?c=main&m=portal_loadmore&page={page}'])
                if not response[0]:
                    break
                page += 1
                yield response[0]

    async def collect_referer_links(self) -> set:
        '''Getting links response and return another'''
        unpuck_response = set()
        async for response in self.__get_pagination():
            if self.check_tag:
                soup = BS(response, 'lxml')
                items = soup.select('ul.gallery > li a[itemprop="url"]')
                if items: 
                    for item in items:
                        unpuck_response.add(item.get('href'))
            else:
                soup = BS(response, 'lxml')
                items = soup.select('body > li a[itemprop="url"]')
                if items:
                    for item in items:
                        unpuck_response.add(item.get('href'))

        return unpuck_response  

    def image_links(self, response) -> str:
        '''Getting page response and return a link'''
        soup = BS(response, 'lxml')
        return soup.select('a.link_btn.aq.mt20')[0].get('href')

    async def get_image_links(self) -> tuple:
        '''Getting links response and return a tuple of links'''
        links = await self.collect_referer_links()
        links_response = await self.collect_data(links)
        with mp.Pool(mp.cpu_count()) as process:
            return process.map(self.image_links, links_response)

    def download_links(self, response) -> str:
        '''Getting page response and return a link'''
        soup = BS(response, 'lxml')    
        return soup.select('section[itemprop="primaryImageOfPage"] > img[id="show_img"]')[0].get('src')

    async def get_download_links(self) -> tuple:
        '''Getting links response and return a tuple of links'''
        links = await self.get_image_links()
        links_response = await self.collect_data(links)
        with mp.Pool(mp.cpu_count()) as process:
            return process.map(self.download_links, links_response)

    def download(self, link) -> None:
        '''Downloading image'''
        session = requests.Session()
        response = session.get(link, headers=self.headers)
        num = link.split('-')[-1].split('.')[0] 
        extension = link.split('.')[-1]
        with open(f'{self._img_path}wallpaper_flare_{num}.{extension}', 'wb') as f:
            f.write(response.content)
  
    async def download_links_response(self) -> None:
        '''Getting download links and download'''
        links = await self.get_download_links()
        with mp.Pool(mp.cpu_count()) as process:
            process.map(self.download, links)

    @staticmethod
    def rename(path) -> None:
        '''Rename files after download'''
        file = os.listdir(path)
        for index in range(len(file)):
            name = str(file[index].split('_')[-1].split('.')[0])
            os.rename(f'{path}{file[index]}', f'{path}{file[index].replace(name, str(index))}')

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    flare = WallpaperFlareParser()
    asyncio.run(flare.download_links_response())

    flare.rename(flare._img_path)
    end = input('Press anything to close program...')