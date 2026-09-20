package studio.gpx.tiles.routes;

import com.onthegomap.planetiler.FeatureCollector;
import com.onthegomap.planetiler.Planetiler;
import com.onthegomap.planetiler.Profile;
import com.onthegomap.planetiler.config.Arguments;
import com.onthegomap.planetiler.reader.SourceFeature;
import com.onthegomap.planetiler.reader.osm.OsmElement;
import com.onthegomap.planetiler.reader.osm.OsmReader;
import com.onthegomap.planetiler.reader.osm.OsmRelationInfo;
import java.nio.file.Path;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/** Standalone vector overlay for OSM hiking, foot and bicycle route relations. */
public final class RoutesProfile implements Profile {

  public static final String SOURCE_NAME = "osm";
  public static final String LAYER_NAME = "routes";
  private static final Set<String> ROUTE_CLASSES = Set.of("hiking", "foot", "bicycle");
  private static final Set<String> COLORS = Set.of(
    "black", "blue", "brown", "green", "orange", "purple", "red", "yellow"
  );

  public static void main(String[] args) throws Exception {
    Arguments arguments = Arguments.fromArgsOrConfigFile(args);
    Path osmPath = arguments.inputFile(
      "osm_path",
      "filtered OSM PBF containing route relations and their referenced ways/nodes",
      Path.of("sources/routes-country.osm.pbf")
    );

    Planetiler.create(arguments)
      .setProfile(new RoutesProfile())
      .addOsmSource(SOURCE_NAME, osmPath)
      .setOutput(Path.of("output/routes.mbtiles"))
      .run();
  }

  @Override
  public List<OsmRelationInfo> preprocessOsmRelation(OsmElement.Relation relation) {
    String routeClass = relation.getString("route");
    if (routeClass == null || !ROUTE_CLASSES.contains(routeClass)) {
      return null;
    }

    return List.of(new Route(
      relation.id(),
      routeClass,
      tag(relation, "name"),
      tag(relation, "name:uk"),
      tag(relation, "name:en"),
      tag(relation, "ref"),
      tag(relation, "network"),
      tag(relation, "operator"),
      tag(relation, "description"),
      tag(relation, "description:uk"),
      tag(relation, "description:en"),
      tag(relation, "from"),
      tag(relation, "to"),
      tag(relation, "via"),
      tag(relation, "distance"),
      tag(relation, "ascent"),
      tag(relation, "descent"),
      tag(relation, "roundtrip"),
      tag(relation, "website"),
      tag(relation, "wikipedia"),
      tag(relation, "wikidata"),
      tag(relation, "state"),
      tag(relation, "osmc:symbol"),
      tag(relation, "colour"),
      routeColor(relation)
    ));
  }

  @Override
  public void processFeature(SourceFeature feature, FeatureCollector features) {
    if (!feature.canBeLine()) {
      return;
    }

    List<OsmReader.RelationMember<Route>> routes = feature.relationInfo(Route.class);
    for (var member : routes) {
      Route route = member.relation();
      features.line(LAYER_NAME)
        .setId(route.id())
        .setAttr("relation_id", route.id())
        .setAttr("class", route.routeClass())
        .setAttr("name", route.name())
        .setAttr("ref", route.ref())
        .setAttr("network", route.network())
        .setAttr("symbol", route.symbol())
        .setAttr("color", route.color())
        .setAttrWithMinzoom("name_uk", route.nameUk(), 10)
        .setAttrWithMinzoom("name_en", route.nameEn(), 10)
        .setAttrWithMinzoom("operator", route.operator(), 10)
        .setAttrWithMinzoom("description", route.description(), 10)
        .setAttrWithMinzoom("description_uk", route.descriptionUk(), 10)
        .setAttrWithMinzoom("description_en", route.descriptionEn(), 10)
        .setAttrWithMinzoom("from", route.from(), 10)
        .setAttrWithMinzoom("to", route.to(), 10)
        .setAttrWithMinzoom("via", route.via(), 10)
        .setAttrWithMinzoom("distance", route.distance(), 10)
        .setAttrWithMinzoom("ascent", route.ascent(), 10)
        .setAttrWithMinzoom("descent", route.descent(), 10)
        .setAttrWithMinzoom("roundtrip", route.roundtrip(), 10)
        .setAttrWithMinzoom("website", route.website(), 10)
        .setAttrWithMinzoom("wikipedia", route.wikipedia(), 10)
        .setAttrWithMinzoom("wikidata", route.wikidata(), 10)
        .setAttrWithMinzoom("state", route.state(), 10)
        .setAttrWithMinzoom("colour", route.colour(), 10)
        .setAttrWithMinzoom("role", emptyToNull(member.role()), 10)
        .setAttrWithMinzoom("highway", tag(feature, "highway"), 10)
        .setAttrWithMinzoom("surface", tag(feature, "surface"), 10)
        .setAttrWithMinzoom("tracktype", tag(feature, "tracktype"), 10)
        .setAttrWithMinzoom("sac_scale", tag(feature, "sac_scale"), 10)
        .setAttrWithMinzoom("trail_visibility", tag(feature, "trail_visibility"), 10)
        .setAttrWithMinzoom("mtb_scale", tag(feature, "mtb:scale"), 10)
        .setAttrWithMinzoom("smoothness", tag(feature, "smoothness"), 10)
        .setMinZoom(6)
        .setMinPixelSize(0)
        .setBufferPixels(4);
    }
  }

  @Override
  public String name() {
    return "OSM Routes";
  }

  @Override
  public String description() {
    return "Hiking, foot and bicycle route relations from OpenStreetMap";
  }

  @Override
  public String attribution() {
    return OSM_ATTRIBUTION;
  }

  @Override
  public String version() {
    return "1.0.0";
  }

  @Override
  public boolean isOverlay() {
    return true;
  }

  private static String routeColor(OsmElement.Relation relation) {
    String symbol = relation.getString("osmc:symbol");
    if (symbol != null) {
      String color = normalizeColor(symbol.split(":", 2)[0]);
      if (color != null) {
        return color;
      }
    }
    String color = normalizeColor(relation.getString("colour"));
    return color != null ? color : normalizeColor(relation.getString("ref:colour"));
  }

  private static String normalizeColor(String color) {
    if (color == null) {
      return null;
    }
    color = color.toLowerCase(Locale.ROOT);
    return COLORS.contains(color) ? color : null;
  }

  private static String tag(com.onthegomap.planetiler.reader.WithTags element, String key) {
    return emptyToNull(element.getString(key));
  }

  private static String emptyToNull(String value) {
    return value == null || value.isBlank() ? null : value;
  }

  private record Route(
    long id,
    String routeClass,
    String name,
    String nameUk,
    String nameEn,
    String ref,
    String network,
    String operator,
    String description,
    String descriptionUk,
    String descriptionEn,
    String from,
    String to,
    String via,
    String distance,
    String ascent,
    String descent,
    String roundtrip,
    String website,
    String wikipedia,
    String wikidata,
    String state,
    String symbol,
    String colour,
    String color
  ) implements OsmRelationInfo {}
}
