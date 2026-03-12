"""Add NREL measure descriptions to the cost lookup JSON."""

import json
from pathlib import Path

COST_LOOKUP_PATH = Path(__file__).parent.parent / "backend" / "app" / "data" / "upgrade_cost_lookup.json"

COMSTOCK_DESCRIPTIONS = {
    "1": "Replaces existing packaged rooftop units with variable-speed heat pump RTUs with electric resistance backup heating. Provides efficient heating and cooling with variable airflow for improved part-load performance.",
    "2": "Replaces existing packaged rooftop units with variable-speed heat pump RTUs that retain the original heating fuel as backup. The heat pump serves as the primary heating source with fossil fuel backup for extreme cold conditions.",
    "3": "Replaces existing packaged rooftop units with variable-speed heat pump RTUs with electric backup and adds energy recovery ventilators (ERVs) to precondition outdoor air using exhaust air energy.",
    "4": "Replaces existing packaged rooftop units with standard-performance heat pump RTUs (lower efficiency than variable-speed) with electric resistance backup heating.",
    "5": "Replaces existing packaged rooftop units with standard-performance heat pump RTUs sized using laboratory test data, with electric resistance backup heating. Performance curves derived from controlled lab measurements.",
    "6": "Combines a standard-performance heat pump RTU replacement with electric backup and addition of roof insulation to meet current code requirements. Reduces both HVAC and envelope losses.",
    "7": "Combines a standard-performance heat pump RTU replacement with electric backup and installation of new high-performance windows. Addresses both HVAC efficiency and solar/thermal gains through glazing.",
    "8": "Replaces existing rooftop units with standard-performance heat pump RTUs with electric backup, configured with a 32°F minimum compressor lockout temperature to limit heat pump operation in very cold conditions.",
    "9": "Replaces existing rooftop units with standard-performance heat pump RTUs with electric backup, adding a 2°F thermostat setback during unoccupied heating periods to reduce energy use.",
    "10": "Replaces existing rooftop units with high-performance heat pump RTUs meeting the DOE Commercial HVAC Challenge specifications, with electric resistance backup heating. Targets best-in-class efficiency levels.",
    "11": "Upgrades existing rooftop units with advanced features including variable-speed fans, improved economizer controls, and optimized staging to improve part-load efficiency without full equipment replacement.",
    "12": "Replaces existing HVAC systems with variable refrigerant flow (VRF) systems paired with a dedicated outdoor air system (DOAS) for ventilation. VRF provides zonal heating and cooling with heat recovery capability.",
    "13": "Replaces existing HVAC systems with variable refrigerant flow (VRF) systems sized with a 25% upsizing allowance to ensure adequate capacity in extreme conditions and account for sizing uncertainty.",
    "14": "Replaces existing HVAC systems with ductless heat pump mini-splits served by a dedicated outdoor air system (DOAS) for ventilation. Provides high-efficiency zonal heating and cooling without ductwork losses.",
    "15": "Replaces existing hot water boilers with air-to-water heat pump boilers with electric resistance backup. Serves hydronic heating systems with significantly improved efficiency over fossil fuel boilers.",
    "16": "Replaces existing hot water boilers with air-to-water heat pump boilers that retain natural gas backup for peak heating loads. The heat pump operates as the primary heating source.",
    "17": "Replaces existing gas-fired boilers with condensing natural gas boilers achieving 95%+ thermal efficiency by recovering latent heat from flue gases.",
    "18": "Replaces existing boilers with electric resistance boilers for buildings transitioning to all-electric heating. Provides 100% conversion efficiency but higher operating costs than heat pump alternatives.",
    "19": "Adds air-side economizers to existing air handling units to provide free cooling using outdoor air when ambient conditions are favorable, reducing mechanical cooling energy.",
    "20": "Installs CO2-based demand control ventilation (DCV) sensors and controls on air handling units to modulate outdoor air intake based on actual occupancy, reducing ventilation energy during partial occupancy.",
    "21": "Adds energy recovery ventilators (ERVs) to existing air handling units to transfer heat and moisture between exhaust and incoming outdoor air streams, reducing heating and cooling loads from ventilation.",
    "22": "Upgrades existing rooftop unit controls with advanced strategies including integrated economizer operation, demand-based ventilation, optimal start/stop, and supply air temperature reset.",
    "23": "Implements automated shutdown of air handling units during unoccupied periods with optimized morning warm-up/cool-down sequences, reducing fan energy and conditioning loads outside operating hours.",
    "24": "Adds static pressure reset controls to multizone variable air volume (VAV) systems, allowing supply fan speed to modulate based on zone demand rather than maintaining constant duct pressure.",
    "25": "Implements nighttime and weekend thermostat setbacks to reduce heating and cooling energy during unoccupied hours. Heating setpoints are lowered and cooling setpoints raised during setback periods.",
    "26": "Replaces constant-speed hydronic pumps with variable frequency drive (VFD) equipped pumps that modulate flow based on system demand, significantly reducing pumping energy at part-load conditions.",
    "27": "Theoretical measure representing ideal HVAC performance with zero distribution losses, used as a benchmarking reference for maximum achievable HVAC efficiency.",
    "28": "Replaces existing hydronic heating and cooling systems with water-to-water geothermal heat pumps using vertical closed-loop ground heat exchangers. Serves existing hydronic distribution piping.",
    "29": "Replaces existing HVAC systems with packaged water-to-air geothermal heat pump units connected to vertical closed-loop ground heat exchangers. Each unit provides direct air heating and cooling.",
    "30": "Replaces existing HVAC systems with console-style water-to-air geothermal heat pump units connected to vertical closed-loop ground heat exchangers. Console units are wall-mounted for perimeter zone conditioning.",
    "31": "Replaces existing chillers with high-efficiency chillers meeting current ASHRAE 90.1 minimum efficiency requirements, improving cooling plant performance.",
    "32": "Implements thermostat-based demand flexibility to shed HVAC load during daily building peak periods by adjusting temperature setpoints, reducing the building's peak demand.",
    "33": "Implements thermostat-based demand flexibility to shift HVAC load away from daily building peak periods through pre-conditioning (pre-cooling or pre-heating) before peak hours.",
    "34": "Implements lighting-based demand flexibility by shedding (dimming or switching off) non-essential lighting during daily building peak demand periods.",
    "35": "Implements lighting-based demand flexibility by shedding non-essential lighting during periods of high grid greenhouse gas emissions to reduce the building's carbon impact.",
    "36": "Implements thermostat-based demand flexibility to shed HVAC load during grid-level peak demand periods by adjusting temperature setpoints to reduce strain on the electric grid.",
    "37": "Implements lighting-based demand flexibility by shedding non-essential lighting during grid-level peak demand periods to reduce strain on the electric grid.",
    "38": "Implements plug load demand flexibility using GEB Gem controls to shed non-essential plug loads during grid-level peak demand periods.",
    "39": "Implements lighting demand flexibility using GEB Gem controls to shed non-essential lighting during grid-level peak demand periods with optimized dimming strategies.",
    "40": "Implements thermostat demand flexibility using GEB Gem controls to shed HVAC load during grid-level peak demand periods with optimized setpoint adjustment strategies.",
    "41": "Implements GEB Gem-controlled pre-heating load shifting to move heating energy consumption ahead of grid peak periods, reducing demand during peak hours.",
    "42": "Implements GEB Gem-controlled pre-cooling load shifting to move cooling energy consumption ahead of grid peak periods, reducing demand during peak hours.",
    "43": "Retrofits all applicable interior and exterior lighting fixtures to LED technology, reducing lighting energy consumption by 30-60% compared to fluorescent and HID fixtures.",
    "44": "Adds advanced lighting controls including occupancy sensors, daylight harvesting, and scheduling to reduce lighting energy in spaces that are unoccupied or have sufficient natural light.",
    "45": "Replaces gas-fired commercial kitchen equipment (ovens, ranges, fryers, griddles) with high-efficiency electric equivalents including induction cooktops and electric convection ovens.",
    "46": "Installs rooftop photovoltaic solar panels covering 40% of available roof area to generate on-site renewable electricity, offsetting grid electricity consumption.",
    "47": "Installs rooftop photovoltaic solar panels covering 40% of available roof area paired with on-site battery storage to generate and store renewable electricity for peak demand reduction.",
    "48": "Adds continuous exterior wall insulation to meet current energy code requirements, reducing thermal bridging and conductive heat transfer through the building envelope.",
    "49": "Adds or upgrades roof insulation to meet current energy code requirements, reducing heat gain in summer and heat loss in winter through the roof assembly.",
    "50": "Installs secondary window panels (interior storm windows) over existing windows to reduce air leakage and improve thermal resistance without full window replacement.",
    "51": "Applies low-emissivity window film to existing glazing to reduce solar heat gain while maintaining visible light transmission, lowering cooling loads.",
    "52": "Replaces existing windows with new high-performance windows featuring low-E coatings, argon fill, and improved frames to reduce both conductive losses and solar heat gain.",
    "53": "Upgrades the complete building envelope (walls, roof, windows, and air sealing) to meet current energy code minimum requirements.",
    "54": "Package combining wall insulation, roof insulation, and new window replacements to comprehensively upgrade the building envelope thermal performance.",
    "55": "Package combining LED lighting retrofit with variable-speed heat pump RTU replacement (or heat pump boilers for hydronic systems) for integrated HVAC and lighting efficiency improvements.",
    "56": "Package combining LED lighting retrofit with standard-performance heat pump RTU replacement for integrated HVAC and lighting efficiency improvements at moderate cost.",
    "57": "Comprehensive package combining full envelope upgrades (wall insulation, roof insulation, new windows) with LED lighting and variable-speed heat pump RTU or heat pump boiler replacement.",
    "58": "Package combining variable-speed heat pump RTU or heat pump boiler replacement with air-side economizers, demand control ventilation, and energy recovery for comprehensive HVAC system optimization.",
    "59": "Package installing geothermal heat pumps (hydronic, packaged, or console type as appropriate) to replace existing HVAC systems with ground-source heating and cooling.",
    "60": "Demand flexibility package combining lighting and thermostat control strategies to shed load during grid-level peak demand periods.",
    "61": "Demand flexibility package combining lighting and thermostat load shedding for daily building peak reduction with rooftop photovoltaic solar panel installation.",
    "62": "Demand flexibility package combining lighting and thermostat control strategies to shed load during daily building peak demand periods.",
    "63": "Comprehensive package combining full envelope upgrades (wall insulation, roof insulation, new windows) with geothermal heat pump system replacement.",
    "64": "Comprehensive package combining full envelope upgrades, geothermal heat pump system replacement, and LED lighting retrofit for deep energy savings.",
    "65": "Package combining rooftop photovoltaic solar panels at 40% roof coverage with roof insulation upgrades for combined on-site generation and envelope improvement.",
}

