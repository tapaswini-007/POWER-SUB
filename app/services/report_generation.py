"""Report generation service for CSV and PDF reports with non-GUI Matplotlib charts."""

import io
from datetime import UTC, datetime
from typing import Any
from xml.sax import saxutils

import matplotlib

# Enforce non-GUI backend before importing pyplot
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.api.deps import STANDARD_LIMITATIONS
from app.utils.csv_safety import sanitize_dataframe_for_csv


def escape_markup(text: Any) -> str:
    """Escape XML/HTML characters to prevent injection into ReportLab Flowables."""
    if text is None:
        return ""
    return saxutils.escape(str(text))


def generate_energy_charts(
    df: pd.DataFrame, anomalies_records: list[dict[str, Any]]
) -> tuple[bytes, bytes]:
    """Generate in-memory PNG charts for consumption trends and entity breakdowns."""
    plt.style.use("fast")

    # 1. Timeline Chart
    fig1, ax1 = plt.subplots(figsize=(7.5, 3.2), dpi=150)
    time_df = df.copy()
    if "date" in time_df.columns and pd.api.types.is_datetime64_any_dtype(time_df["date"]):
        time_df = time_df.sort_values(by="date")
        ax1.plot(
            time_df["date"],
            time_df["energy_kwh"],
            label="Daily Consumption (kWh)",
            color="#1f77b4",
            linewidth=1.5,
            alpha=0.85,
        )

        # Plot anomalies
        anom_rows = [a for a in anomalies_records if a.get("is_anomaly")]
        if anom_rows:
            anom_df = pd.DataFrame(anom_rows)
            anom_df["date"] = pd.to_datetime(anom_df["date"], errors="coerce")
            anom_df = anom_df.dropna(subset=["date"])
            ax1.scatter(
                anom_df["date"],
                anom_df["energy_kwh"],
                color="#d62728",
                label="Flagged Anomaly (Possible Waste)",
                s=40,
                zorder=5,
                edgecolors="black",
                linewidth=0.5,
            )

        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig1.autofmt_xdate(rotation=30)
    else:
        ax1.plot(time_df["energy_kwh"].values, label="Consumption (kWh)", color="#1f77b4")

    ax1.set_title(
        "Energy Consumption Over Time with Flagged Outliers",
        fontsize=11,
        fontweight="bold",
    )
    ax1.set_ylabel("Energy (kWh)", fontsize=9)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper right", fontsize=8)
    fig1.tight_layout()

    buf1 = io.BytesIO()
    fig1.savefig(buf1, format="png")
    plt.close(fig1)
    buf1.seek(0)
    img1_bytes = buf1.getvalue()

    # 2. Entity Breakdown Chart
    fig2, ax2 = plt.subplots(figsize=(7.5, 2.8), dpi=150)
    group_col = "building" if "building" in df.columns and df["building"].notna().any() else None
    if not group_col and "department" in df.columns and df["department"].notna().any():
        group_col = "department"

    if group_col:
        grp = df.groupby(group_col)["energy_kwh"].sum().sort_values(ascending=False).head(8)
        colors_list = ["#2ca02c", "#ff7f0e", "#1f77b4", "#9467bd", "#8c564b"][: len(grp)]
        bars = ax2.bar(
            grp.index.astype(str),
            grp.values,
            color=colors_list,
            alpha=0.85,
            edgecolor="gray",
        )
        ax2.set_title(
            f"Cumulative Consumption by {group_col.capitalize()}",
            fontsize=11,
            fontweight="bold",
        )
        ax2.set_ylabel("Total kWh", fontsize=9)
        ax2.grid(True, axis="y", linestyle="--", alpha=0.5)
        for bar in bars:
            height = bar.get_height()
            ax2.annotate(
                f"{height:,.0f}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 2),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=7,
            )
    else:
        ax2.text(
            0.5,
            0.5,
            "No categorical building/department breakdown available",
            ha="center",
            va="center",
        )
        ax2.set_axis_off()

    fig2.tight_layout()
    buf2 = io.BytesIO()
    fig2.savefig(buf2, format="png")
    plt.close(fig2)
    buf2.seek(0)
    img2_bytes = buf2.getvalue()

    return img1_bytes, img2_bytes


def generate_csv_report(
    dataset: dict[str, Any],
    df: pd.DataFrame,
    analysis: dict[str, Any],
    anomalies: dict[str, Any],
    recommendations: list[dict[str, Any]],
) -> bytes:
    """Generate comprehensive, formula-injection neutralized CSV report with UTF-8 BOM."""
    # Combine core records with anomaly annotations
    anom_map = {
        a["row_id"]: (
            a.get("is_anomaly", False),
            a.get("anomaly_score", 0.0),
            a.get("severity", "normal"),
        )
        for a in anomalies.get("anomalies", [])
    }

    report_df = df.copy()
    report_df["is_flagged_anomaly"] = report_df["row_id"].map(
        lambda rid: anom_map.get(rid, (False, 0.0, "normal"))[0]
    )
    report_df["anomaly_score"] = report_df["row_id"].map(
        lambda rid: anom_map.get(rid, (False, 0.0, "normal"))[1]
    )
    report_df["anomaly_severity"] = report_df["row_id"].map(
        lambda rid: anom_map.get(rid, (False, 0.0, "normal"))[2]
    )

    if "date" in report_df.columns and pd.api.types.is_datetime64_any_dtype(report_df["date"]):
        report_df["date"] = report_df["date"].dt.strftime("%Y-%m-%d")

    # Apply Formula-Injection neutralization
    safe_df = sanitize_dataframe_for_csv(report_df)

    # Export with UTF-8 BOM so Excel decodes accents and formatting properly
    csv_str = safe_df.to_csv(index=False)
    return ("\ufeff" + csv_str).encode("utf-8")


