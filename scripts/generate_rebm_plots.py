"""
Generate REBM dose-response plots from the latest data in robotaste_soli_1904_data.db.

Produces 9 plots:
  - 6 dose-response plots (cold/roomtemp × sweetness/bitterness/saltiness)
  - 3 protocol-overlay plots (both protocols overlaid, per attribute)

Usage: python scripts/generate_rebm_plots.py
"""

import os
import sqlite3
from collections import defaultdict

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "robotaste.db")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "logs", "analysis_graphs")

# ── Palette & style ───────────────────────────────────────────────────────────
BLUE        = "#3D5A99"
BLUE_LIGHT  = "#A8B8D8"
MAROON      = "#7B2D3E"
MAROON_LIGHT = "#C9A0A8"
BG          = "#F8F9FC"
GRID_COLOR  = "#DDE1EC"
TITLE_COLOR = "#2D3A5C"
AXIS_COLOR  = "#4A5568"

TITLE_SIZE  = 22
AXIS_SIZE   = 16
TICK_SIZE   = 14
LEGEND_SIZE = 14
SEC_SIZE    = 13   # secondary axis label size

INTENSITY_LABELS = {1: "Not at all", 3: "Light", 5: "Moderate", 7: "Strong", 9: "Extremely strong"}


def fmt_conc(val: float) -> str:
    if val == 0:
        return "0"
    if val < 0.1:
        return f"{val:.3f}"   # 0.040, 0.090
    return f"{val:.2f}"       # 0.18, 0.36, 0.50


