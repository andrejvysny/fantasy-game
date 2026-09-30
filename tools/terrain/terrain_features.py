"""Hand-authored terrain features, traced from ref/topo.png.

All coordinates are pixels in the 1254x1254 topo reference (x right, y down = south).
Distances/widths are meters. Edit here, then re-run build.sh.
"""

REF_SIZE = 1254  # topo reference width/height in px

# Waterfalls / rapids: a line across the channel (extend it over the banks so the
# level solver cannot route around it). Crossing it upstream adds `drop` meters.
FALLS = [
    {"name": "Fall_Canyon_Top", "pts": [(1025, 82), (1125, 82)], "drop": 30.0},
    {"name": "Fall_Canyon_Mid", "pts": [(985, 262), (1065, 262)], "drop": 14.0},
    {"name": "Fall_Canyon_Low", "pts": [(990, 338), (1070, 338)], "drop": 6.0},
    {"name": "Fall_East_Scarp", "pts": [(1095, 690), (1170, 718)], "drop": 26.0},
    {"name": "Rapids_West_Branch", "pts": [(958, 375), (962, 430)], "drop": 6.0},
]

# Level connectors: dry links that tell the level solver how disconnected water
# bodies drain (the topo leaves them isolated). Not carved.
CONNECTORS = [
    {"name": "Link_MiddleRiver_SELake", "pts": [(725, 770), (755, 755), (780, 768), (805, 792)]},
    {"name": "Link_SELake_MainRiver", "pts": [(860, 845), (855, 900), (850, 935)]},
    {"name": "Link_EastPool_SELake", "pts": [(1060, 830), (1000, 835), (945, 830)]},
]

# Cliffs: polyline along the middle of the drawn cliff face. The high side is detected
# automatically (override with "side": 1 / -1). `w` = half-width of the re-profiled band,
# `drop` = extra height added to the high side, fading out over `back` m behind the rim,
# `steps` = terrace risers in the face, `taper` = fade length past the polyline ends.
CLIFFS = [
    {"name": "Cliff_NW_Escarpment", "drop": 35, "back": 220, "w": 24, "steps": 2,
     "pts": [(60, 252), (150, 238), (200, 228), (228, 185), (245, 135), (290, 115), (345, 75), (382, 42)]},
    {"name": "Cliff_W_Escarpment", "drop": 32, "back": 200, "w": 24, "steps": 2,
     "pts": [(62, 262), (72, 330), (85, 400), (120, 440), (175, 490), (235, 540)]},
    {"name": "Cliff_NE_Canyon_WestRim", "drop": 38, "back": 220, "w": 30, "steps": 3,
     "pts": [(875, 145), (955, 130), (1005, 115), (1058, 98)]},
    {"name": "Cliff_NE_Canyon_EastRim", "drop": 40, "back": 260, "w": 28, "steps": 3,
     "pts": [(1094, 112), (1130, 132), (1170, 160), (1192, 205), (1200, 260), (1210, 320),
             (1218, 380), (1225, 440), (1222, 500), (1215, 545)]},
    {"name": "Cliff_NE_Shoulder_South", "drop": 28, "back": 160, "w": 24, "steps": 2,
     "pts": [(850, 285), (900, 302), (950, 320), (995, 338)]},
    {"name": "Cliff_NE_Shoulder_West", "drop": 18, "back": 120, "w": 18, "steps": 2,
     "pts": [(882, 150), (912, 195), (945, 238)]},
    {"name": "Cliff_NE_Ledge_South", "drop": 16, "back": 90, "w": 20, "steps": 2,
     "pts": [(1045, 305), (1100, 325), (1150, 338), (1178, 332)]},
    {"name": "Cliff_Butte_Scarp", "drop": 42, "back": 230, "w": 40, "steps": 3,
     "pts": [(912, 575), (965, 638), (1020, 698), (1075, 742), (1112, 738)]},
    {"name": "Cliff_E_Plateau_West", "drop": 34, "back": 220, "w": 24, "steps": 2,
     "pts": [(1152, 735), (1148, 800), (1140, 870), (1110, 915)]},
    {"name": "Cliff_E_Plateau_South", "drop": 26, "back": 200, "w": 28, "steps": 2,
     "pts": [(1068, 948), (1112, 1000), (1160, 1040), (1254, 1082)]},
    {"name": "Cliff_SE_Block_West", "drop": 26, "back": 180, "w": 28, "steps": 2,
     "pts": [(1032, 1105), (1080, 1170), (1130, 1230), (1150, 1254)]},
]

# Labelled probe points, printed after generation to sanity-check levels.
PROBES = {
    "upper_lake": (480, 255), "junction": (750, 490), "canyon_above_top_fall": (1078, 40),
    "canyon_pool": (1040, 210), "canyon_basin": (1045, 385), "east_river_above_fall": (1195, 640),
    "east_fall_pool": (1075, 815), "se_lake": (890, 820), "west_source": (160, 510),
    "river_mouth": (820, 1040), "central_hill": (480, 470), "butte_top": (990, 610),
    "ne_plateau": (1230, 120), "e_plateau": (1215, 850), "sw_plateau": (330, 1000),
}
