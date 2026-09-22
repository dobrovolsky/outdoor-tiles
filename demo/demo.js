const center = [1.59033, 42.53313];
const zoom = 12
const tileUrl = (name) => `${location.origin}/tiles/${name}`;
const stylePath = '/styles';
const openFreeMapStyleUrl = 'https://tiles.openfreemap.org/styles/liberty';

const poiColors = {
    water: '#3A94C5',
    ford: '#3A94C5',
    waterfall: '#3A94C5',
    hot_spring: '#3A94C5',
    water_tower: '#3A94C5',
    hydropower: '#3A94C5',
    dam: '#3A94C5',
    castle: '#DFA000',
    ruins: '#DFA000',
    memorial: '#DFA000',
    monument: '#DFA000',
    archaeological_site: '#DFA000',
    fort: '#DFA000',
    campsite: '#DFA000',
    nature_reserve: '#8DA101',
    park: '#8DA101',
    cliff: '#8DA101',
    peak: '#8DA101',
    cave_entrance: '#8DA101',
    bird_hide: '#8DA101',
    picnic: '#8DA101',
    cemetery: '#5C6A72',
    barrier: '#5C6A72',
    windmill: '#5C6A72',
    wind_turbine: '#5C6A72',
    watermill: '#5C6A72',
};

function poiLayers(tileJson) {
    return (tileJson.vector_layers ?? []).map(({ id, minzoom = 7 }) => ({
        id: `poi-${id}`,
        type: 'circle',
        source: 'poi-vector',
        'source-layer': id,
        minzoom,
        layout: { visibility: 'none' },
        paint: {
            'circle-color': poiColors[id] ?? '#F57D26',
            'circle-radius': [
                'interpolate',
                ['linear'],
                ['zoom'],
                7,
                3,
                14,
                6,
            ],
            'circle-stroke-color': '#fff',
            'circle-stroke-width': 1.5,
        },
    }));
}

function addContours(style, demSource) {
    const source = 'contours_m';
    const contourLayer = 'contours';
    style.sources[source] = {
        type: 'vector',
        tiles: [
            demSource.contourProtocolUrl({
                thresholds: {
                    11: [100, 500],
                    12: [50, 250],
                    13: [25, 100],
                    14: [25, 50],
                },
                contourLayer,
                elevationKey: 'ele',
                levelKey: 'level',
                overzoom: 1,
            }),
        ],
        minzoom: 11,
        maxzoom: 16,
    };

    const layers = [
        {
            id: source,
            type: 'line',
            source,
            'source-layer': contourLayer,
            paint: {
                'line-color': 'rgba(191, 99, 56, 1)',
                'line-opacity': 0.4,
                'line-width': 0.6,
            },
        },
        {
            id: 'contours_index_m',
            type: 'line',
            source,
            'source-layer': contourLayer,
            filter: ['==', ['get', 'level'], 1],
            paint: {
                'line-color': 'rgba(191, 99, 56, 1)',
                'line-opacity': 0.5,
                'line-width': 0.9,
            },
        },
        {
            id: 'contours_label_m',
            type: 'symbol',
            source,
            'source-layer': contourLayer,
            filter: ['==', ['get', 'level'], 1],
            layout: {
                'text-size': ['interpolate', ['linear'], ['zoom'], 11, 6, 18, 10],
                'text-allow-overlap': false,
                'symbol-avoid-edges': true,
                'text-ignore-placement': false,
                'symbol-placement': 'line',
                'text-rotation-alignment': 'map',
                'text-field': [
                    'concat',
                    ['number-format', ['get', 'ele'], {}],
                    'm',
                ],
                'text-padding': 0,
            },
            paint: {
                'text-color': '#5c5c5c',
                'text-halo-color': 'rgba(255,255,255,0.85)',
                'text-halo-width': 1.25,
            },
        },
    ];

    style.layers.push(...layers);
}

async function getJson(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
    return response.json();
}

function detailsTable(properties) {
    const table = document.createElement('table');
    for (const [key, value] of Object.entries(properties)) {
        if (key === 'name' || value === null || value === '') continue;

        const row = table.insertRow();
        const label = document.createElement('th');
        label.textContent = key;
        row.append(label);

        const content = row.insertCell();
        if (typeof value === 'string' && /^https?:\/\//.test(value)) {
            const link = document.createElement('a');
            link.href = value;
            link.target = '_blank';
            link.rel = 'noreferrer';
            link.textContent = value;
            content.append(link);
        } else {
            content.textContent = String(value);
        }
    }
    return table;
}

function coordinateText(coordinates) {
    const element = document.createElement('div');
    element.className = 'feature-popup__coordinates';
    element.textContent = `${coordinates[1].toFixed(6)}°, ${coordinates[0].toFixed(6)}°`;
    return element;
}

