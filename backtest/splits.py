import numpy as np


def samples(length, fraction):
    if not 0 < fraction < 1 or length < 2:
        raise ValueError("Need two or more bars and a split fraction between zero and one")
    cut = max(1, min(length - 1, int(length * fraction)))
    return {"all": (0, length), "in_sample": (0, cut), "out_of_sample": (cut, length)}


def exclusion_mask(frame, signals, config):
    mask = np.zeros(len(frame), dtype=bool)
    indexes = {ts: i for i, ts in enumerate(frame.ts)}
    windows = []
    import pandas as pd

    for row in signals:
        i = indexes.get(pd.Timestamp(row["ts"]))
        if i is None:
            continue
        if row["signal_key"] == "short_history":
            mask[i] = True
        if row["signal_key"] == "possible_split_or_bonus":
            width = config["exclusions"]["around_split_flag_days"]
            a, b = max(0, i - width), min(len(frame), i + width + 1)
            mask[a:b] = True
            windows.append([a, b])
        if row["signal_key"] == "gap_in_data":
            mask[max(0, i - 1) : i + 1] = True
            windows.append([max(0, i - 1), i + 1])
    return mask, windows
