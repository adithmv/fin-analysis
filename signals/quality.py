import pandas as pd


def compute(frame, config):
    rows = []
    q = config["quality"]

    def add(i, key, description, details):
        rows.append(
            dict(
                index=i,
                signal_key=key,
                signal_type="data_flag",
                direction="neutral",
                raw_value=None,
                description=description,
                details=details,
            )
        )

    longest = max(config["indicators"]["sma"])
    streak = 0
    for i, row in frame.iterrows():
        if i + 1 < longest:
            add(
                i,
                "short_history",
                f"Only {i + 1} candles available; longest SMA needs {longest}",
                {"available": i + 1, "required": longest},
            )
        if i:
            change = float(row.close / frame.iloc[i - 1].close - 1)
            if abs(change) * 100 > q["split_jump_threshold_percent"]:
                add(
                    i,
                    "possible_split_or_bonus",
                    "Large daily move; possible corporate action",
                    {"change_percent": change * 100},
                )
            previous = frame.iloc[i - 1].ts.tz_convert("Asia/Kolkata").date()
            current = row.ts.tz_convert("Asia/Kolkata").date()
            missing = len(
                pd.bdate_range(
                    pd.Timestamp(previous) + pd.Timedelta(days=1),
                    pd.Timestamp(current) - pd.Timedelta(days=1),
                )
            )
            if missing > q["max_missing_weekdays_in_row"]:
                add(
                    i,
                    "gap_in_data",
                    f"{missing} missing weekdays before this candle",
                    {"missing_weekdays": missing},
                )
        streak = streak + 1 if pd.notna(row.volume) and row.volume == 0 else 0
        if streak == q["zero_volume_streak_days"]:
            add(i, "zero_volume_streak", f"{streak} consecutive zero-volume sessions", {"sessions": streak})
    return rows
