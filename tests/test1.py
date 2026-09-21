from risk_enginev2 import (
    calculate_risk_score,
    determine_risk_level,
)


def test_case(name, evidence, hydrology, expected):

    score = calculate_risk_score(
        evidence,
        hydrology
    )

    level = determine_risk_level(
        score,
        evidence,
        hydrology
    )

    status = "PASS" if level == expected else "FAIL"

    print(
        f"{status:<6} | "
        f"{name:<25} | "
        f"Score: {score:6.2f} | "
        f"Risk: {level:<8} | "
        f"Expected: {expected}"
    )


# =========================================================
# HEADER
# =========================================================

print("=" * 90)
print("PRAVAH - RISK ENGINE V2 VALIDATION")
print("=" * 90)

print()

print(
    f"{'STATUS':<6} | "
    f"{'TEST':<25} | "
    f"{'SCORE':<13} | "
    f"{'RESULT':<8} | "
    f"EXPECTED"
)

print("-" * 90)


# =========================================================
# 1. NORMAL CONDITIONS
# =========================================================

test_case(
    "Normal conditions",

    {
        "rainfall": "LOW",
        "runoff": "VERY_LOW",
        "river": "NORMAL",
        "antecedent_rainfall": "VERY_LOW"
    },

    {
        "hydrological_signal": 0.10,
        "hydrological_state": "NORMAL"
    },

    "LOW"
)


# =========================================================
# 2. RIVER NEAR WARNING
# =========================================================

test_case(
    "River near warning",

    {
        "rainfall": "LOW",
        "runoff": "VERY_LOW",
        "river": "NEAR_WARNING",
        "antecedent_rainfall": "LOW"
    },

    {
        "hydrological_signal": 0.30,
        "hydrological_state": "NEAR_WARNING"
    },

    "WATCH"
)


# =========================================================
# 3. RIVER NEAR DANGER
# =========================================================

test_case(
    "River near danger",

    {
        "rainfall": "LOW",
        "runoff": "VERY_LOW",
        "river": "NEAR_DANGER",
        "antecedent_rainfall": "LOW"
    },

    {
        "hydrological_signal": 0.55,
        "hydrological_state": "NEAR_DANGER"
    },

    "WATCH"
)


# =========================================================
# 4. WARNING THRESHOLD CROSSED
# =========================================================

test_case(
    "Warning threshold crossed",

    {
        "rainfall": "MODERATE",
        "runoff": "MODERATE",
        "river": "WARNING",
        "antecedent_rainfall": "MODERATE"
    },

    {
        "hydrological_signal": 0.75,
        "hydrological_state": "WARNING"
    },

    "WARNING"
)


# =========================================================
# 5. DANGER THRESHOLD CROSSED
# =========================================================

test_case(
    "Danger threshold crossed",

    {
        "rainfall": "HIGH",
        "runoff": "HIGH",
        "river": "DANGER",
        "antecedent_rainfall": "HIGH"
    },

    {
        "hydrological_signal": 1.0,
        "hydrological_state": "DANGER"
    },

    "CRITICAL"
)


# =========================================================
# 6. HIGH RAINFALL WITHOUT RIVER DATA
# =========================================================

test_case(
    "High rainfall, no river",

    {
        "rainfall": "VERY_HIGH",
        "runoff": "HIGH",
        "river": "NO_DATA",
        "antecedent_rainfall": "HIGH"
    },

    {
        "hydrological_signal": 0.50,
        "hydrological_state": "MODERATE_HYDROLOGICAL_PRESSURE"
    },

    "WARNING"
)


# =========================================================
# 7. NO RIVER DATA + LOW RAINFALL
# =========================================================

test_case(
    "No river data",

    {
        "rainfall": "LOW",
        "runoff": "VERY_LOW",
        "river": "NO_DATA",
        "antecedent_rainfall": "LOW"
    },

    {
        "hydrological_signal": 0.03,
        "hydrological_state": "NORMAL"
    },

    "LOW"
)


# =========================================================
# FOOTER
# =========================================================

print()

print("=" * 90)
print("VALIDATION COMPLETE")
print("=" * 90)