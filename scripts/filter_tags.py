# Osmium syntax: <object types>/<tag key>=<comma-separated values>.
# n = node
# w = way
# r = relation
# https://docs.osmcode.org/osmium/latest/osmium-tags-filter.html#filter-expressions

FILTER_TAGS_BY_TARGET = {
    "low-zoom-outdoor": (
        (
            "w/highway=tertiary,residential,unclassified,living_street,road,service,"
            "track,path,footway,cycleway,bridleway,steps,pedestrian"
        ),
    ),
    "poi": (
        "nwr/amenity=drinking_water,grave_yard,water_point",
        (
            "nwr/barrier=bar,barrier_board,block,chain,cycle_barrier,gate,hampshire_gate,"
            "horse_stile,kissing_gate,lift_gate,motorcycle_barrier,sliding_beam,sliding_gate,"
            "stile,swing_gate,turnstile,wicket_gate"
        ),
        "nwr/drinking_water=yes",
        "nwr/ford",
        "nwr/generator:source=wind",
        "nwr/historic=archaeological_site,castle,fort,memorial,monument,ruins",
        "nwr/landuse=cemetery",
        "nwr/leisure=bird_hide,nature_reserve,park",
        "nwr/man_made=water_tower,watermill,windmill",
        "nwr/natural=cave_entrance,cliff,hot_spring,peak,spring",
        "nwr/plant:source=hydro",
        "nwr/power=generator,plant",
        "nwr/shop=convenience,supermarket",
        "nwr/tourism=alpine_hut,attraction,camp_site,picnic_site,viewpoint,wilderness_hut",
        "nwr/waterway=dam,waterfall",
    ),
    "trails": ("r/route=hiking,foot,bicycle",),
}
