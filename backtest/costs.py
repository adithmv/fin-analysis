def rates(config):
    fee = config["costs"]["fees_pct_per_side"] / 100
    slip = config["costs"]["slippage_pct_per_side"] / 100
    if not 0 <= fee < 1 or not 0 <= slip < 1:
        raise ValueError("Fees and slippage must be percentages in [0,100)")
    return fee, slip


def net_return(entry, exit, config, direction="bullish"):
    fee, slip = rates(config)
    gross = exit / entry - 1
    net = (exit * (1 - slip) * (1 - fee)) / (entry * (1 + slip) * (1 + fee)) - 1
    # Costs must penalize bearish evidence too, never become a reward on sign flip.
    return net if direction == "bullish" else -gross - (gross - net)