function poiPopupContent(feature, coordinates) {
    const root = document.createElement('div');
    root.className = 'feature-popup';

    const title = document.createElement('h3');
    title.textContent = feature.properties.name || feature.sourceLayer;
    root.append(title);
    root.append(coordinateText(coordinates));

    const body = document.createElement('div');
    body.className = 'feature-popup__body';
    body.append(
        detailsTable({
            layer: feature.sourceLayer,
            ...feature.properties,
        }),
    );
    root.append(body);
    return root;
}

function routePopupContent(features, coordinates) {
    const root = document.createElement('div');
    root.className = 'feature-popup';
    root.append(coordinateText(coordinates));

    const body = document.createElement('div');
    body.className = 'feature-popup__body';
    for (const feature of features) {
        const properties = feature.properties;
        const route = document.createElement('section');
        route.className = 'route-popup__route';

        const title = document.createElement('h3');
        title.textContent =
            properties.name ||
            properties.ref ||
            `${properties.class || 'route'} route`;
        route.append(title);

        const details = { ...properties };
        if (properties.relation_id !== undefined) {
            details.osm = `https://www.openstreetmap.org/relation/${properties.relation_id}`;
        }
        route.append(detailsTable(details));
        body.append(route);
    }
    root.append(body);
    return root;
}

function namespaceBasemap(style, prefix) {
    const sources = Object.fromEntries(
        Object.entries(style.sources).map(([id, source]) => [
            `${prefix}-${id}`,
            structuredClone(source),
        ]),
    );
    const layers = style.layers.map((layer) => {
        const namespaced = structuredClone(layer);
        namespaced.id = `${prefix}-${layer.id}`;
        if (layer.source) namespaced.source = `${prefix}-${layer.source}`;
        return namespaced;
    });
    return { sources, layers };
}

