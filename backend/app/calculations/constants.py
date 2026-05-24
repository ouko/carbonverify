"""IPCC and methodology constants for cookstove carbon calculations."""

from typing import Dict

# ─── IPCC Emission Factors (kg CO2e per kg fuel) ──────────────────────────────
# Source: IPCC 2006 Guidelines, Vol 2, Ch 2 (Stationary Combustion)
EMISSION_FACTORS: Dict[str, Dict[str, float]] = {
    "wood": {
        "ncv_mj_per_kg": 15.6,
        "co2ef_kg_per_gj": 112.0,   # kg CO2/TJ = 112,000 => kg CO2/GJ = 112
        "ch4ef_g_per_kg": 1.5,      # g CH4/kg fuel (Tier 1)
        "n2oef_g_per_kg": 0.15,     # g N2O/kg fuel (Tier 1)
        "co2e_factor": 1.58,        # kg CO2e per kg wood
    },
    "charcoal": {
        "ncv_mj_per_kg": 29.5,
        "co2ef_kg_per_gj": 112.0,
        "ch4ef_g_per_kg": 7.0,      # Higher CH4 from charcoal production
        "n2oef_g_per_kg": 0.20,
        "co2e_factor": 2.85,        # kg CO2e per kg charcoal
    },
    "biogas": {
        "ncv_mj_per_kg": 23.0,      # Approximate for digestate/biogas slurry equivalent
        "co2ef_kg_per_gj": 54.3,
        "ch4ef_g_per_kg": 0.5,
        "n2oef_g_per_kg": 0.05,
        "co2e_factor": 0.05,        # Very low direct emissions
    },
    "lpg": {
        "ncv_mj_per_kg": 46.0,
        "co2ef_kg_per_gj": 63.1,
        "ch4ef_g_per_kg": 0.1,
        "n2oef_g_per_kg": 0.05,
        "co2e_factor": 2.99,        # kg CO2e per kg LPG
    },
    "ethanol": {
        "ncv_mj_per_kg": 26.8,
        "co2ef_kg_per_gj": 64.8,
        "ch4ef_g_per_kg": 0.2,
        "n2oef_g_per_kg": 0.05,
        "co2e_factor": 1.61,        # kg CO2e per kg ethanol
    },
    "coal": {
        "ncv_mj_per_kg": 25.8,
        "co2ef_kg_per_gj": 94.6,
        "ch4ef_g_per_kg": 1.0,
        "n2oef_g_per_kg": 0.15,
        "co2e_factor": 2.47,
    },
    "kerosene": {
        "ncv_mj_per_kg": 43.3,
        "co2ef_kg_per_gj": 74.1,
        "ch4ef_g_per_kg": 0.1,
        "n2oef_g_per_kg": 0.05,
        "co2e_factor": 2.58,
    },
    "dung": {
        "ncv_mj_per_kg": 13.0,
        "co2ef_kg_per_gj": 117.0,
        "ch4ef_g_per_kg": 2.0,
        "n2oef_g_per_kg": 0.20,
        "co2e_factor": 1.31,
    },
}

# GWP values (IPCC AR6)
GWP_100 = {
    "co2": 1.0,
    "ch4": 27.9,   # Fossil CH4
    "ch4_bio": 27.0,  # Biogenic CH4 (non-CO2)
    "n2o": 273.0,
}