def load_data(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT
            pl.name AS protocol_name,
            CAST(json_extract(sam.ingredient_concentration, '$.RebM') AS REAL) AS conc_mM,
            sam.sample_temperature_c,
            CAST(json_extract(sam.questionnaire_answer, '$.sweetness')  AS REAL) AS sweetness,
            CAST(json_extract(sam.questionnaire_answer, '$.bitterness') AS REAL) AS bitterness,
            CAST(json_extract(sam.questionnaire_answer, '$.saltiness')  AS REAL) AS saltiness,
            s.session_code
        FROM samples sam
        JOIN sessions s ON sam.session_id = s.session_id
        LEFT JOIN protocol_library pl ON s.protocol_id = pl.protocol_id
        WHERE sam.deleted_at IS NULL
          AND s.deleted_at IS NULL
          AND sam.questionnaire_answer IS NOT NULL
        ORDER BY pl.name, sam.sample_temperature_c, conc_mM
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def aggregate(data_points: list[dict], attribute: str) -> list[tuple]:
    """Return list of (conc, mean, sem, n) sorted by conc."""
    by_conc: dict = defaultdict(list)
    for dp in data_points:
        val = dp.get(attribute)
        if val is not None:
            by_conc[dp["conc_mM"]].append(float(val))
    result = []
    for conc in sorted(by_conc):
        vals = by_conc[conc]
        n = len(vals)
        mean = float(np.mean(vals))
        sem = float(np.std(vals, ddof=1) / np.sqrt(n)) if n > 1 else 0.0
        result.append((conc, mean, sem, n))
    return result


def _style_main_ax(ax: plt.Axes, concs: list[float]) -> None:
    ax.set_facecolor(BG)
    margin = max(concs) * 0.06
    ax.set_xlim(-margin, max(concs) + margin * 1.5)
    ax.set_ylim(1, 9)
    ax.set_yticks(range(1, 10))
    ax.set_xticks(concs)
    ax.set_xticklabels([fmt_conc(c) for c in concs], fontsize=TICK_SIZE)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%g"))
    ax.tick_params(axis="y", labelsize=TICK_SIZE)
    ax.grid(True, axis="y", color=GRID_COLOR, linestyle="--", linewidth=0.8, alpha=0.9)
    ax.grid(True, axis="x", color=GRID_COLOR, linestyle="--", linewidth=0.8, alpha=0.9)
    for spine in ax.spines.values():
        spine.set_color(GRID_COLOR)
    ax.spines["top"].set_visible(False)


def _add_secondary_axis(ax: plt.Axes) -> plt.Axes:
    """Mirror y-axis on the right with intensity scale labels."""
    ax2 = ax.twinx()
    ax2.set_ylim(1, 9)
    ax2.set_yticks(list(INTENSITY_LABELS.keys()))
    ax2.set_yticklabels(list(INTENSITY_LABELS.values()), fontsize=SEC_SIZE, color=AXIS_COLOR)
    ax2.tick_params(axis="y", length=4, pad=6, color=GRID_COLOR)
    for spine in ax2.spines.values():
        spine.set_visible(False)
    ax2.spines["right"].set_visible(True)
    ax2.spines["right"].set_color(GRID_COLOR)
    return ax2


def plot_dose_response(
    protocol_name: str,
    data_points: list[dict],
    attribute: str,
    attr_label: str,
    out_path: str,
) -> None:
    agg = aggregate(data_points, attribute)
    concs  = [x[0] for x in agg]
    means  = np.array([x[1] for x in agg])
    sems   = np.array([x[2] for x in agg])

    n_subjects = len({dp["session_code"] for dp in data_points})
    temps = [dp["sample_temperature_c"] for dp in data_points if dp["sample_temperature_c"] is not None]
    mean_temp = float(np.mean(temps)) if temps else None
    temp_str = f"{mean_temp:.1f}°C" if mean_temp is not None else "?"

    fig, ax = plt.subplots(figsize=(11, 6.5))
    fig.patch.set_facecolor(BG)

    ax.fill_between(concs, means - sems, means + sems, color=BLUE_LIGHT, alpha=0.5, label="±SEM band")
    ax.plot(
        concs, means, "o-", color=BLUE, linewidth=2.5, markersize=8,
        label=f"Mean {attr_label.lower()} (participants n={n_subjects}, mean temp={temp_str})",
    )

    _style_main_ax(ax, concs)
    _add_secondary_axis(ax)

    ax.set_xlabel("RebM concentration (mM)", fontsize=AXIS_SIZE, color=AXIS_COLOR, labelpad=10)
    ax.set_ylabel(f"{attr_label} score (1–9 scale)", fontsize=AXIS_SIZE, color=AXIS_COLOR, labelpad=10)
    ax.legend(fontsize=LEGEND_SIZE, framealpha=0.9, loc="upper left")
    ax.set_title(
        f"{protocol_name}\nMean {attr_label} by RebM Concentration",
        fontsize=TITLE_SIZE, fontweight="bold", color=TITLE_COLOR, pad=16,
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  Saved: {os.path.basename(out_path)}")


def plot_overlay(
    protocol_data_map: dict,   # {protocol_name: [data_points]}
    attribute: str,
    attr_label: str,
    out_path: str,
) -> None:
    palette = [
        (MAROON, MAROON_LIGHT),
        (BLUE,   BLUE_LIGHT),
    ]

    fig, ax = plt.subplots(figsize=(11, 6.5))
    fig.patch.set_facecolor(BG)

    all_concs: set = set()

    for i, (proto_name, data_points) in enumerate(protocol_data_map.items()):
        agg = aggregate(data_points, attribute)
        concs  = [x[0] for x in agg]
        means  = np.array([x[1] for x in agg])
        sems   = np.array([x[2] for x in agg])
        all_concs.update(concs)

        n_subjects = len({dp["session_code"] for dp in data_points})
        temps = [dp["sample_temperature_c"] for dp in data_points if dp["sample_temperature_c"] is not None]
        mean_temp = float(np.mean(temps)) if temps else None
        temp_str = f"{mean_temp:.1f}°C" if mean_temp is not None else "?"

        line_color, fill_color = palette[i % len(palette)]
        ax.fill_between(concs, means - sems, means + sems, color=fill_color, alpha=0.35)
        ax.plot(
            concs, means, "o-", color=line_color, linewidth=2.5, markersize=8,
            label=f"{proto_name} (participants n={n_subjects}, mean temp={temp_str})",
        )

    sorted_concs = sorted(all_concs)
    _style_main_ax(ax, sorted_concs)
    _add_secondary_axis(ax)

    ax.set_xlabel("RebM concentration (mM)", fontsize=AXIS_SIZE, color=AXIS_COLOR, labelpad=10)
    ax.set_ylabel(f"{attr_label} score (1–9 scale)", fontsize=AXIS_SIZE, color=AXIS_COLOR, labelpad=10)
    ax.legend(fontsize=LEGEND_SIZE, framealpha=0.9, loc="upper left")
    ax.set_title(
        f"{attr_label} Dose-Response Comparison Across Protocols\nMean lines with ±SEM shading",
        fontsize=TITLE_SIZE, fontweight="bold", color=TITLE_COLOR, pad=16,
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  Saved: {os.path.basename(out_path)}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    data = load_data(DB_PATH)
    print(f"Loaded {len(data)} samples from DB.")

    by_protocol: dict = defaultdict(list)
    for dp in data:
        by_protocol[dp["protocol_name"]].append(dp)

    cold_data     = by_protocol["RebM Dose-Response Cold"]
    roomtemp_data = by_protocol["RebM Dose-Response RoomTemp"]
    print(f"Cold samples: {len(cold_data)} | RoomTemp samples: {len(roomtemp_data)}")

    attributes = [
        ("sweetness",  "Sweetness"),
        ("bitterness", "Bitterness"),
        ("saltiness",  "Saltiness"),
    ]

    print("\nGenerating dose-response plots...")
    for attr, label in attributes:
        for proto_name, proto_data, temp_tag in [
            ("RebM Dose-Response Cold",    cold_data,     "cold"),
            ("RebM Dose-Response RoomTemp", roomtemp_data, "roomtemp"),
        ]:
            fname = f"rebm_dose_response_{temp_tag}_{attr}_mean_sem_analysis_hub_style.png"
            plot_dose_response(proto_name, proto_data, attr, label, os.path.join(OUT_DIR, fname))

    print("\nGenerating overlay plots...")
    overlay_map = {
        "RebM Dose-Response RoomTemp": roomtemp_data,
        "RebM Dose-Response Cold":     cold_data,
    }
    for attr, label in attributes:
        fname = f"rebm_protocols_overlay_{attr}_mean_sem_analysis_hub_style.png"
        plot_overlay(overlay_map, attr, label, os.path.join(OUT_DIR, fname))

    print("\nDone. All 9 plots saved to", OUT_DIR)


if __name__ == "__main__":
    main()
