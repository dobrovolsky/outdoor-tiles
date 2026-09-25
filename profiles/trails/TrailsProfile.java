package tiles.trails;

import com.onthegomap.planetiler.FeatureCollector;
import com.onthegomap.planetiler.FeatureMerge;
import com.onthegomap.planetiler.Planetiler;
import com.onthegomap.planetiler.Profile;
import com.onthegomap.planetiler.VectorTile;
import com.onthegomap.planetiler.config.Arguments;
import com.onthegomap.planetiler.geo.GeometryException;
import com.onthegomap.planetiler.reader.SourceFeature;
import com.onthegomap.planetiler.reader.osm.OsmElement;
import com.onthegomap.planetiler.reader.osm.OsmReader;
import com.onthegomap.planetiler.reader.osm.OsmRelationInfo;
import com.onthegomap.planetiler.util.Translations;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentSkipListSet;

/** Standalone vector overlay for OSM hiking, foot and bicycle route relations. */
public final class TrailsProfile implements Profile {

  public static final String SOURCE_NAME = "osm";
  public static final String LAYER_NAME = "trails";
  public static final String LABEL_LAYER_NAME = "trail_labels";
  private static final Set<String> ROUTE_CLASSES = Set.of("hiking", "foot", "bicycle");
  private static final Set<String> LOW_ZOOM_NETWORKS = Set.of("iwn", "nwn", "icn", "ncn");
  private static final Set<String> COLORS = Set.of(
    "black", "blue", "brown", "green", "orange", "purple", "red", "yellow"
  );
  // Keep this in sync with https://github.com/openmaptiles/openmaptiles/blob/master/openmaptiles.yaml
  private static final List<String> DEFAULT_LANGUAGES = List.of(
    "af", "am", "ar", "az", "be", "bg", "bn", "br", "bs", "ca", "co", "cs", "cy", "da", "de", "el",
    "en", "eo", "es", "et", "eu", "fa", "fi", "fr", "fy", "ga", "gd", "he", "hi", "hr", "hu", "hy",
    "id", "is", "it", "ja", "ja_kana", "ja_rm", "ja-Latn", "ja-Hira", "ka", "kk", "kn", "ko", "ko-Latn",
    "ku", "la", "lb", "lt", "lv", "mk", "mt", "ml", "nl", "no", "oc", "pa", "pnb", "pl", "pt", "rm",
    "ro", "ru", "sk", "sl", "sq", "sr", "sr-Latn", "sv", "ta", "te", "th", "tok", "tr", "uk", "ur",
    "vi", "zh", "zh-Hant", "zh-Hans"
  );
  private final Translations translations;
  private final Set<String> symbols = new ConcurrentSkipListSet<>();

  public TrailsProfile(Translations translations) {
    this.translations = translations;
  }

  public static void main(String[] args) throws Exception {
    Arguments arguments = Arguments.fromArgsOrConfigFile(args);
    Path osmPath = arguments.inputFile(
      "osm_path",
      "filtered OSM PBF containing route relations and their referenced ways/nodes",
      Path.of("sources/trails-country.osm.pbf")
    );
    Path shieldsPath = arguments.file(
      "shields_path",
      "output text file containing unique OSMC symbols",
      Path.of("tmp/shields.txt")
    );
    Planetiler runner = Planetiler.create(arguments)
      .setDefaultLanguages(DEFAULT_LANGUAGES);
    TrailsProfile profile = new TrailsProfile(runner.translations());

    runner
      .setProfile(profile)
      .addOsmSource(SOURCE_NAME, osmPath)
      .setOutput(Path.of("output/trails.mbtiles"))
      .run();
    Files.createDirectories(shieldsPath.toAbsolutePath().getParent());
    Files.write(shieldsPath, profile.symbols);
  }

