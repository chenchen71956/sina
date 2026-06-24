#!/usr/bin/env python3
"""从新浪商品期权页面获取全部期权品种列表。"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://stock.finance.sina.com.cn"
OPTIONS_PAGE_URL = f"{BASE_URL}/futures/view/optionsDP.php"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": OPTIONS_PAGE_URL,
}

# href 示例: /futures/view/optionsDP.php/m_o/dce
HREF_SUFFIX_RE = re.compile(r"/futures/view/optionsDP\.php/([^/]+)/([^/?#]+)")


@dataclass(frozen=True)
class OptionSymbol:

    code: str
    name: str
    exchange: str
    href: str
    path: str

    @property
    def url(self) -> str:
        return urljoin(BASE_URL, self.href)


def fetch_options_page_html(
    session: requests.Session | None = None,
    timeout: float = 30,
) -> str:
    sess = session or requests.Session()
    response = sess.get(OPTIONS_PAGE_URL, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_option_symbols(html: str) -> list[OptionSymbol]:
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("div", id="option_symbol")
    if container is None:
        raise ValueError("未找到 id=option_symbol 的期权品种选择区域")

    symbols: list[OptionSymbol] = []
    for li in container.find_all("li"):
        anchor = li.find("a", href=True)
        if anchor is None:
            continue

        href = anchor["href"].strip()
        match = HREF_SUFFIX_RE.search(href)
        if not match:
            continue

        code, exchange = match.group(1), match.group(2)
        name = anchor.get_text(strip=True)
        path = f"{code}/{exchange}"

        symbols.append(
            OptionSymbol(
                code=code,
                name=name,
                exchange=exchange,
                href=href,
                path=path,
            )
        )

    if not symbols:
        raise ValueError("未解析到任何期权品种")

    return symbols


def get_option_symbols(
    session: requests.Session | None = None,
    timeout: float = 30,
) -> list[OptionSymbol]:
    html = fetch_options_page_html(session=session, timeout=timeout)
    return parse_option_symbols(html)


def get_option_paths(
    session: requests.Session | None = None,
    timeout: float = 30,
) -> list[str]:
    return [item.path for item in get_option_symbols(session=session, timeout=timeout)]


def print_symbols(symbols: Iterable[OptionSymbol]) -> None:
    for item in symbols:
        print(f"{item.path}\t{item.name}\t{item.url}")


def main() -> None:
    symbols = get_option_symbols()
    print(f"共获取 {len(symbols)} 个期权品种:\n")
    print_symbols(symbols)

    print("\n仅 path 列表 (JSON):")
    print(json.dumps([item.path for item in symbols], ensure_ascii=False, indent=2))

    print("\n完整数据 (JSON):")
    print(json.dumps([asdict(item) for item in symbols], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
