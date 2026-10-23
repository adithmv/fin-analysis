def compute(frame, window):
    rows = []
    for confirmed in range(2 * window, len(frame)):
        pivot = confirmed - window
        part = frame.iloc[pivot - window : confirmed + 1]
        for kind, column, extreme in [
            ("swing_high", "high", part.high.max()),
            ("swing_low", "low", part.low.min()),
        ]:
            value = float(frame.iloc[pivot][column])
            if value == extreme and int((part[column] == extreme).sum()) == 1:
                rows.append(
                    dict(
                        index=confirmed,
                        signal_key=kind,
                        signal_type="level",
                        direction="neutral",
                        raw_value=value,
                        description=f"Confirmed {kind.replace('_', ' ')} at {value:g}",
                        details={
                            "kind": kind,
                            "price": value,
                            "swing_ts": frame.iloc[pivot].ts.isoformat(),
                            "confirmation_bars": window,
                        },
                    )
                )
    return rows
