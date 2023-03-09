from datetime import date

from itemloaders.processors import Compose, Identity, TakeFirst, MapCompose
from scrapy import Spider as BaseSpider
from scrapy.loader import ItemLoader

from juniorguru.lib import loggers
from juniorguru.lib.url_params import strip_params
from juniorguru.sync.scrape_jobs.items import Job, first


logger = loggers.from_path(__file__)


class Spider(BaseSpider):
    name = 'jobscz'
    proxy = True
    download_timeout = 59
    download_delay = 1.25
    custom_settings = {
        'ROBOTSTXT_OBEY': False,
        'COOKIES_ENABLED': False,
    }

    start_urls = [
        'https://beta.www.jobs.cz/prace/?field%5B%5D=200900013&field%5B%5D=200900012&suitable-for=graduates',
    ]

    def parse(self, response):
        card_xpath = "//article[contains(@class, 'SearchResultCard')]"
        for n, card in enumerate(response.xpath(card_xpath), start=1):
            loader = Loader(item=Job(), response=response)
            card_loader = loader.nested_xpath(f'{card_xpath}[{n}]')
            card_loader.add_value('source', self.name)
            card_loader.add_value('first_seen_on', date.today())
            card_loader.add_css('title', 'h2 a::text')
            card_loader.add_css('company_name', '.SearchResultCard__footerItem:nth-child(1) span::text')
            card_loader.add_css('company_logo_urls', '.CompanyLogo img::attr(src)')
            card_loader.add_css('locations_raw', '.SearchResultCard__footerItem:nth-child(2)::text')
            card_loader.add_value('source_urls', response.url)
            item = loader.load_item()
            link = card.css('a[data-link="jd-detail"]::attr(href)')[0]
            yield response.follow(link, cb_kwargs=dict(item=item))
        logger.warning('Not implemented yet: pagination')

    def parse_job(self, response, item):
        if 'www.jobs.cz' not in response.url:
            logger.warning('Not implemented yet: custom job portals')
            return
        loader = Loader(item=item, response=response)
        loader.add_value('url', response.url)
        loader.add_value('source_urls', response.url)
        # TODO
        # loader.add_xpath('employment_types', "//span[contains(text(), 'Typ pracovního poměru')]/following-sibling::p/text()")
        # loader.add_xpath('description_html', "//p[contains(text(), 'Úvodní představení')]/following-sibling::p")
        # loader.add_css('description_html', '.content-rich-text')
        item = loader.load_item()
        yield item


def clean_url(url):
    return strip_params(url, ['positionOfAdInAgentEmail', 'searchId', 'rps'])


def join(values):
    return ''.join(values)


def remove_empty(values):
    return filter(None, values)


def remove_width_param(url):
    return strip_params(url, ['width'])


class Loader(ItemLoader):
    default_input_processor = MapCompose(str.strip)
    default_output_processor = TakeFirst()
    url_in = Compose(first, clean_url)
    company_url_in = Compose(first, clean_url)
    company_logo_urls_in = MapCompose(remove_width_param)
    company_logo_urls_out = Compose(set, list)
    description_html_out = Compose(join)
    employment_types_out = Identity()
    locations_raw_out = Compose(remove_empty, set, list)
    source_urls_out = Identity()
    first_seen_on_in = Identity()