"""Evidence-driven energy waste recommendation engine.

Adheres strictly to core research principles:
- Anomaly ≠ waste (all findings are possible waste).
- No invented tariffs or fabricated savings figures.
- Estimated savings computed only when substantiated by dataset cost or user tariff.
"""

from typing import Any

import pandas as pd

from app.api.deps import STANDARD_LIMITATIONS
from app.core.errors import BadRequestError


def generate_recommendations(
    df: pd.DataFrame,
    tariff_per_kwh: float | None = None,
    quality_summary: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Analyze consumption patterns and produce grounded, evidence-based recommendations."""
    if df.empty or "energy_kwh" not in df.columns:
        return []

    if tariff_per_kwh is not None and tariff_per_kwh <= 0:
        raise BadRequestError("When provided, 'tariff_per_kwh' must be greater than 0.")

    recommendations: list[dict[str, Any]] = []

    # Derive unit cost strictly from dataset if available, otherwise check user tariff
    derived_cost_per_kwh: float | None = None
    cost_source = None

    if "cost" in df.columns and df["cost"].notna().any():
        total_kwh = float(df["energy_kwh"].sum())
        total_cost = float(df["cost"].dropna().sum())
        if total_kwh > 0 and total_cost > 0:
            derived_cost_per_kwh = total_cost / total_kwh
            cost_source = "dataset_reported_cost"

    if derived_cost_per_kwh is None and tariff_per_kwh is not None:
        derived_cost_per_kwh = tariff_per_kwh
        cost_source = "user_provided_tariff"

    total_records = len(df)
    overall_mean_kwh = float(df["energy_kwh"].mean())

    # Evidence level based on sample size and missing data
    if total_records >= 60:
        base_evidence = "high"
    elif total_records >= 25:
        base_evidence = "medium"
    else:
        base_evidence = "low"

    def compute_potential_savings(excess_kwh: float) -> dict[str, Any] | None:
        if excess_kwh <= 0:
            return None
        if derived_cost_per_kwh is not None:
            potential_financial = round(excess_kwh * derived_cost_per_kwh, 2)
            return {
                "potential_kwh_reduction": round(excess_kwh, 2),
                "potential_cost_savings": potential_financial,
                "unit": "USD",
                "cost_source": cost_source,
                "confidence_label": "potential, not guaranteed",
                "note": (
                    f"Calculated as {excess_kwh:.1f} excess kWh multiplied by {cost_source} "
                    f"(${derived_cost_per_kwh:.4f}/kWh). Requires field validation."
                ),
            }
        else:
            return {
                "potential_kwh_reduction": round(excess_kwh, 2),
                "potential_cost_savings": None,
                "unit": None,
                "cost_source": "none",
                "confidence_label": "potential, not guaranteed",
                "note": (
                    "Financial savings cannot be calculated without cost data. "
                    "Supply 'tariff_per_kwh' or upload records with cost column."
                ),
            }

    # -------------------------------------------------------------
    # RULE 1: Off-Hours / Zero Operating Hours Consumption
    # -------------------------------------------------------------
    if "operating_hours" in df.columns and df["operating_hours"].notna().any():
        zero_hours_mask = (df["operating_hours"] == 0) & (df["energy_kwh"] > 0)
        zero_hour_records = df[zero_hours_mask]

        if len(zero_hour_records) >= 2:
            off_hours_kwh = float(zero_hour_records["energy_kwh"].sum())
            mean_off_hours = float(zero_hour_records["energy_kwh"].mean())

            # Excess is consumption during off-hours above expected baseline leakage (assumed 20% standby)
            excess_kwh = max(0.0, off_hours_kwh * 0.70)
            savings = compute_potential_savings(excess_kwh)

            measurements = [
                {
                    "metric": "zero_operating_hours_days",
                    "value": float(len(zero_hour_records)),
                    "unit": "days",
                    "comparison_baseline": 0.0,
                },
                {
                    "metric": "total_off_hours_consumption",
                    "value": round(off_hours_kwh, 2),
                    "unit": "kWh",
                    "comparison_baseline": 0.0,
                },
                {
                    "metric": "average_daily_off_hours_draw",
                    "value": round(mean_off_hours, 2),
                    "unit": "kWh/day",
                    "comparison_baseline": round(overall_mean_kwh, 2),
                },
            ]

            recommendations.append(
                {
                    "id": "REC-OFFHOURS-001",
                    "issue_detected": "Significant energy consumption detected during zero-operating-hour periods",
                    "supporting_measurements": measurements,
                    "suggested_action": (
                        "Implement automated building management system (BMS) setback schedules or "
                        "smart relay isolation to eliminate non-essential baseload draw during off-hours."
                    ),
                    "priority": "high"
                    if off_hours_kwh > (0.15 * df["energy_kwh"].sum())
                    else "medium",
                    "estimated_savings": savings,
                    "evidence_level": base_evidence,
                    "explanation": (
                        f"Detected {len(zero_hour_records)} days where equipment or facility was recorded "
                        f"with 0 operating hours but drew a total of {off_hours_kwh:.1f} kWh."
                    ),
                    "required_additional_data": [
                        "Submeter telemetry for lighting vs HVAC baseload",
                        "Security and critical refrigeration baseline draw specifications",
                    ],
                    "limitations": STANDARD_LIMITATIONS,
                }
            )

    # -------------------------------------------------------------
    # RULE 2: Sustained Consumption Above Historical Baseline
    # -------------------------------------------------------------
    consecutive_high_count = 0
    max_consecutive = 0
    total_consecutive_excess = 0.0

    for val in df["energy_kwh"]:
        if val > (overall_mean_kwh * 1.15):
            consecutive_high_count += 1
            total_consecutive_excess += val - overall_mean_kwh
            max_consecutive = max(max_consecutive, consecutive_high_count)
        else:
            consecutive_high_count = 0

    if max_consecutive >= 3:
        savings = compute_potential_savings(total_consecutive_excess)
        measurements = [
            {
                "metric": "longest_sustained_high_consumption_run",
                "value": float(max_consecutive),
                "unit": "consecutive_periods",
                "comparison_baseline": 1.0,
            },
            {
                "metric": "cumulative_excess_over_mean",
                "value": round(total_consecutive_excess, 2),
                "unit": "kWh",
                "comparison_baseline": 0.0,
            },
        ]

        recommendations.append(
            {
                "id": "REC-SUSTAINED-002",
                "issue_detected": "Sustained multi-period consumption exceeding 115% of historical baseline",
                "supporting_measurements": measurements,
                "suggested_action": (
                    "Inspect cooling/heating valves, thermostat sensor calibration, or production "
                    "scheduling to verify whether sustained elevation reflects legitimate operational demand."
                ),
                "priority": "high" if max_consecutive >= 5 else "medium",
                "estimated_savings": savings,
                "evidence_level": base_evidence,
                "explanation": (
                    f"Consumption remained persistently elevated above the baseline for {max_consecutive} "
                    f"consecutive periods, accumulating {total_consecutive_excess:.1f} excess kWh."
                ),
                "required_additional_data": [
                    "Production logs matching the elevated period dates",
                    "Weather degree-day data during peak days",
                ],
                "limitations": STANDARD_LIMITATIONS,
            }
        )

    # -------------------------------------------------------------
    # RULE 3: Disproportionate Consumption by Top Entity
    # -------------------------------------------------------------
    for group_col, group_name in [
        ("building", "Building"),
        ("department", "Department"),
        ("equipment", "Equipment"),
    ]:
        if group_col in df.columns and df[group_col].nunique() > 1:
            totals = df.groupby(group_col)["energy_kwh"].sum()
            total_sum = float(totals.sum())
            if total_sum > 0:
                top_entity = str(totals.idxmax())
                top_val = float(totals.max())
                top_pct = round((top_val / total_sum) * 100.0, 1)

                if top_pct >= 45.0:
                    measurements = [
                        {
                            "metric": f"{group_col}_consumption_share",
                            "value": top_pct,
                            "unit": "percent",
                            "comparison_baseline": round(100.0 / df[group_col].nunique(), 1),
                        },
                        {
                            "metric": f"{group_col}_total_consumption",
                            "value": round(top_val, 2),
                            "unit": "kWh",
                            "comparison_baseline": round(total_sum / df[group_col].nunique(), 2),
                        },
                    ]

                    recommendations.append(
                        {
                            "id": f"REC-LOADSHARE-{group_col.upper()}-003",
                            "issue_detected": f"Disproportionate load share: {group_name} '{top_entity}' accounts for {top_pct}% of total facility energy",
                            "supporting_measurements": measurements,
                            "suggested_action": (
                                f"Conduct focused energy audit and sub-metering breakdown specifically for "
                                f"{group_name.lower()} '{top_entity}' to target high-impact efficiency retrofits."
                            ),
                            "priority": "medium",
                            "estimated_savings": None,
                            "evidence_level": base_evidence,
                            "explanation": (
                                f"{group_name} '{top_entity}' consumes {top_val:.1f} kWh ({top_pct}% of the facility total), "
                                f"making it the highest-leverage candidate for conservation measures."
                            ),
                            "required_additional_data": [
                                f"Sub-circuit electrical metering for {top_entity}",
                                "Asset age and manufacturer nameplate efficiency ratings",
                            ],
                            "limitations": STANDARD_LIMITATIONS,
                        }
                    )
                    break

    # -------------------------------------------------------------
    # RULE 4: Data Quality and Telemetry Gaps
    # -------------------------------------------------------------
    if quality_summary:
        missing_dict = quality_summary.get("missing_values_per_column", {})
        total_accepted = quality_summary.get("accepted_rows", len(df))

        high_missing = [
            col
            for col, count in missing_dict.items()
            if col in ("operating_hours", "temperature", "cost") and count > (0.30 * total_accepted)
        ]

        if high_missing:
            recommendations.append(
                {
                    "id": "REC-DATA-QUALITY-004",
                    "issue_detected": f"Significant data gaps in critical operational columns: {', '.join(high_missing)}",
                    "supporting_measurements": [
                        {
                            "metric": f"missing_{col}_rows",
                            "value": float(missing_dict[col]),
                            "unit": "rows",
                            "comparison_baseline": 0.0,
                        }
                        for col in high_missing
                    ],
                    "suggested_action": (
                        "Improve meter data logging and telemetry ingestion to capture operating hours "
                        "and environmental temperatures. Full data completeness is necessary for causal waste attribution."
                    ),
                    "priority": "low",
                    "estimated_savings": None,
                    "evidence_level": "high",
                    "explanation": (
                        f"Over 30% of records lack data for {', '.join(high_missing)}, which limits the "
                        f"precision of weather-normalized baselines and operational shift analysis."
                    ),
                    "required_additional_data": [
                        f"Integration with local BMS or IoT sensors for {', '.join(high_missing)}"
                    ],
                    "limitations": STANDARD_LIMITATIONS,
                }
            )

    return recommendations
