from __future__ import annotations

import json
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from fetch_option_symbols import BASE_URL, DEFAULT_HEADERS, OptionSymbol, get_option_symbols


@dataclass(frozen=True)
class SymbolPinzhong:
    symbol: OptionSymbol
    pinzhong_list: list[str]


def symbol_page_url(product: str, exchange: str) -> str:
    return f"{BASE_URL}/futures/view/optionsDP.php/{product}/{exchange}"


def fetch_symbol_page_html(
    product: str,
    exchange: str,
    session: requests.Session | None = None,
    timeout: float = 30,
) -> str:
    sess = session or requests.Session()
    headers = {
        **DEFAULT_HEADERS,
        "Referer": symbol_page_url(product, exchange),
    }
    response = sess.get(symbol_page_url(product, exchange), headers=headers, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_pinzhong_list(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    container = soup.find("div", id="option_suffix")
    if container is None:
        raise ValueError("未找到 id=option_suffix 的合约月份选择区域")

    pinzhong_list: list[str] = []
    for li in container.find_all("li"):
        value = (li.get("data-value") or "").strip()
        if value:
            pinzhong_list.append(value)

    if not pinzhong_list:
        raise ValueError("未解析到任何 pinzhong 合约月份")

    return pinzhong_list


def get_pinzhong_list(
    product: str,
    exchange: str,
    session: requests.Session | None = None,
    timeout: float = 30,
) -> list[str]:
    html = fetch_symbol_page_html(product, exchange, session=session, timeout=timeout)
    return parse_pinzhong_list(html)


def get_pinzhong_list_for_symbol(
    symbol: OptionSymbol,
    session: requests.Session | None = None,
    timeout: float = 30,
) -> list[str]:
    return get_pinzhong_list(symbol.code, symbol.exchange, session=session, timeout=timeout)


def get_all_pinzhong_lists(
    symbols: list[OptionSymbol] | None = None,
    session: requests.Session | None = None,
    timeout: float = 30,
) -> list[SymbolPinzhong]:
    sess = session or requests.Session()
    symbol_list = symbols if symbols is not None else get_option_symbols(session=sess, timeout=timeout)

    results: list[SymbolPinzhong] = []
    for symbol in symbol_list:
        pinzhong_list = get_pinzhong_list_for_symbol(symbol, session=sess, timeout=timeout)
        results.append(SymbolPinzhong(symbol=symbol, pinzhong_list=pinzhong_list))

    return results


def main() -> None:
    all_pinzhong = get_all_pinzhong_lists()
    print(f"共 {len(all_pinzhong)} 个品种:\n")

    summary = [
        {
            "path": item.symbol.path,
            "name": item.symbol.name,
            "pinzhong_list": item.pinzhong_list,
        }
        for item in all_pinzhong
    ]
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