RESSTOCK_DESCRIPTIONS = {
    "1": "Replaces existing furnace with a high-efficiency 95% AFUE natural gas furnace for all dwelling units served by ducted forced-air distribution systems.",
    "2": "Replaces existing furnace with a high-efficiency 95% AFUE furnace for homes using propane or fuel oil, applicable to ducted forced-air systems.",
    "3": "Upgrades boilers, furnaces, and air conditioners to minimum federal efficiency standards effective circa 2025, representing code-minimum baseline equipment replacement.",
    "4": "Installs a cold climate ducted air source heat pump (ccASHP) meeting NEEP Cold Climate specification with detailed lab-measured performance data, providing efficient heating down to low ambient temperatures with electric backup.",
    "5": "Installs a dual-fuel heating system combining an air source heat pump for primary heating with an existing gas furnace as backup for extreme cold conditions, optimizing efficiency across all outdoor temperatures.",
    "6": "Installs a single-speed geothermal (ground source) heat pump with thermally enhanced grout and high-conductivity ground loop piping for efficient heating and cooling using stable ground temperatures.",
    "7": "Installs a dual-speed geothermal (ground source) heat pump with thermally enhanced grout and high-conductivity ground loop piping, offering improved part-load efficiency over single-speed models.",
    "8": "Installs a variable-speed geothermal (ground source) heat pump with thermally enhanced grout and high-conductivity ground loop piping, providing the highest part-load efficiency and precise comfort control.",
    "9": "Replaces existing water heater with a heat pump water heater (HPWH) that uses refrigerant-based heat extraction from surrounding air to heat water at 2-3x the efficiency of electric resistance units.",
    "10": "Replaces existing water heater with a high-efficiency natural gas tankless (on-demand) water heater that heats water only when needed, eliminating standby losses from storage tanks.",
    "11": "Reduces building air infiltration through targeted sealing of air leakage pathways including gaps around penetrations, joints, and framing connections to reduce uncontrolled air exchange.",
    "12": "Adds blown-in or batt insulation to the attic floor of homes with unfinished attic spaces, reducing heat transfer through the ceiling assembly to unconditioned attic space.",
    "13": "Seals duct leakage points and adds insulation to exposed ductwork in unconditioned spaces, reducing distribution losses from the forced-air HVAC system.",
    "14": "Injects loose-fill insulation into existing wall cavities through small drilled holes combined with air sealing, improving thermal resistance of wood-framed walls without removing interior or exterior finishes.",
    "15": "Envelope package combining air sealing, attic floor insulation for unfinished attics, and duct sealing and insulation to address the most common residential envelope deficiencies.",
    "16": "Comprehensive envelope package combining air sealing, attic floor insulation, duct sealing and insulation, and drill-and-fill wall cavity insulation for thorough building shell improvement.",
    "17": "Replaces existing windows with ENERGY STAR certified windows featuring low-E coatings, insulated frames, and gas fills meeting current program efficiency requirements for the applicable climate zone.",
    "18": "Comprehensive package combining a dual-speed geothermal heat pump with thermally enhanced ground loop, air sealing, attic floor insulation, and duct sealing for deep energy retrofits.",
    "19": "Models household adoption of an electric vehicle charged with Level 1 (120V, ~1.4 kW) home charging, adding EV electricity consumption to the dwelling's energy profile.",
    "20": "Models household adoption of an electric vehicle charged with Level 2 (240V, ~7.7 kW) home charging, adding EV electricity consumption to the dwelling's energy profile.",
    "21": "Models household adoption of a high-efficiency electric vehicle (lower kWh/mile) charged with Level 2 (240V) home charging, representing best-in-class EV efficiency.",
    "22": "Models electric vehicle adoption with Level 2 home charging and demand-flexible charging controls that shift charging to off-peak grid periods to reduce peak demand impacts.",
    "23": "Models high-efficiency electric vehicle adoption with Level 2 home charging and demand-flexible charging controls that shift charging to off-peak grid periods.",
    "24": "Implements HVAC demand flexibility by shedding load during on-peak periods with a 2°F thermostat offset (raising cooling setpoint or lowering heating setpoint) to reduce peak electricity demand.",
    "25": "Implements HVAC demand flexibility by pre-conditioning the home (pre-cooling or pre-heating) with a 2°F offset during a 4-hour window before peak periods, then allowing temperature to drift during peak.",
    "26": "Implements HVAC demand flexibility by shedding load during on-peak periods with a 4°F thermostat offset for more aggressive peak demand reduction compared to the 2°F variant.",
    "27": "Implements HVAC demand flexibility by pre-conditioning the home with a 4°F offset during a 4-hour window before peak periods, then allowing temperature to drift during peak for greater load shifting.",
    "28": "Implements HVAC demand flexibility by pre-conditioning the home with a 2°F offset during a shorter 1-hour window before peak periods, providing moderate load shifting with minimal pre-peak energy increase.",
    "29": "Performs general air sealing to reduce building infiltration rates, targeting accessible air leakage pathways throughout the dwelling envelope.",
    "30": "Combines general air sealing with attic floor insulation and duct sealing and insulation for a cost-effective envelope improvement package addressing major infiltration and insulation deficiencies.",
    "31": "Comprehensive package combining a dual-speed geothermal heat pump with thermally enhanced ground loop, general air sealing, attic floor insulation, and duct sealing for deep energy retrofits.",
    "32": "Comprehensive package combining a variable-speed geothermal heat pump with thermally enhanced ground loop, general air sealing, attic floor insulation, and duct sealing for maximum energy savings.",
}


def main():
    with open(COST_LOOKUP_PATH) as f:
        data = json.load(f)

    added = 0

    for uid, desc in COMSTOCK_DESCRIPTIONS.items():
        if uid in data["comstock"]:
            data["comstock"][uid]["description"] = desc
            added += 1
        else:
            print(f"WARNING: ComStock upgrade {uid} not found in JSON")

    for uid, desc in RESSTOCK_DESCRIPTIONS.items():
        if uid in data["resstock"]:
            data["resstock"][uid]["description"] = desc
            added += 1
        else:
            print(f"WARNING: ResStock upgrade {uid} not found in JSON")

    with open(COST_LOOKUP_PATH, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    print(f"Added {added} descriptions ({len(COMSTOCK_DESCRIPTIONS)} ComStock + {len(RESSTOCK_DESCRIPTIONS)} ResStock)")


if __name__ == "__main__":
    main()
