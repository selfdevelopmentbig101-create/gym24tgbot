"""
Progress charts as PNG images (matplotlib, no Telegram code).

Rendering is CPU work, so callers run these functions in a thread
(asyncio.to_thread) to keep the bot responsive.
"""
import io
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)

try:
    import matplotlib

    matplotlib.use("Agg")  # no screen needed; must be set before importing pyplot
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
except ImportError as error:
    # matplotlib (and Pillow, which it uses) ship native DLLs that Windows
    # Smart App Control can block. The bot still runs without charts.
    mdates = plt = None
    logger.warning("matplotlib unavailable (%s): charts are disabled", error)


class ChartsUnavailable(RuntimeError):
    """Raised when the chart library couldn't be loaded."""


def _require() -> None:
    if plt is None:
        raise ChartsUnavailable()


COLORS = ["#2b6cb0", "#dd6b20", "#38a169", "#805ad5", "#d53f8c"]


def _finish(fig, ax, title: str, ylabel: str) -> bytes:
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    fig.autofmt_xdate()
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=120)
    plt.close(fig)  # free memory: the bot renders many charts
    return buffer.getvalue()


def moving_average(values: list[float], window: int = 7) -> list[float]:
    result = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1): i + 1]
        result.append(sum(chunk) / len(chunk))
    return result


def line_chart(title: str, ylabel: str,
               series: list[tuple[str, list[datetime | date], list[float]]],
               show_average: bool = False) -> bytes:
    """One or more lines. With show_average, a moving average of the last 7 points is added."""
    _require()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for index, (label, xs, ys) in enumerate(series):
        color = COLORS[index % len(COLORS)]
        ax.plot(xs, ys, marker="o", markersize=4, linewidth=1.5, color=color, label=label,
                alpha=0.6 if show_average else 1)
        if show_average and len(ys) >= 3:
            ax.plot(xs, moving_average(ys), linewidth=2.5, color="#1a202c", label="Trend (last 7 weigh-ins)")
    if len(series) > 1 or show_average:
        ax.legend(frameon=False)
    return _finish(fig, ax, title, ylabel)


def bar_chart(title: str, ylabel: str, xs: list[date], ys: list[float]) -> bytes:
    _require()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(xs, ys, color=COLORS[0], width=0.7)
    return _finish(fig, ax, title, ylabel)
