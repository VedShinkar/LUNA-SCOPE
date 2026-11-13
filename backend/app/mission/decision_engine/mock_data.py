"""
LUNA-SCOPE Synthetic Test Data

These values are created only for testing
the Mission Decision Engine.

They are NOT actual NASA measurements.
"""

LUNAR_SITES = {

    "SHACKLETON_RIM": {

        "site_name": "Shackleton Rim",

        "sunlight_hours": 110,

        "earth_visibility_hours": 130,

        "solar_energy_wh": 750,

        "slope_deg": 8,

        "terrain_hazard_score": 0.3,

        "data_status": "SYNTHETIC_EXAMPLE"

    },

    "MALAPERT_MASSIF": {

        "site_name": "Malapert Massif",

        "sunlight_hours": 95,

        "earth_visibility_hours": 140,

        "solar_energy_wh": 680,

        "slope_deg": 6,

        "terrain_hazard_score": 0.2,

        "data_status": "SYNTHETIC_EXAMPLE"

    },

    "DE_GERLACHE_RIM": {

        "site_name": "de Gerlache Rim",

        "sunlight_hours": 120,

        "earth_visibility_hours": 100,

        "solar_energy_wh": 800,

        "slope_deg": 12,

        "terrain_hazard_score": 0.6,

        "data_status": "SYNTHETIC_EXAMPLE"

    }

}


def get_lunar_site(site_id):

    """
    Retrieve lunar site information.
    """

    if site_id not in LUNAR_SITES:

        raise ValueError(
            f"Lunar site '{site_id}' was not found."
        )

    return LUNAR_SITES[site_id]


if __name__ == "__main__":

    print("LUNA-SCOPE Synthetic Site Data")
    print("--------------------------------")

    for site_id, site in LUNAR_SITES.items():

        print("\nSite:", site["site_name"])

        print("Sunlight:", site["sunlight_hours"], "hours")

        print("Earth Visibility:",
              site["earth_visibility_hours"], "hours")

        print("Solar Energy:",
              site["solar_energy_wh"], "Wh")

        print("Data Status:", site["data_status"])