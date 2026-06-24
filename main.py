from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import requests

from fetch_option_data import get_all_pinzhong_lists
from fetch_option_quotes import OptionChainData, get_option_data_for_symbol

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = ROOT_DIR / "csv"
SUMMARY_CSV_PATH = DEFAULT_OUTPUT_DIR / "open_interest_summary.csv"

UP_HEADERS = ["品种", "合约", "买量", "买价", "最新价", "卖价", "卖量", "持仓量", "涨跌", "行权价"]
DOWN_HEADERS = ["品种", "合约", "买量", "买价", "最新价", "卖价", "卖量", "持仓量", "涨跌", "行权价"]
SUMMARY_HEADERS = ["品种", "名称", "看涨持仓量", "看跌持仓量"]

STRIKE_FROM_CONTRACT_RE = re.compile(r"[PC](\d+)$")
PINZHONG_RE = re.compile(r"^([a-zA-Z]+)(\d+)$")


@dataclass
class ProductOpenInterest:
    product: str
    variety: str
    name: str
    call_open_interest: int = 0
    put_open_interest: int = 0


def parse_open_interest(value: str) -> int:
    text = str(value).strip()
    if text in ("", "-", "--"):
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def sum_chain_open_interest(chain: OptionChainData) -> tuple[int, int]:
    call_total = sum(parse_open_interest(quote.open_interest) for quote in chain.calls)
    put_total = sum(parse_open_interest(quote.open_interest) for quote in chain.puts)
    return call_total, put_total


def save_open_interest_summary_csv(
    summaries: list[ProductOpenInterest],
    output_path: Path = SUMMARY_CSV_PATH,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(SUMMARY_HEADERS)
        for item in summaries:
            writer.writerow([
                item.variety,
                item.name,
                item.call_open_interest,
                item.put_open_interest,
            ])

    return output_path


def csv_base_name(product: str, pinzhong: str) -> str:
    return f"{product}-{pinzhong}"


def up_csv_path(output_dir: Path, product: str, pinzhong: str) -> Path:
    return output_dir / f"{csv_base_name(product, pinzhong)}-up.csv"


def down_csv_path(output_dir: Path, product: str, pinzhong: str) -> Path:
    return output_dir / f"{csv_base_name(product, pinzhong)}-down.csv"


def parse_pinzhong(pinzhong: str) -> tuple[str, str]:
    match = PINZHONG_RE.match(pinzhong)
    if match is None:
        raise ValueError(f"无法解析 pinzhong: {pinzhong}")
    return match.group(1), match.group(2)


def strike_from_contract(contract: str) -> str:
    match = STRIKE_FROM_CONTRACT_RE.search(contract)
    if match is None:
        raise ValueError(f"无法从合约代码解析行权价: {contract}")
    return match.group(1)


def call_to_row(pinzhong: str, quote) -> list[str]:
    variety, contract = parse_pinzhong(pinzhong)
    return [
        variety,
        contract,
        quote.bid_volume,
        quote.bid_price,
        quote.last_price,
        quote.ask_price,
        quote.ask_volume,
        quote.open_interest,
        quote.change_pct,
        quote.strike,
    ]


def put_to_row(pinzhong: str, quote) -> list[str]:
    variety, contract = parse_pinzhong(pinzhong)
    return [
        variety,
        contract,
        quote.bid_volume,
        quote.bid_price,
        quote.last_price,
        quote.ask_price,
        quote.ask_volume,
        quote.open_interest,
        quote.change_pct,
        strike_from_contract(quote.contract),
    ]


def save_option_chain_csv(
    chain: OptionChainData,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    up_path = up_csv_path(output_dir, chain.product, chain.pinzhong)
    down_path = down_csv_path(output_dir, chain.product, chain.pinzhong)

    with up_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(UP_HEADERS)
        writer.writerows(
            call_to_row(chain.pinzhong, quote) for quote in chain.calls
        )

    with down_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(DOWN_HEADERS)
        writer.writerows(
            put_to_row(chain.pinzhong, quote) for quote in chain.puts
        )

    return up_path, down_path


def batch_save_all_csv(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    session: requests.Session | None = None,
    timeout: float = 30,
) -> tuple[list[tuple[Path, Path]], Path]:
    sess = session or requests.Session()
    symbol_pinzhong_list = get_all_pinzhong_lists(session=sess, timeout=timeout)

    saved: list[tuple[Path, Path]] = []
    summaries: list[ProductOpenInterest] = []

    for item in symbol_pinzhong_list:
        variety, _ = parse_pinzhong(item.pinzhong_list[0])
        summary = ProductOpenInterest(
            product=item.symbol.code,
            variety=variety,
            name=item.symbol.name,
        )

        for pinzhong in item.pinzhong_list:
            chain = get_option_data_for_symbol(
                item.symbol,
                pinzhong,
                session=sess,
                timeout=timeout,
            )
            saved.append(save_option_chain_csv(chain, output_dir=output_dir))

            call_total, put_total = sum_chain_open_interest(chain)
            summary.call_open_interest += call_total
            summary.put_open_interest += put_total

        summaries.append(summary)

    summary_path = save_open_interest_summary_csv(
        summaries,
        output_path=output_dir / SUMMARY_CSV_PATH.name,
    )
    return saved, summary_path


def main() -> None:
    saved, summary_path = batch_save_all_csv()
    print(f"已保存 {len(saved)} 组 CSV 到 {DEFAULT_OUTPUT_DIR}")
    for up_path, down_path in saved[:3]:
        print(f"{up_path.name}, {down_path.name}")
    if len(saved) > 3:
        print(f"... 共 {len(saved)} 组")
    print(f"已保存持仓量汇总到 {summary_path}")


if __name__ == "__main__":
    main()
