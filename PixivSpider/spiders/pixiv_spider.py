import scrapy
from PixivSpider.items import PixivspiderItem
from scrapy.exceptions import *


class PixivSpider(scrapy.Spider):
    name = 'pixiv_spider'
    allowed_domains = ['pixiv_net']
    items = []
    count = 0

    # login page
    def start_requests(self):
        return [scrapy.Request(url='https://accounts.pixiv.net/login', callback=self.get_post_key)]

    # login, keep post key
    def get_post_key(self, response):
        # selector by css
        post_key = response.css('#old-login input[name=post_key]::attr(value)').extract_first()

        setting = self.settings
        if not setting['PIXIV_USER_NAME'] or not setting['PIXIV_USER_PASS']:
            raise CloseSpider('username or password error!!!')
        return scrapy.FormRequest(url='https://accounts.pixiv.net/login',
                                  formdata={
                                      'pixiv_id': setting['PIXIV_USER_NAME'],
                                      'password': setting['PIXIV_USER_PASS'],
                                      'post_key': post_key,
                                      'skip': '1',
                                      'mode': 'login'
                                  },
                                  callback=self.logged_in,
                                  dont_filter=True)  # http://www.q2zy.com/articles/2015/12/15/note-of-scrapy/

    # logged in, search by given params
    def logged_in(self, response):
        if response.url == 'https://accounts.pixiv.net/login':
            raise CloseSpider('username or password error!!!')
        yield scrapy.Request(self.generate_url(self.settings['SEARCH_PARAMS']), callback=self.parse, dont_filter=True)

    # parse the searching result
    def parse(self, response):
        # selector by xpath
        # <span class="count-badge">9140件</span>
        result_count = response.xpath('//span[@class="count-badge"]/text()').extract_first()
        # 9140
        self.count = int(result_count[:-1])
        # one page has 20 results
        page_count = int((self.count - 1) / 20) + 1

        # parse all pages
        for i in range(page_count):
            url = self.generate_url(self.settings['SEARCH_PARAMS'] + "&order=date_d&p=" + str(i + 1));
            # print(url)
            yield scrapy.Request(url, callback=self.parse_per_page, dont_filter=True)

    def parse_per_page(self, response):
        image_items = response.xpath('//section[@class="column-search-result"]/ul/li[@class="image-item"]')
        for index, image_item in enumerate(image_items):
            item = PixivspiderItem()

            # print(image_item.extract())
            # http://886.iteye.com/blog/2324619
            # to use relative xpath, there must have '.' ahead
            item['title'] = image_item.xpath('.//h1[@class="title"]/@title').extract()[0]
            item['author'] = image_item.xpath('.//a[@class="user ui-profile-popup"]/@title').extract()[0]
            item['link'] = 'http://www.pixiv.net' + image_item.xpath('.//a/@href').extract()[0]
            item['id'] = int(item['link'].split("illust_id=")[1])
            try:
                bookmark = image_item.xpath('.//a[@class="bookmark-count _ui-tooltip"]/@data-tooltip').extract()[0]
                bookmark = bookmark.replace(',', '')
                item['bookmark'] = int(bookmark[:-4])
            # some pictures have no bookmarks
            except IndexError:
                item['bookmark'] = 0
            except ValueError:
                print(bookmark)

            # insert sort
            self.items.append(item)
            n = len(self.items)
            if n > 1:
                i = 0
                j = n - 2
                while i != j:
                    if item['bookmark'] > self.items[int((i + j) / 2)]['bookmark']:
                        j = int((i + j) / 2)
                    else:
                        i = int((i + j) / 2) + 1
                if item['bookmark'] <= self.items[int((i + j) / 2)]['bookmark']:
                    i += 1
                    j += 1
                for k in range(n - 1, i, -1):
                    self.items[k] = self.items[k - 1]
                self.items[i] = item

            if n >= self.count:
                self.show_results()

    def show_results(self):
        n = min(self.count, self.settings['MAX_RESULTS'])
        for i in range(n):
            item = self.items[i]
            print('\nbookmark:' + str(item['bookmark']) + '\tlink:' + item['link'] + '\ttitle:' + item[
                'title'] + '\tauthor:' +
                  item['author'] + '\n')

    def generate_url(self, search_params):
        return 'http://www.pixiv.net/search.php?{params}'.format(params=search_params)
