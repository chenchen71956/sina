from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

import requests

from fetch_option_data import SymbolPinzhong, get_all_pinzhong_lists, symbol_page_url
from fetch_option_symbols import BASE_URL, DEFAULT_HEADERS, OptionSymbol

OPTION_DATA_API = (
    f"{BASE_URL}/futures/api/openapi.php/OptionService.getOptionData"
)

JSONP_PREFIX_RE = re.compile(r"^[^(]+\(")
JSONP_SUFFIX_RE = re.compile(r"\)\s*;?\s*$")


@dataclass(frozen=True)
class CallQuote:
    bid_volume: str
    bid_price: str
    last_price: str
    ask_price: str
    ask_volume: str
    open_interest: str
    change_pct: str
    strike: str
    contract: str


@dataclass(frozen=True)
class PutQuote:
    bid_volume: str
    bid_price: str
    last_price: str
    ask_price: str
    ask_volume: str
    open_interest: str
    change_pct: str
    contract: str


@dataclass(frozen=True)
class OptionChainData:
    product: str
    exchange: str
    pinzhong: str
    calls: list[CallQuote]
    puts: list[PutQuote]
    info: list[Any]


def parse_api_payload(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("{") or raw.startswith("["):
        return json.loads(raw)

    raw = JSONP_PREFIX_RE.sub("", raw, count=1)
    raw = JSONP_SUFFIX_RE.sub("", raw)
    return json.loads(raw)


def fetch_option_data_raw(
    product: str,
    exchange: str,
    pinzhong: str,
    session: requests.Session | None = None,
    timeout: float = 30,
) -> dict[str, Any]:
    sess = session or requests.Session()
    params = {
        "type": "futures",
        "product": product,
        "exchange": exchange,
        "pinzhong": pinzhong,
    }
    headers = {
        **DEFAULT_HEADERS,
        "Referer": symbol_page_url(product, exchange),
    }
    response = sess.get(
        OPTION_DATA_API,
        params=params,
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = parse_api_payload(response.text)

    status_code = payload.get("result", {}).get("status", {}).get("code")
    if status_code != 0:
        raise ValueError(f"接口返回异常 status.code={status_code!r}")

    return payload


def _to_call_quote(row: list[Any]) -> CallQuote:
    return CallQuote(
        bid_volume=str(row[0]),
        bid_price=str(row[1]),
        last_price=str(row[2]),
        ask_price=str(row[3]),
        ask_volume=str(row[4]),
        open_interest=str(row[5]),
        change_pct=str(row[6]),
        strike=str(row[7]),
        contract=str(row[8]),
    )


def _to_put_quote(row: list[Any]) -> PutQuote:
    return PutQuote(
        bid_volume=str(row[0]),
        bid_price=str(row[1]),
        last_price=str(row[2]),
        ask_price=str(row[3]),
        ask_volume=str(row[4]),
        open_interest=str(row[5]),
        change_pct=str(row[6]),
        contract=str(row[7]),
    )


def parse_option_data(
    payload: dict[str, Any],
    product: str,
    exchange: str,
    pinzhong: str,
) -> OptionChainData:
    data = payload["result"]["data"]
    calls = [_to_call_quote(row) for row in data.get("up", [])]
    puts = [_to_put_quote(row) for row in data.get("down", [])]
    return OptionChainData(
        product=product,
        exchange=exchange,
        pinzhong=pinzhong,
        calls=calls,
        puts=puts,
        info=list(data.get("info", [])),
    )


def get_option_data(
    product: str,
    exchange: str,
    pinzhong: str,
    session: requests.Session | None = None,
    timeout: float = 30,
) -> OptionChainData:
    payload = fetch_option_data_raw(
        product,
        exchange,
        pinzhong,
        session=session,
        timeout=timeout,
    )
    return parse_option_data(payload, product, exchange, pinzhong)


def get_option_data_for_symbol(
    symbol: OptionSymbol,
    pinzhong: str,
    session: requests.Session | None = None,
    timeout: float = 30,
) -> OptionChainData:
    return get_option_data(
        symbol.code,
        symbol.exchange,
        pinzhong,
        session=session,
        timeout=timeout,
    )


def get_all_option_data(
    symbol_pinzhong_list: list[SymbolPinzhong] | None = None,
    session: requests.Session | None = None,
    timeout: float = 30,
) -> list[OptionChainData]:
    sess = session or requests.Session()
    items = symbol_pinzhong_list if symbol_pinzhong_list is not None else get_all_pinzhong_lists(
        session=sess,
        timeout=timeout,
    )

    results: list[OptionChainData] = []
    for item in items:
        for pinzhong in item.pinzhong_list:
            chain = get_option_data_for_symbol(
                item.symbol,
                pinzhong,
                session=sess,
                timeout=timeout,
            )
            results.append(chain)

    return results


def main() -> None:
    product = "m_o"
    exchange = "dce"
    pinzhong = "m2609"

    chain = get_option_data(product, exchange, pinzhong)
    print(f"{product}/{exchange}/{pinzhong}")
    print(f"看涨 {len(chain.calls)} 档, 看跌 {len(chain.puts)} 档")
    print("\n示例看涨:")
    print(json.dumps(asdict(chain.calls[0]), ensure_ascii=False, indent=2))
    print("\n示例看跌:")
    print(json.dumps(asdict(chain.puts[0]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
