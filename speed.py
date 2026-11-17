#!/usr/bin/env python3
"""Замер скорости скачивания: 10 последовательных полных запросов к одному адресу."""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REQUESTS = 10
CHUNK = 64 * 1024
MIB = 1024 * 1024
MBIT = 1_000_000


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Скачивает адрес 10 раз подряд, дожидается полного ответа "
            "и печатает среднее время, объём и скорость."
        )
    )
    parser.add_argument(
        "url",
        help="Абсолютный http(s)-адрес, например тяжёлой картинки",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60,
        metavar="СЕК",
        help="Лимит ожидания одного запроса в секундах (по умолчанию 60)",
    )
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("timeout должен быть больше нуля")
    parsed = urllib.parse.urlparse(args.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        parser.error("нужен абсолютный адрес со схемой http или https")
    return args


def fetch(url: str, timeout: float) -> tuple[int, int, float]:
    """Возвращает (код ответа, байты тела, секунды до полной загрузки)."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "download-speed/1.0",
            "Accept-Encoding": "identity",
            "Cache-Control": "no-cache",
        },
        method="GET",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = response.status
        total = 0
        while True:
            chunk = response.read(CHUNK)
            if not chunk:
                break
            total += len(chunk)
        elapsed = time.perf_counter() - started
    return status, total, elapsed


def format_report(
    url: str,
    rows: list[tuple[int, int, float]],
) -> str:
    total_bytes = sum(size for _, size, _ in rows)
    total_seconds = sum(elapsed for _, _, elapsed in rows)
    average = total_seconds / len(rows)
    mib = total_bytes / MIB

    lines = [
        f"Адрес: {url}",
        f"Запросов: {len(rows)}, последовательно. Каждый раз читается всё тело ответа.",
        "",
        f"{'#':>3}   {'код':>4}   {'время, с':>10}   {'байт':>12}",
    ]
    for index, (status, size, elapsed) in enumerate(rows, start=1):
        lines.append(f"{index:>3}   {status:>4}   {elapsed:>10.3f}   {size:>12}")

    lines.extend(
        [
            "",
            f"Среднее время запроса: {average:.3f} с",
            f"Общее время:           {total_seconds:.3f} с",
            f"Общий объём:           {mib:.2f} МиБ ({total_bytes} байт)",
        ]
    )
    if total_seconds > 0 and total_bytes > 0:
        mbit_s = (total_bytes * 8) / total_seconds / MBIT
        mib_s = total_bytes / total_seconds / MIB
        lines.append(f"Скорость:              {mbit_s:.2f} Мбит/с ({mib_s:.2f} МиБ/с)")
    else:
        lines.append("Скорость:              0 Мбит/с (0 МиБ/с)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    rows: list[tuple[int, int, float]] = []
    for number in range(1, REQUESTS + 1):
        try:
            status, size, elapsed = fetch(args.url, args.timeout)
        except urllib.error.HTTPError as exc:
            print(
                f"Запрос {number} из {REQUESTS} завершился с кодом {exc.code}: {exc.reason}",
                file=sys.stderr,
            )
            return 1
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            print(
                f"Запрос {number} из {REQUESTS} не удался: {reason}",
                file=sys.stderr,
            )
            return 1
        rows.append((status, size, elapsed))
        print(
            f"[{number}/{REQUESTS}] {status}  {elapsed:.3f} с  {size} байт",
            flush=True,
        )

    print()
    print(format_report(args.url, rows))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nПрервано.", file=sys.stderr)
        raise SystemExit(130)