# ─── fNRB Reference Points ────────────────────────────────────────────────────
# Known fNRB values from peer-reviewed studies / GS/Verra PD documents
fNRB_REFERENCE_POINTS = {
    # (lat, lon): {"fnrb": value, "uncertainty": value, "source": "...", "year": int}
    (-1.2921, 36.8219): {"fnrb": 0.30, "uncertainty": 0.08, "source": "Kenya NRB Study 2019", "year": 2019, "country": "Kenya"},
    (6.5244, 3.3792): {"fnrb": 0.35, "uncertainty": 0.10, "source": "Nigeria MoFuSS 2020", "year": 2020, "country": "Nigeria"},
    (-6.3690, 34.8888): {"fnrb": 0.42, "uncertainty": 0.12, "source": "Tanzania Biomass Assessment 2018", "year": 2018, "country": "Tanzania"},
    (9.1450, 40.4897): {"fnrb": 0.45, "uncertainty": 0.10, "source": "Ethiopia NRB 2021", "year": 2021, "country": "Ethiopia"},
    (-13.2543, 34.3015): {"fnrb": 0.55, "uncertainty": 0.15, "source": "Malawi Forest Depletion 2017", "year": 2017, "country": "Malawi"},
    (12.6392, -8.0029): {"fnrb": 0.25, "uncertainty": 0.07, "source": "Mali Woodfuel Study 2016", "year": 2016, "country": "Mali"},
    (7.9465, -1.0232): {"fnrb": 0.28, "uncertainty": 0.08, "source": "Ghana Savanna NRB 2020", "year": 2020, "country": "Ghana"},
    (-15.3875, 28.3228): {"fnrb": 0.50, "uncertainty": 0.12, "source": "Zambia Deforestation 2019", "year": 2019, "country": "Zambia"},
    (4.1755, 73.5093): {"fnrb": 0.20, "uncertainty": 0.06, "source": "Maldives Island Study 2015", "year": 2015, "country": "Maldives"},
    (27.7172, 85.3240): {"fnrb": 0.22, "uncertainty": 0.07, "source": "Nepal Hills NRB 2018", "year": 2018, "country": "Nepal"},
    (14.0583, 108.2772): {"fnrb": 0.18, "uncertainty": 0.05, "source": "Vietnam Highlands 2020", "year": 2020, "country": "Vietnam"},
    (-19.0154, 29.1549): {"fnrb": 0.48, "uncertainty": 0.13, "source": "Zimbabwe Miombo 2017", "year": 2017, "country": "Zimbabwe"},
    (0.3476, 32.5825): {"fnrb": 0.32, "uncertainty": 0.09, "source": "Uganda NRB 2021", "year": 2021, "country": "Uganda"},
    (-18.8792, 47.5079): {"fnrb": 0.40, "uncertainty": 0.11, "source": "Madagascar Spiny Forest 2019", "year": 2019, "country": "Madagascar"},
    (11.1270, 78.6569): {"fnrb": 0.24, "uncertainty": 0.07, "source": "India Tamil Nadu 2020", "year": 2020, "country": "India"},
    (-23.4420, 29.1525): {"fnrb": 0.52, "uncertainty": 0.14, "source": "South Africa Bushveld 2018", "year": 2018, "country": "South Africa"},
    (5.6037, -0.1870): {"fnrb": 0.33, "uncertainty": 0.09, "source": "Ghana Coastal Savanna 2021", "year": 2021, "country": "Ghana"},
    (3.8480, 11.5021): {"fnrb": 0.38, "uncertainty": 0.10, "source": "Cameroon Congo Basin Edge 2019", "year": 2019, "country": "Cameroon"},
    (-1.9403, 29.8739): {"fnrb": 0.44, "uncertainty": 0.12, "source": "Rwanda Hills 2020", "year": 2020, "country": "Rwanda"},
    (17.6078, 8.0817): {"fnrb": 0.30, "uncertainty": 0.08, "source": "Niger Sahel 2018", "year": 2018, "country": "Niger"},
}

# CCP cap for cookstove projects
CCP_FNRB_CAP = 0.50

# Default fNRB when no reference data available
DEFAULT_FNRB = 0.30
DEFAULT_FNRB_UNCERTAINTY = 0.10

# ─── Methodology Constants ────────────────────────────────────────────────────

# TPDDTEC v4
TPDDTEC_MIN_THERMAL_EFFICIENCY = 0.25  # 25%
TPDDTEC_MIN_TRACKING_RATE = 0.90       # 90%

# VM0050
VM0050_USAGE_RATE_CAPS = {
    "survey_only": 0.75,
    "field_training": 0.90,
    "sums": 1.00,
}
VM0050_MIN_KPT_SAMPLE_SIZE = 30

# VMR0006
VMR0006_MAX_RETROACTIVE_YEARS = 5

# ─── Stove Performance Reference Data ─────────────────────────────────────────
# Typical thermal efficiencies by stove type
STOVE_EFFICIENCIES = {
    "traditional_three_stone": 0.10,
    "improved_biomass": 0.25,
    "rocket_stove": 0.30,
    "gasifier": 0.35,
    "lpg_stove": 0.55,
    "biogas_stove": 0.55,
    "ethanol_stove": 0.50,
    "induction": 0.80,
}

# Default household parameters
DEFAULT_HOUSEHOLD_SIZE = 5.0
DEFAULT_COOKING_DAYS_PER_YEAR = 350.0
