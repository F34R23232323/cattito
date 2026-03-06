"""
graph.py — generates a stock price line chart as a PNG buffer.
Used by the /stocks command: graph.make_graph(data, width_inches, height_inches)

data: list of (unix_timestamp, price) tuples, sorted oldest-first
Returns: io.BytesIO PNG buffer ready to pass to discord.File
"""

import io
import datetime

import matplotlib
matplotlib.use("Agg")  # non-interactive backend, required for server use
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def make_graph(data: list[tuple[int, int]], width: int = 10, height: int = 3) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(width, height))

    # Style
    fig.patch.set_facecolor("#2b2d31")   # Discord dark background
    ax.set_facecolor("#2b2d31")
    ax.tick_params(colors="#b5bac1", labelsize=9)
    ax.xaxis.label.set_color("#b5bac1")
    ax.yaxis.label.set_color("#b5bac1")
    for spine in ax.spines.values():
        spine.set_edgecolor("#3f4248")

    if not data:
        ax.text(
            0.5, 0.5, "No price history yet",
            transform=ax.transAxes,
            ha="center", va="center",
            color="#b5bac1", fontsize=12,
        )
        ax.set_xticks([])
        ax.set_yticks([])
    else:
        times  = [datetime.datetime.fromtimestamp(t) for t, _ in data]
        prices = [p for _, p in data]

        # Colour the line green if price went up, red if down
        colour = "#23a55a" if prices[-1] >= prices[0] else "#f23f43"

        ax.plot(times, prices, color=colour, linewidth=2)
        ax.fill_between(times, prices, min(prices), alpha=0.15, color=colour)

        # Grid
        ax.grid(True, color="#3f4248", linewidth=0.5, linestyle="--")
        ax.set_axisbelow(True)

        # X-axis: show readable date/time labels
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d %H:%M"))
        fig.autofmt_xdate(rotation=30, ha="right")

        # Y-axis: coin values
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v):,}"))

    plt.tight_layout(pad=0.5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf
