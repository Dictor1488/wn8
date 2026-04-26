def calc_wn8(avg_damage, avg_spot, avg_frag, avg_def, avg_win_pct,
             exp_damage, exp_spot, exp_frag, exp_def, exp_win_pct):

    if exp_damage <= 0 or exp_win_pct <= 0:
        return 0

    rDAMAGE = float(avg_damage) / exp_damage
    rSPOT = (float(avg_spot) / exp_spot) if exp_spot > 0 else 0.0
    rFRAG = (float(avg_frag) / exp_frag) if exp_frag > 0 else 0.0
    rDEF = (float(avg_def) / exp_def) if exp_def > 0 else 0.0
    rWIN = float(avg_win_pct) / exp_win_pct

    rDAMAGEc = max(0.0, (rDAMAGE - 0.22) / (1 - 0.22))
    rWINc = max(0.0, (rWIN - 0.71) / (1 - 0.71))
    rFRAGc = max(0.0, min(rDAMAGEc + 0.2, (rFRAG - 0.12) / (1 - 0.12)))
    rSPOTc = max(0.0, min(rDAMAGEc + 0.1, (rSPOT - 0.38) / (1 - 0.38)))
    rDEFc = max(0.0, min(rDAMAGEc + 0.1, (rDEF - 0.10) / (1 - 0.10)))

    wn8 = (
        980.0 * rDAMAGEc
        + 210.0 * rDAMAGEc * rFRAGc
        + 155.0 * rFRAGc * rSPOTc
        + 75.0 * rDEFc * rFRAGc
        + 145.0 * min(1.8, rWINc)
    )
    return wn8


def calc_overall_wn8_from_per_tank(tank_stats, exp_table):

    total_battles = 0
    total_wins = 0
    total_damage = 0
    total_frags = 0
    total_spot = 0
    total_def = 0

    expDamage_sum = 0.0
    expSpot_sum = 0.0
    expFrag_sum = 0.0
    expDef_sum = 0.0
    expWin_sum = 0.0
    counted_battles = 0

    for tank in tank_stats:
        battles = int(tank.get('battles') or 0)
        if battles <= 0:
            continue
        tid = tank.get('tank_id')

        damage = int(tank.get('damage_dealt') or 0)
        frags = int(tank.get('frags') or 0)
        spotted = int(tank.get('spotted') or 0)
        dropped = int(tank.get('dropped_capture_points') or 0)
        wins = int(tank.get('wins') or 0)

        total_battles += battles
        total_wins += wins
        total_damage += damage
        total_frags += frags
        total_spot += spotted
        total_def += dropped

        exp = exp_table.get(int(tid)) if tid is not None else None
        if not exp:
            continue
        expDamage_sum += float(exp.get('expDamage', 0)) * battles
        expSpot_sum += float(exp.get('expSpot', 0)) * battles
        expFrag_sum += float(exp.get('expFrag', 0)) * battles
        expDef_sum += float(exp.get('expDef', 0)) * battles
        expWin_sum += float(exp.get('expWinRate', 0)) * battles
        counted_battles += battles

    if counted_battles == 0 or total_battles == 0:
        return 0, total_battles, total_wins, total_damage

    avg_damage = float(total_damage) / total_battles
    avg_spot = float(total_spot) / total_battles
    avg_frag = float(total_frags) / total_battles
    avg_def = float(total_def) / total_battles
    avg_win_pct = float(total_wins) / total_battles * 100.0

    exp_damage = expDamage_sum / counted_battles
    exp_spot = expSpot_sum / counted_battles
    exp_frag = expFrag_sum / counted_battles
    exp_def = expDef_sum / counted_battles
    exp_win = expWin_sum / counted_battles

    wn8 = calc_wn8(avg_damage, avg_spot, avg_frag, avg_def, avg_win_pct,
                   exp_damage, exp_spot, exp_frag, exp_def, exp_win)
    return int(round(wn8)), total_battles, total_wins, total_damage