def generate_pdf_report(
    dataset: dict[str, Any],
    df: pd.DataFrame,
    analysis: dict[str, Any],
    anomalies: dict[str, Any],
    recommendations: list[dict[str, Any]],
) -> bytes:
    """Generate a publication-grade PDF report using ReportLab and Matplotlib Agg."""
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1e3d59"),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#555555"),
        spaceAfter=12,
    )
    section_h2 = ParagraphStyle(
        "SectionH2",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#17252a"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#222222"),
    )
    notice_style = ParagraphStyle(
        "NoticeText",
        parent=styles["Normal"],
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#777777"),
    )

    story = []

    # Title & Header
    story.append(
        Paragraph("<b>POWER-SUB: Energy Waste Detection & Analysis Report</b>", title_style)
    )
    now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    dataset_name = escape_markup(dataset.get("display_filename", "Dataset"))
    story.append(
        Paragraph(
            f"<b>Dataset:</b> {dataset_name} &nbsp;|&nbsp; "
            f"<b>Dataset ID:</b> {dataset['id'][:8]}... &nbsp;|&nbsp; "
            f"<b>Generated:</b> {now_str}",
            subtitle_style,
        )
    )
    story.append(
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1e3d59"), spaceAfter=10)
    )

    # Executive Summary Table
    stats = analysis["statistics"]
    cost_info = analysis["cost_statistics"]
    baseline_info = analysis["baseline_comparison"]
    anom_summary = anomalies["summary"]

    summary_data = [
        [
            Paragraph("<b>Metric</b>", body_style),
            Paragraph("<b>Value</b>", body_style),
            Paragraph("<b>Metric</b>", body_style),
            Paragraph("<b>Value</b>", body_style),
        ],
        [
            Paragraph("Total Records", body_style),
            Paragraph(str(len(df)), body_style),
            Paragraph("Total Consumption", body_style),
            Paragraph(f"{stats['total_kwh']:,.1f} kWh", body_style),
        ],
        [
            Paragraph("Daily Mean", body_style),
            Paragraph(f"{stats['mean_kwh']:,.1f} kWh", body_style),
            Paragraph("Daily Median", body_style),
            Paragraph(f"{stats['median_kwh']:,.1f} kWh", body_style),
        ],
        [
            Paragraph("Baseline Used", body_style),
            Paragraph(escape_markup(baseline_info["baseline_method_used"]), body_style),
            Paragraph("Baseline Value", body_style),
            Paragraph(f"{baseline_info['baseline_kwh']:,.1f} kWh", body_style),
        ],
        [
            Paragraph("Flagged Anomalies", body_style),
            Paragraph(
                f"<b>{anom_summary['anomalies_flagged']}</b> ({anom_summary['anomaly_percentage']}%)",
                body_style,
            ),
            Paragraph("Derived Cost / kWh", body_style),
            Paragraph(
                f"${cost_info['derived_cost_per_kwh']:.4f}"
                if cost_info.get("derived_cost_per_kwh")
                else "N/A (No cost data)",
                body_style,
            ),
        ],
    ]

    t_summary = Table(summary_data, colWidths=[110, 150, 110, 150])
    t_summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f1f5")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(t_summary)
    story.append(Spacer(1, 10))

    # Visualizations
    chart1_bytes, chart2_bytes = generate_energy_charts(df, anomalies.get("anomalies", []))
    story.append(Paragraph("<b>Consumption Timeline & Anomaly Distribution</b>", section_h2))
    img1 = Image(io.BytesIO(chart1_bytes), width=6.8 * inch, height=2.9 * inch)
    story.append(img1)
    story.append(Spacer(1, 6))

    if chart2_bytes:
        img2 = Image(io.BytesIO(chart2_bytes), width=6.8 * inch, height=2.5 * inch)
        story.append(img2)
        story.append(Spacer(1, 10))

    # Recommendations Section
    story.append(Paragraph("<b>Intelligent Efficiency Recommendations</b>", section_h2))
    if recommendations:
        for idx, rec in enumerate(recommendations[:5], 1):
            prio_color = (
                "#b30000"
                if rec["priority"] == "high"
                else ("#d97706" if rec["priority"] == "medium" else "#2563eb")
            )
            rec_text = (
                f"<b>{idx}. {escape_markup(rec['issue_detected'])}</b> "
                f"<font color='{prio_color}'><b>[{rec['priority'].upper()} PRIORITY]</b></font><br/>"
                f"<b>Action:</b> {escape_markup(rec['suggested_action'])}<br/>"
                f"<b>Evidence:</b> {escape_markup(rec['explanation'])}"
            )
            if rec.get("estimated_savings") and rec["estimated_savings"].get(
                "potential_cost_savings"
            ):
                savings = rec["estimated_savings"]
                rec_text += (
                    f"<br/><b>Estimated Savings:</b> "
                    f"Up to ~{savings['potential_kwh_reduction']:,.1f} kWh (${savings['potential_cost_savings']:,.2f}) "
                    f"<i>({escape_markup(savings['confidence_label'])})</i>"
                )
            story.append(Paragraph(rec_text, body_style))
            story.append(Spacer(1, 6))
    else:
        story.append(
            Paragraph(
                "No actionable anomalous patterns detected based on current evidence.",
                body_style,
            )
        )

    story.append(Spacer(1, 10))

    # Core Research Limitations Notice
    story.append(
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#aaaaaa"), spaceAfter=6)
    )
    story.append(Paragraph("<b>MANDATORY RESEARCH LIMITATIONS:</b>", notice_style))
    story.append(Paragraph(escape_markup(STANDARD_LIMITATIONS), notice_style))

    doc.build(story)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()
