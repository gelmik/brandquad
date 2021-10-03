import scrapy
import re
import json
import datetime


class MagnitcosmeticSpider(scrapy.Spider):

    name = "magnitcosmetic"
    ajax = "https://magnitcosmetic.ru/local/ajax/load_remains/catalog_load_remains.php"
    categorys = {}
    allowed_domains = ["magnitcosmetic.ru"]
    start_urls = ["https://magnitcosmetic.ru/catalog/kosmetika/"]

    def parse(self, response):
        cats = response.xpath("//ul[@class = 'section_in_sidebar']/li/a")
        for cat in cats:
            title = cat.xpath("./text()").extract()[0]
            count = int(re.search(r"\d+", title).group())
            if count >= 200:
                self.categorys[title[: title.find("(") - 1]] = {
                    "count": count,
                    "url": "https://magnitcosmetic.ru"
                    + cat.xpath("./@href").extract()[0],
                }

                yield scrapy.Request(
                    "https://magnitcosmetic.ru"
                    + cat.xpath("./@href").extract()[0]
                    + f"?perpage=96",
                    callback=self.parse_category,
                    meta={
                        "category": title[: title.find("(") - 1],
                        "page": 1,
                        "url": "https://magnitcosmetic.ru"
                        + cat.xpath("./@href").extract()[0]
                        + f"?perpage=96",
                    },
                )

    def parse_category(self, response):
        cat = self.categorys[response.meta["category"]]
        items = response.xpath(
            "//div[@class ='catalog__list']/div[@class = 'catalog__item']"
        )
        SHOP_XML_CODE = response.xpath(
            "//input[@class = 'js-shop__xml-code']/@value"
        ).extract()[0]
        for item in items:
            item_products_id = item.xpath("./@data-external").extract()[0]
            item_id = item.xpath("./@data-item").extract()[0]
            url = (
                "https://magnitcosmetic.ru"
                + item.xpath(".//a[@class = 'product__link']/@href").extract()[0]
            )
            image_url = (
                "https://magnitcosmetic.ru"
                + item.xpath(".//img[@class = 'product__image']/@src").extract()[0]
            )
            yield scrapy.Request(
                url,
                callback=self.parse_item,
                meta={
                    "url": url,
                    "RPC": url[url[:-1].rfind("/") + 1 : -1],
                    "main_image": image_url,
                    "SHOP_XML_CODE": SHOP_XML_CODE,
                    "item_products_id": item_products_id,
                    "item_id": item_id,
                },
            )
        if cat["count"] > response.meta["page"] * 96:
            yield scrapy.Request(
                response.meta["url"] + f"&PAGEN_1={response.meta['page'] + 1}",
                callback=self.parse_category,
                meta={
                    "url": response.meta["url"],
                    "category": response.meta["category"],
                    "page": response.meta["page"] + 1,
                },
            )

    def parse_item(self, response):
        meta = response.meta
        meta["title"] = response.xpath("//h1/text()").extract()[0].strip()
        brand = response.xpath(
            "//table[@class = 'action-card__table']//tr/td[text() = 'Бренд:']/following-sibling::td/text()"
        ).extract()
        if brand:
            meta["brand"] = brand[0]
        else:
            meta["brand"] = ""
        meta["section"] = [
            section.strip()
            for section in response.xpath(
                "//div[@class = 'breadcrumbs__list']/div[@class = 'breadcrumbs__item']/a/@title"
            ).extract()
        ]

        src_images = []
        product_image = response.xpath(
            "//div[@class = 'action-card__content']//img[@class = 'product__image']/@src"
        ).extract()
        if product_image != []:
            src_images.append("https://magnitcosmetic.ru" + product_image[0])
            meta["main_image"] = src_images[0]

        slider_images = response.xpath(
            "//div[@class = 'action-card__content']//div[@class = 'slick-list draggable']//div[@class = 'slick-slide']//img/@src"
        ).extract()
        if slider_images != []:
            for slider in slider_images:
                src_images.append("https://magnitcosmetic.ru" + slider)
            meta["main_image"] = src_images[0]

        meta["set_images"] = src_images

        metadata = {}

        description = response.xpath(
            "//div[@class = 'action-card__text']/text()"
        ).extract()
        if description != []:
            metadata["__description"] = description[0]

        mets = response.xpath(
            "//table[@class = 'action-card__table']//tr[position() > 1]"
        )

        for met in mets:
            metadata[met.xpath("./td/text()").extract()[0][:-1]] = (
                met.xpath("./td/text()").extract()[1].strip()
            )
        meta["metadata"] = metadata

        meta["barcode"] = response.xpath(
            "substring-after(//div[@class = 'action-card__text note']/text(), 'Штрихкод:')"
        )

        frmdata = {
            "SHOP_XML_CODE": response.meta["SHOP_XML_CODE"],
            f"PRODUCTS[{response.meta['item_products_id']}]": response.meta["item_id"],
            "type": "detail",
            "ism": "N",
            "JUST_ONE": "Y",
            "enigma": response.xpath(
                "//input[@class= 'js-remains__detail']/@value"
            ).extract()[0],
        }
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36 OPR/79.0.4143.50",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://magnitcosmetic.ru/catalog/kosmetika/brite_i_epilyatsiya/britvennye_stanki_i_lezviya/49705/",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        yield scrapy.FormRequest(
            self.ajax,
            formdata=frmdata,
            method="POST",
            headers=headers,
            callback=self.parse_item_ajax,
            meta=meta,
        )

    def parse_item_ajax(self, response):
        data = json.loads(response.body)["data"][0]
        current = float(data["price_promo"])
        original = float(data["price"])
        yield {
            "timestamp": datetime.datetime.now().timestamp(),  # Текущее время в формате timestamp
            "RPC": response.meta["RPC"],  # {str} Уникальный код товара
            "url": response.meta["url"],  # {str} Ссылка на страницу товара
            "title": response.meta[
                "title"
            ],  # {str} Заголовок/название товара (если в карточке товара указан цвет или объем, необходимо добавить их в title в формате: "{название}, {цвет}")
            "marketing_tags": [],  # {list of str} Список тэгов, например: ['Популярный', 'Акция', 'Подарок'], если тэг представлен в виде изображения собирать его не нужно
            "brand": response.meta["brand"],  # {str} Брэнд товара
            "section": response.meta[
                "section"
            ],  # {list of str} Иерархия разделов, например: ['Игрушки', 'Развивающие и интерактивные игрушки', 'Интерактивные игрушки']
            "price_data": {
                "current": current
                if current > 0
                else original,  # {float} Цена со скидкой, если скидки нет то = original
                "original": original,  # {float} Оригинальная цена
                "sale_tag": f"Скидка {(original - current)/original*100}%"
                if current != 0
                else "Скидка 0%",  # {str} Если есть скидка на товар то необходимо вычислить процент скидки и записать формате: "Скидка {}%"
            },
            "stock": {
                "in_stock": True
                if current > 0
                else False,  # {bool} Должно отражать наличие товара в магазине
                "count": 0,  # {int} Если есть возможность получить информацию о количестве оставшегося товара в наличии, иначе 0
            },
            "assets": {
                "main_image": response.meta[
                    "main_image"
                ],  # {str} Ссылка на основное изображение товара
                "set_images": response.meta[
                    "set_images"
                ],  # {list of str} Список больших изображений товара
                "view360": [],  # {list of str}
                "video": [],  # {list of str}
            },
            "metadata": response.meta["metadata"],
            "variants": 1,  # {int} Кол-во вариантов у товара в карточке (За вариант считать только цвет или объем/масса. Размер у одежды или обуви варинтами не считаются)
        }