async function main(maplibregl, demSource, SwipeControl) {
    const [customBasemap, openFreeMap, hiking, cycling, poi] = await Promise.all([
        getJson(`${stylePath}/libertyTopo.json`),
        getJson(openFreeMapStyleUrl),
        getJson(`${stylePath}/hikingRoutes.json`),
        getJson(`${stylePath}/cyclingRoutes.json`),
        getJson(tileUrl('poi')),
    ]);

    const routeStyleLayers = [...hiking.layers, ...cycling.layers];
    const routeLayers = [
        ...routeStyleLayers.filter((layer) => layer.type !== 'symbol'),
        ...routeStyleLayers.filter((layer) => layer.type === 'symbol'),
    ];
    const poiStyleLayers = poiLayers(poi);
    const routeLayerIds = routeLayers.map(({ id }) => id);
    const poiLayerIds = poiStyleLayers.map(({ id }) => id);
    const contourLayerIds = [
        'contours_m',
        'contours_index_m',
        'contours_label_m',
    ];
    const custom = namespaceBasemap(customBasemap, 'custom');
    const openfreemap = namespaceBasemap(openFreeMap, 'openfreemap');
    const customLayerIds = custom.layers.map(({ id }) => id);
    const openFreeMapLayerIds = openfreemap.layers.map(({ id }) => id);

    function buildStyle() {
        const style = structuredClone(customBasemap);
        style.sprite = [
            { id: 'default', url: customBasemap.sprite },
            {
                id: 'routes',
                url: `${location.origin}/static/tiles/routes-sprite`,
            },
        ];
        style.sources = { ...custom.sources, ...openfreemap.sources };
        style.layers = [...custom.layers, ...openfreemap.layers];
        style.sources['custom-openmaptiles'].url = tileUrl('openmaptiles');
        style.sources.routes = {
            ...hiking.sources.routes,
            url: tileUrl('routes'),
        };
        style.sources['poi-vector'] = {
            type: 'vector',
            url: tileUrl('poi'),
        };
        addContours(style, demSource);
        style.layers.push(
            ...structuredClone(routeLayers),
            ...structuredClone(poiStyleLayers),
        );
        return style;
    }

    const map = new maplibregl.Map({
        container: 'map',
        style: buildStyle(),
        center,
        zoom,
        hash: true,
    });
    map.addControl(new maplibregl.NavigationControl(), 'top-right');
    map.addControl(new maplibregl.ScaleControl());
    const swipeControl = new SwipeControl({
        className: 'demo-swipe-control',
        position: 50,
        leftLayers: [
            ...customLayerIds,
            ...contourLayerIds,
            ...routeLayerIds,
        ],
        rightLayers: [
            ...openFreeMapLayerIds,
            ...contourLayerIds,
            ...routeLayerIds,
        ],
        showPanel: false,
    });
    map.addControl(swipeControl);

    const overlays = {
        contours: {
            layerIds: contourLayerIds,
            left: document.querySelector('#contours-left'),
            right: document.querySelector('#contours-right'),
        },
        routes: {
            layerIds: routeLayerIds,
            left: document.querySelector('#routes-left'),
            right: document.querySelector('#routes-right'),
        },
        poi: {
            layerIds: poiLayerIds,
            left: document.querySelector('#poi-left'),
            right: document.querySelector('#poi-right'),
        },
    };
    const popup = new maplibregl.Popup({
        closeButton: false,
        maxWidth: '420px',
    });

    function setVisibility(targetMap, layerIds, visible) {
        for (const layerId of layerIds) {
            if (targetMap?.getLayer(layerId)) {
                targetMap.setLayoutProperty(
                    layerId,
                    'visibility',
                    visible ? 'visible' : 'none',
                );
            }
        }
    }

    function applyOverlayVisibility() {
        const leftOverlayIds = [];
        const rightOverlayIds = [];
        for (const overlay of Object.values(overlays)) {
            if (overlay.left.checked) leftOverlayIds.push(...overlay.layerIds);
            if (overlay.right.checked) rightOverlayIds.push(...overlay.layerIds);
        }

        swipeControl.setLeftLayers([...customLayerIds, ...leftOverlayIds]);
        swipeControl.setRightLayers([
            ...openFreeMapLayerIds,
            ...rightOverlayIds,
        ]);

        for (const overlay of Object.values(overlays)) {
            if (overlay.left.checked || overlay.right.checked) continue;
            for (const targetMap of [map, swipeControl.getComparisonMap()]) {
                setVisibility(targetMap, overlay.layerIds, false);
            }
        }
    }

    function renderedMap(point) {
        const split = (map.getContainer().clientWidth * swipeControl.getPosition()) / 100;
        return point.x <= split ? map : swipeControl.getComparisonMap();
    }

    function overlayEnabledAtPoint(overlay, point) {
        const split = (map.getContainer().clientWidth * swipeControl.getPosition()) / 100;
        return point.x <= split ? overlay.left.checked : overlay.right.checked;
    }

    function renderedPoi(point) {
        const targetMap = renderedMap(point);
        if (!overlayEnabledAtPoint(overlays.poi, point) || !targetMap?.isStyleLoaded()) {
            return [];
        }
        const existingLayers = poiLayerIds.filter((id) => targetMap.getLayer(id));
        return targetMap.queryRenderedFeatures(point, { layers: existingLayers });
    }

    function renderedRoutes(point) {
        const targetMap = renderedMap(point);
        if (
            !overlayEnabledAtPoint(overlays.routes, point) ||
            !targetMap?.isStyleLoaded()
        ) {
            return [];
        }
        const existingLayers = routeLayerIds.filter((id) => targetMap.getLayer(id));
        const radius = 5;
        const features = targetMap.queryRenderedFeatures(
            [
                [point.x - radius, point.y - radius],
                [point.x + radius, point.y + radius],
            ],
            { layers: existingLayers },
        );
        const unique = new Map();
        for (const feature of features) {
            const properties = feature.properties;
            const key =
                properties.relation_id ??
                [
                    properties.class,
                    properties.network,
                    properties.ref,
                    properties.name,
                ].join('|');
            if (!unique.has(key)) unique.set(key, feature);
        }
        return [...unique.values()];
    }

    for (const overlay of Object.values(overlays)) {
        for (const control of [overlay.left, overlay.right]) {
            control.addEventListener('change', () => {
                popup.remove();
                applyOverlayVisibility();
            });
        }
    }
    map.on('style.load', applyOverlayVisibility);

    map.on('mousemove', (event) => {
        map.getCanvas().style.cursor =
            renderedPoi(event.point).length || renderedRoutes(event.point).length
                ? 'pointer'
                : '';
    });
    map.on('click', (event) => {
        const poiFeature = renderedPoi(event.point)[0];
        if (poiFeature?.geometry.type === 'Point') {
            const coordinates = [...poiFeature.geometry.coordinates];
            while (Math.abs(event.lngLat.lng - coordinates[0]) > 180) {
                coordinates[0] += event.lngLat.lng > coordinates[0] ? 360 : -360;
            }
            popup
                .setLngLat(coordinates)
                .setDOMContent(poiPopupContent(poiFeature, coordinates))
                .addTo(map);
            return;
        }

        const routeFeatures = renderedRoutes(event.point);
        if (routeFeatures.length) {
            const coordinates = [event.lngLat.lng, event.lngLat.lat];
            popup
                .setLngLat(coordinates)
                .setDOMContent(routePopupContent(routeFeatures, coordinates))
                .addTo(map);
            return;
        }

        popup.remove();
    });
}

try {
    const [maplibregl, { SwipeControl }] = await Promise.all([
        import('maplibre-gl'),
        import(
            'https://cdn.jsdelivr.net/npm/maplibre-gl-swipe@0.11.3/dist/index.mjs'
        ),
    ]);
    const demSource = new globalThis.mlcontour.DemSource({
        url: 'https://tiles.mapterhorn.com/{z}/{x}/{y}.webp',
        encoding: 'terrarium',
        maxzoom: 16,
        worker: true,
    });
    demSource.setupMaplibre(maplibregl);
    await main(maplibregl, demSource, SwipeControl);
} catch (error) {
    document.querySelector('#status').textContent =
        `Could not open the demo. Check demo/static/tiles/*.mbtiles.\n${error.message}`;
    console.error(error);
}
