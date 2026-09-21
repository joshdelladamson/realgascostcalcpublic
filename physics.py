def calculate_segment_fuel(
    distance_mi: float,
    speed_mph: float,
    speed_limit_mph: float,
    grade_pct: float,
    city_mpg: float,
    highway_mpg: float
) -> tuple[float, float]:
    """
    Calculate fuel used in gallons for a route segment based on physical modeling.
    Returns (gallons_used, effective_mpg).
    """
    if distance_mi <= 0:
        return 0.0, 0.0
    if speed_mph <= 0:
        # Idle consumption could go here, but for zero distance we return 0
        return 0.0, 0.0

    # 1. Base MPG Interpolation
    # City MPG is typically achieved around 20-25 mph (stop & go average).
    # Highway MPG is achieved around 55-65 mph cruise.
    # Peak economy is often around 45-55 mph.
    if speed_mph <= 25:
        base_mpg = city_mpg
    elif speed_mph >= 60:
        base_mpg = highway_mpg
    else:
        # Linear interpolation between 25 and 60 mph
        ratio = (speed_mph - 25) / (60 - 25)
        base_mpg = city_mpg + ratio * (highway_mpg - city_mpg)

    # 2. Idle/Congestion Penalty
    # If the segment average speed is significantly below the speed limit,
    # it implies stop-and-go traffic or idling.
    if speed_limit_mph > 0 and speed_mph < (speed_limit_mph * 0.6):
        # The lower the speed relative to limit, the higher the penalty
        congestion_factor = 1.0 - (speed_mph / speed_limit_mph)
        # Reduce MPG by up to 30% for severe congestion
        base_mpg *= (1.0 - 0.3 * congestion_factor)

    # 3. Aerodynamic Penalty (High Speed)
    # Drag increases with the square of velocity.
    # We apply a penalty for speeds > 65 mph.
    if speed_mph > 65:
        # For fuel per mile, energy required scales with v^2
        v_ratio = speed_mph / 65.0
        drag_penalty = v_ratio ** 2
        base_mpg /= drag_penalty

    # 4. Grade Correction
    # Uphill requires extra work against gravity.
    # Downhill provides partial credit (engine braking, idling).
    if grade_pct > 0:
        # Rough heuristic: 1% grade = ~10% increase in fuel consumption
        grade_factor = 1.0 + (grade_pct * 0.10)
        effective_mpg = base_mpg / grade_factor
    elif grade_pct < 0:
        # Downhill gives back some energy, but engine friction limits recovery.
        # Max ~50% boost to MPG on steep downhills.
        grade_factor = 1.0 + (abs(grade_pct) * 0.05)
        effective_mpg = base_mpg * min(grade_factor, 1.5)
    else:
        effective_mpg = base_mpg

    # Sanity check floor
    effective_mpg = max(effective_mpg, 1.0)

    # 5. Output
    gallons = distance_mi / effective_mpg
    return gallons, effective_mpg

