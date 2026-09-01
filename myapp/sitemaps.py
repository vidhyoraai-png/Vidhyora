from django.contrib.sitemaps import Sitemap
from django.urls import reverse

DOMAIN = 'www.edutrellis.in'


class StaticViewSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'weekly'

    priorities = {
        'home': 1.0,
        'ai_page': 0.9,
    }

    def get_urls(self, page=1, site=None, protocol=None):
        protocol = self.protocol
        return [
            {
                'item': item,
                'location': 'https://{}{}'.format(DOMAIN, reverse(item)),
                'lastmod': None,
                'changefreq': self.changefreq,
                'priority': str(self.priorities[item]),
                'alternates': [],
                'x_default': None,
            }
            for item in self.items()
        ]

    def items(self):
        return ['home', 'ai_page']

    def location(self, item):
        return reverse(item)