  @Override
  public List<OsmRelationInfo> preprocessOsmRelation(OsmElement.Relation relation) {
    String routeClass = relation.getString("route");
    if (routeClass == null || !ROUTE_CLASSES.contains(routeClass)) {
      return null;
    }

    String symbol = tag(relation, "osmc:symbol");
    if (symbol != null && !"no".equals(symbol)) {
      symbols.add(symbol);
    }

    return List.of(new Route(
      relation.id(),
      routeClass,
      tag(relation, "name"),
      Map.copyOf(translations.getTranslations(relation.tags())),
      tag(relation, "ref"),
      tag(relation, "network"),
      tag(relation, "operator"),
      tag(relation, "description"),
      localizedTags(relation, "description"),
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
      symbol,
      tag(relation, "colour"),
      routeColor(relation)
    ));
  }

  @Override
  public void processFeature(SourceFeature feature, FeatureCollector features) {
    if (!feature.canBeLine()) {
      return;
    }

    List<OsmReader.RelationMember<Route>> trails = feature.relationInfo(Route.class);
    for (var member : trails) {
      Route route = member.relation();
      FeatureCollector.Feature trail = features.line(LAYER_NAME)
        .setId(route.id())
        .setAttr("relation_id", route.id())
        .setAttr("class", route.routeClass())
        .setAttr("name", route.name())
        .setAttr("ref", route.ref())
        .setAttr("network", route.network())
        .setAttr("symbol", route.symbol())
        .setAttr("color", route.color())
        .setAttrWithMinzoom("operator", route.operator(), 10)
        .setAttrWithMinzoom("description", route.description(), 10)
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
        .setMinZoom(route.network() != null && LOW_ZOOM_NETWORKS.contains(route.network()) ? 6 : 10)
        .setMinPixelSize(0)
        .setBufferPixels(4);
      putAttrsWithMinzoom(trail, route.localizedNames(), 10);
      putAttrsWithMinzoom(trail, route.localizedDescriptions(), 10);

      if (route.symbol() != null || route.ref() != null || route.name() != null || !route.localizedNames().isEmpty()) {
        FeatureCollector.Feature label = features.line(LABEL_LAYER_NAME)
          .setId(route.id())
          .setAttr("relation_id", route.id())
          .setAttr("class", route.routeClass())
          .setAttr("name", route.name())
          .setAttr("ref", route.ref())
          .setAttr("symbol", route.symbol())
          .setAttr("color", route.color())
          .setMinZoom(11)
          .setMinPixelSize(0)
          .setBufferPixels(4);
        route.localizedNames().forEach(label::setAttr);
      }
    }
  }

  @Override
  public List<VectorTile.Feature> postProcessLayerFeatures(String layer, int zoom,
      List<VectorTile.Feature> items) throws GeometryException {
    return LABEL_LAYER_NAME.equals(layer) ? FeatureMerge.mergeLineStrings(items, 0, 0, 4) : items;
  }

  @Override
  public String name() {
    return "OSM Trails";
  }

  @Override
  public String description() {
    return "Hiking, foot and bicycle trail relations from OpenStreetMap";
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

  private Map<String, Object> localizedTags(OsmElement.Relation relation, String key) {
    String prefix = key + ":";
    Map<String, Object> result = new HashMap<>();
    for (var entry : relation.tags().entrySet()) {
      String tag = entry.getKey();
      String value = entry.getValue() instanceof String string ? emptyToNull(string) : null;
      if (tag.startsWith(prefix) && translations.careAboutLanguage(tag.substring(prefix.length())) && value != null) {
        result.put(tag, value);
      }
    }
    return Map.copyOf(result);
  }

  private static void putAttrsWithMinzoom(FeatureCollector.Feature feature, Map<String, Object> attrs, int minzoom) {
    attrs.forEach((key, value) -> feature.setAttrWithMinzoom(key, value, minzoom));
  }

  private static String emptyToNull(String value) {
    return value == null || value.isBlank() ? null : value;
  }

  private record Route(
    long id,
    String routeClass,
    String name,
    Map<String, Object> localizedNames,
    String ref,
    String network,
    String operator,
    String description,
    Map<String, Object> localizedDescriptions,
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
