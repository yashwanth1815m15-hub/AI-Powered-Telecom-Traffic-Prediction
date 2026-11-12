import React, { useEffect, useRef, useState, useMemo } from 'react';
import { Tower, OpenCellIDClustersResponse, OpenCellIDRecordItem, PresenterStatus } from '../types/telemetry';
import {
  fetchOpenCellIDClusters,
  fetchOpenCellIDRecords,
  fetchOoklaTiles,
  fetchIndiaBoundary
} from '../services/api';
import { translate } from '../i18n/translations';
import L from 'leaflet';
import Fuse from 'fuse.js';
import {
  Search,
  MapPin,
  X,
  AlertTriangle,
  AlertOctagon,
  CheckCircle2,
  Navigation,
  Loader2,
  ChevronRight,
  Flame,
  Radio,
  SlidersHorizontal,
  Compass,
  Hexagon,
  ChevronUp,
  ChevronDown
} from 'lucide-react';

interface NocMapViewProps {
  towers: Tower[];
  onSelectTower: (tower: Tower) => void;
  selectedTowerId?: string;
  language: string;
  presenterStatus?: PresenterStatus | null;
}

interface GeocodedPlace {
  name: string;
  state?: string;
  lat: number;
  lon: number;
}

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371.0;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c * 10) / 10;
}

function normalizeStr(s: string): string {
  return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().toLowerCase();
}

const INDIVIDUAL_RECORDS_MIN_ZOOM = 13;

export const NocMapView: React.FC<NocMapViewProps> = ({
  towers,
  onSelectTower,
  selectedTowerId,
  language,
  presenterStatus
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const lastFlownDemoKeyRef = useRef<string | null>(null);
  const markersGroupRef = useRef<L.LayerGroup | null>(null);
  const ocidGroupRef = useRef<L.LayerGroup | null>(null);
  const ooklaGroupRef = useRef<L.LayerGroup | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [ocidData, setOcidData] = useState<OpenCellIDClustersResponse | null>(null);
  const [zoomedRecords, setZoomedRecords] = useState<OpenCellIDRecordItem[]>([]);
  const [ooklaData, setOoklaData] = useState<any>(null);
  const [showOoklaLayer, setShowOoklaLayer] = useState<boolean>(false);
  const [mapZoom, setMapZoom] = useState<number>(5);
  const [showOcidLayer, setShowOcidLayer] = useState<boolean>(true);

  // Place Geocoding State
  const [placeResults, setPlaceResults] = useState<GeocodedPlace[]>([]);
  const [isSearchingPlaces, setIsSearchingPlaces] = useState<boolean>(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [showDropdown, setShowDropdown] = useState<boolean>(false);

  // Active searched place and nearest towers
  const [activePlace, setActivePlace] = useState<GeocodedPlace | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(true);

  // Fuse.js Index for Fuzzy Tower Search
  const fuse = useMemo(() => {
    return new Fuse(towers, {
      keys: ['tower_id', 'name', 'city', 'circle', 'state', 'operator', 'area_type'],
      threshold: 0.35,
      ignoreLocation: true
    });
  }, [towers]);

  // Compute Towers that Need Attention strictly from alert-derived status (A5 split)
  const overloadedTowers = useMemo(() => {
    return towers.filter(
      (t) => t.status === 'OUTAGE' || t.status === 'CRITICAL' || t.status === 'AT_RISK' || t.status === 'WARNING'
    );
  }, [towers]);

  const weakCoverageTowers = useMemo(() => {
    return towers.filter((t) => t.status === 'WEAK_COVERAGE');
  }, [towers]);

  const attentionTowers = useMemo(() => {
    return [...overloadedTowers, ...weakCoverageTowers];
  }, [overloadedTowers, weakCoverageTowers]);

  const criticalCount = useMemo(() => {
    return towers.filter((t) => t.status === 'CRITICAL' || t.status === 'OUTAGE').length;
  }, [towers]);

  const atRiskCount = useMemo(() => {
    return towers.filter((t) => t.status === 'AT_RISK' || t.status === 'WARNING').length;
  }, [towers]);

  // Fuzzy Tower Matches
  const matchedTowers = useMemo(() => {
    const q = normalizeStr(searchQuery);
    if (!q) return [];
    const fuseMatches = fuse.search(q).map((res) => res.item);
    if (fuseMatches.length > 0) return fuseMatches.slice(0, 5);

    // Fallback substring matching
    return towers.filter((t) => {
      return (
        normalizeStr(t.name).includes(q) ||
        normalizeStr(t.city).includes(q) ||
        normalizeStr(t.tower_id).includes(q) ||
        normalizeStr(t.circle || '').includes(q)
      );
    }).slice(0, 5);
  }, [searchQuery, fuse, towers]);

  // Debounced Place Geocoder (Photon / Nominatim limited to India bbox)
  useEffect(() => {
    const q = normalizeStr(searchQuery);
    if (!q || q.length < 2) {
      setPlaceResults([]);
      setIsSearchingPlaces(false);
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsSearchingPlaces(true);
    setSearchError(null);

    const timer = setTimeout(async () => {
      try {
        // Photon Indian bbox query
        const url = `https://photon.komoot.io/api/?q=${encodeURIComponent(q)}&bbox=68.0,6.5,97.5,37.5&limit=4`;
        const res = await fetch(url, { signal: controller.signal });
        if (!res.ok) throw new Error('Geocoding service unavailable');
        const data = await res.json();

        const places: GeocodedPlace[] = (data.features || []).map((f: any) => ({
          name: f.properties.name || f.properties.city || f.properties.street || 'Location',
          state: f.properties.state || f.properties.country || 'India',
          lat: f.geometry.coordinates[1],
          lon: f.geometry.coordinates[0]
        }));
        setPlaceResults(places);
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          console.warn('Geocoder notice:', err);
          setSearchError('Place search unavailable');
        }
      } finally {
        setIsSearchingPlaces(false);
      }
    }, 250);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [searchQuery]);

  // Initialize Leaflet Map with Esri World Dark Neutral Canvas
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const indiaBounds = L.latLngBounds([6.2, 67.5], [37.5, 97.6]);

    const map = L.map(mapContainerRef.current, {
      center: [21.5, 78.8],
      zoom: 5,
      minZoom: 4,
      maxZoom: 17,
      maxBounds: indiaBounds,
      maxBoundsViscosity: 0.9,
      zoomControl: false
    });

    map.fitBounds([[7.5, 68.5], [35.8, 97.0]], { padding: [20, 20] });

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    // Esri Canvas Dark Base with OpenStreetMap & Esri Attribution
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
      attribution: '&copy; <a href="https://www.esri.com" target="_blank" rel="noopener">Esri</a> &mdash; &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
      maxZoom: 16
    }).addTo(map);

    const maskGroup = L.layerGroup().addTo(map);
    const layerGroup = L.layerGroup().addTo(map);
    const ocidGroup = L.layerGroup().addTo(map);
    const ooklaGroup = L.layerGroup().addTo(map);
    markersGroupRef.current = layerGroup;
    ocidGroupRef.current = ocidGroup;
    ooklaGroupRef.current = ooklaGroup;
    mapInstanceRef.current = map;

    // Dim everything outside India so the NOC canvas remains strictly focused on India
    fetchIndiaBoundary()
      .then((res) => {
        const indiaRings: [number, number][][] = [];
        if (Array.isArray(res?.polygons)) {
          indiaRings.push(...res.polygons);
        } else if (Array.isArray(res?.features)) {
          res.features.forEach((feat: any) => {
            const geom = feat?.geometry;
            if (!geom) return;
            if (geom.type === 'Polygon' && Array.isArray(geom.coordinates?.[0])) {
              indiaRings.push(geom.coordinates[0].map((c: number[]) => [c[1], c[0]]));
            } else if (geom.type === 'MultiPolygon' && Array.isArray(geom.coordinates)) {
              geom.coordinates.forEach((poly: any) => {
                if (Array.isArray(poly?.[0])) {
                  indiaRings.push(poly[0].map((c: number[]) => [c[1], c[0]]));
                }
              });
            }
          });
        }
        if (!indiaRings.length) return;
        const worldOuter: [number, number][] = [
          [-90, -180],
          [90, -180],
          [90, 180],
          [-90, 180]
        ];
        L.polygon([worldOuter, ...indiaRings], {
          color: '#3f3f46',
          weight: 1,
          fillColor: '#050507',
          fillOpacity: 0.84,
          interactive: false
        }).addTo(maskGroup);
      })
      .catch(() => {});

    fetchOpenCellIDClusters()
      .then((res) => setOcidData(res))
      .catch((err) => console.warn('Could not load cached OpenCellID clusters:', err));

    fetchOoklaTiles()
      .then((res) => setOoklaData(res))
      .catch((err) => console.warn('Could not load Ookla India tiles:', err));

    let viewportController: AbortController | null = null;
    const handleViewportUpdate = () => {
      const z = map.getZoom();
      setMapZoom(z);
      if (z >= INDIVIDUAL_RECORDS_MIN_ZOOM) {
        if (viewportController) viewportController.abort();
        viewportController = new AbortController();
        const b = map.getBounds();
        fetchOpenCellIDRecords({
          lat_min: b.getSouth(),
          lat_max: b.getNorth(),
          lon_min: b.getWest(),
          lon_max: b.getEast(),
          limit: 300
        })
          .then((res) => setZoomedRecords(res.records || []))
          .catch((err) => console.warn('Could not fetch zoomed OpenCellID records:', err));
      } else {
        setZoomedRecords([]);
      }
    };

    map.on('zoomend', handleViewportUpdate);
    map.on('moveend', handleViewportUpdate);

    // Fix A4: ResizeObserver prevents blank grey Leaflet map when global demo banner mounts/unmounts or resizes
    const containerEl = mapContainerRef.current;
    let resizeObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined' && containerEl) {
      resizeObserver = new ResizeObserver(() => {
        map.invalidateSize({ animate: false });
      });
      resizeObserver.observe(containerEl);
    }
    const initTimer = window.setTimeout(() => {
      map.invalidateSize({ animate: false });
    }, 150);

    return () => {
      window.clearTimeout(initTimer);
      resizeObserver?.disconnect();
      if (viewportController) viewportController.abort();
      map.off('zoomend', handleViewportUpdate);
      map.off('moveend', handleViewportUpdate);
      map.remove();
      mapInstanceRef.current = null;
      ooklaGroupRef.current = null;
      ocidGroupRef.current = null;
    };
  }, []);

  // Re-validate map size & fly to demo city when presenter demo activates/changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    const timer = window.setTimeout(() => {
      map.invalidateSize({ animate: false });
    }, 100);

    if (presenterStatus?.active && presenterStatus.city && presenterStatus.scenario_id) {
      const demoKey = `${presenterStatus.scenario_id}::${presenterStatus.city}`;
      if (lastFlownDemoKeyRef.current !== demoKey) {
        const firstSite =
          presenterStatus.affected_sites?.[0] ||
          towers.find((t) => t.city?.toLowerCase() === presenterStatus.city?.toLowerCase());
        if (firstSite) {
          lastFlownDemoKeyRef.current = demoKey;
          map.flyTo([firstSite.lat, firstSite.lon], 11, { duration: 1.0 });
        }
      }
    } else if (!presenterStatus?.active) {
      lastFlownDemoKeyRef.current = null;
    }

    return () => window.clearTimeout(timer);
  }, [presenterStatus?.active, presenterStatus?.city, presenterStatus?.scenario_id, towers]);

  // Filtered towers for markers (single source of truth via tower.status)
  const filteredTowers = useMemo(() => {
    let result = towers;
    if (filterStatus === 'CRITICAL') {
      result = result.filter((t) => t.status === 'CRITICAL' || t.status === 'OUTAGE');
    } else if (filterStatus === 'WARNING') {
      result = result.filter((t) => t.status === 'AT_RISK' || t.status === 'WARNING' || t.status === 'WEAK_COVERAGE');
    } else if (filterStatus === 'HEALTHY') {
      result = result.filter((t) => !t.status || t.status === 'HEALTHY');
    }
    return result;
  }, [towers, filterStatus]);

  const demoTargetSet = useMemo(() => {
    return new Set(presenterStatus?.active ? presenterStatus.target_tower_ids || [] : []);
  }, [presenterStatus?.active, presenterStatus?.target_tower_ids]);

  // Update Markers (strictly alert-derived status colour + demo pulse ring)
  useEffect(() => {
    if (!mapInstanceRef.current || !markersGroupRef.current) return;

    markersGroupRef.current.clearLayers();

    filteredTowers.forEach((tower) => {
      const load = tower.current_load_pct ?? 50.0;
      const st = tower.status || 'HEALTHY';
      const isCrit = st === 'CRITICAL' || st === 'OUTAGE';
      const isWarn = st === 'AT_RISK' || st === 'WARNING' || st === 'WEAK_COVERAGE';
      const statusClass = isCrit ? 'beacon-critical' : (isWarn ? 'beacon-warning' : 'beacon-healthy');
      const isDemoTarget = demoTargetSet.has(tower.tower_id);
      const pulseHalo = isDemoTarget
        ? `<span style="position:absolute;inset:-6px;border-radius:9999px;border:2px solid ${isCrit ? '#ff453a' : '#ffd60a'};animation:ping 1.2s cubic-bezier(0,0,0.2,1) infinite;"></span>`
        : '';

      const customIcon = L.divIcon({
        className: 'apple-beacon-marker',
        html: `<div style="position:relative;display:flex;align-items:center;justify-content:center;">${pulseHalo}<div class="${statusClass}" data-tower-id="${tower.tower_id}" data-status="${st}"></div></div>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11]
      });

      const marker = L.marker([tower.lat, tower.lon], { icon: customIcon });

      marker.on('click', () => {
        onSelectTower(tower);
      });

      const isReal = (tower as any).source_type?.includes('REAL') || (tower as any).source_type?.includes('OpenCellID') || tower.tower_id.startsWith('OCID');
      const provenanceLabel = isReal
        ? 'REAL - OpenCellID (approximate position, about 1 km)'
        : 'SIMULATED SITE';

      marker.bindTooltip(`
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; padding: 3px 5px; min-width: 160px;">
          <div style="font-weight: 700; color: #ffffff;">${tower.name}</div>
          <div style="color: #a1a1a6; font-size: 10px;">${tower.city} • ${tower.tower_id}</div>
          <div style="margin-top: 2px; font-size: 9px; font-weight: 700; color: ${isReal ? '#34d399' : '#fbbf24'};">
            ${provenanceLabel}${isDemoTarget ? ' • DEMO ACTIVE' : ''}
          </div>
          <div style="margin-top: 3px; font-weight: bold; color: ${isCrit ? '#ff453a' : (isWarn ? '#ff9f0a' : '#30d158')};">
            Status: ${st} • Load: ${load.toFixed(1)}% (SIMULATED)
          </div>
        </div>
      `, {
        direction: 'top',
        offset: [0, -10],
        opacity: 0.95
      });

      markersGroupRef.current?.addLayer(marker);
    });
  }, [filteredTowers, onSelectTower, demoTargetSet]);

  // Render Ookla Quarterly Mobile Performance Tiles (India-filtered)
  useEffect(() => {
    if (!mapInstanceRef.current || !ooklaGroupRef.current) return;
    ooklaGroupRef.current.clearLayers();
    if (!showOoklaLayer || !ooklaData?.tiles?.length) return;

    ooklaData.tiles.forEach((tile: any) => {
      const dl = Number(tile.avg_d_mbps ?? 0);
      const color = dl >= 120 ? '#34d399' : dl >= 50 ? '#38bdf8' : dl >= 20 ? '#fbbf24' : '#f87171';
      const circle = L.circleMarker([tile.lat, tile.lon], {
        radius: 4,
        color,
        weight: 1,
        opacity: 0.75,
        fillColor: color,
        fillOpacity: 0.45
      });
      circle.bindTooltip(`
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; padding: 3px 5px; min-width: 170px;">
          <div style="font-weight: 700; color: #34d399;">Real mobile speed (Ookla, quarterly)</div>
          <div style="color: #e4e4e7; font-size: 10px; margin-top: 2px;">${tile.state || 'India'} • ${ooklaData.quarter || 'Q3 2026'}</div>
          <div style="margin-top: 3px; font-weight: bold; color: #fff;">
            DL: ${dl.toFixed(1)} Mbps • UL: ${Number(tile.avg_u_mbps ?? 0).toFixed(1)} Mbps
          </div>
          <div style="color: #a1a1a6; font-size: 10px;">
            Latency: ${Number(tile.avg_lat_ms ?? 0).toFixed(0)} ms • ${tile.tests} tests (${tile.devices} devices)
          </div>
        </div>
      `, { direction: 'top', offset: [0, -4], opacity: 0.96 });
      ooklaGroupRef.current?.addLayer(circle);
    });
  }, [showOoklaLayer, ooklaData]);

  // Render OpenCellID Area Clusters (zoom < 13) or Individual Cell Records (zoom >= 13)
  useEffect(() => {
    if (!mapInstanceRef.current || !ocidGroupRef.current) return;
    ocidGroupRef.current.clearLayers();
    if (!showOcidLayer) return;

    if (mapZoom >= INDIVIDUAL_RECORDS_MIN_ZOOM && zoomedRecords.length > 0) {
      // Fan out co-located rounded-1km records in a deterministic spiral strictly for map clickability
      const coordIndex = new Map<string, number>();

      zoomedRecords.forEach((r) => {
        const key = `${r.lat.toFixed(2)}_${r.lon.toFixed(2)}`;
        const idx = coordIndex.get(key) ?? 0;
        coordIndex.set(key, idx + 1);

        const angle = idx * 2.39996;
        const radiusDeg = idx === 0 ? 0 : 0.00035 + 0.00018 * Math.sqrt(idx);
        const dispLat = r.lat + radiusDeg * Math.sin(angle);
        const dispLon = r.lon + radiusDeg * Math.cos(angle);

        const cellIcon = L.divIcon({
          className: 'ocid-cell-dot',
          html: `<div style="width:10px;height:10px;border-radius:9999px;background:#38bdf8;border:1.5px solid #e0f2fe;box-shadow:0 0 6px rgba(56,189,248,0.65);"></div>`,
          iconSize: [10, 10],
          iconAnchor: [5, 5]
        });

        const marker = L.marker([dispLat, dispLon], { icon: cellIcon });
        marker.bindTooltip(`
          <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; padding: 3px 5px; min-width: 210px;">
            <div style="font-weight: 700; color: #38bdf8;">${r.radio} Cell #${r.cellid}</div>
            <div style="color: #e4e4e7; font-size: 10px;">${r.operator_label} (MCC ${r.mcc} / MNC ${r.mnc})</div>
            <div style="color: #a1a1aa; font-size: 9px; font-family: monospace;">LAC: ${r.lac} • Samples: ${r.samples}</div>
            <div style="color: #fbbf24; font-size: 9px; margin-top: 2px;">approximate position (about 1 km): ${r.lat.toFixed(2)}, ${r.lon.toFixed(2)}</div>
            <div style="color: #71717a; font-size: 9px;">Source: ${r.source} • Fetched: ${r.fetched_at || 'N/A'}</div>
          </div>
        `, { direction: 'top', offset: [0, -6], opacity: 0.96 });

        marker.bindPopup(`
          <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; color: #e4e4e7; background: #09090b; padding: 6px; min-width: 250px;">
            <div style="font-weight: 700; color: #38bdf8; font-size: 12px;">OpenCellID Record (Real Fields Only)</div>
            <div style="color: #a1a1aa; font-size: 10px; margin-bottom: 6px;">${r.city || 'India'}, ${r.state || 'India'}</div>
            <table style="width:100%; border-collapse:collapse; font-family:monospace; font-size:10px; color:#d4d4d8;">
              <tr><td style="padding:2px 4px;color:#71717a;">Radio Type</td><td style="padding:2px 4px;font-weight:700;">${r.radio}</td></tr>
              <tr><td style="padding:2px 4px;color:#71717a;">MCC / MNC</td><td style="padding:2px 4px;">${r.mcc} / ${r.mnc}</td></tr>
              <tr><td style="padding:2px 4px;color:#71717a;">Operator</td><td style="padding:2px 4px;">${r.operator_label}</td></tr>
              <tr><td style="padding:2px 4px;color:#71717a;">Area Code (LAC)</td><td style="padding:2px 4px;">${r.lac}</td></tr>
              <tr><td style="padding:2px 4px;color:#71717a;">Cell ID</td><td style="padding:2px 4px;">${r.cellid}</td></tr>
              <tr><td style="padding:2px 4px;color:#71717a;">Approx. Pos (~1 km)</td><td style="padding:2px 4px;">${r.lat.toFixed(2)}, ${r.lon.toFixed(2)}</td></tr>
              <tr><td style="padding:2px 4px;color:#71717a;">Sample Count</td><td style="padding:2px 4px;">${r.samples}</td></tr>
              <tr><td style="padding:2px 4px;color:#71717a;">Source</td><td style="padding:2px 4px;">${r.source} (CC BY-SA 4.0)</td></tr>
              <tr><td style="padding:2px 4px;color:#71717a;">Fetched Date</td><td style="padding:2px 4px;">${r.fetched_at || 'N/A'}</td></tr>
            </table>
          </div>
        `, { maxWidth: 320 });

        ocidGroupRef.current?.addLayer(marker);
      });
      return;
    }

    if (!ocidData?.clusters?.length) return;

    ocidData.clusters.forEach((cluster) => {
      const clusterIcon = L.divIcon({
        className: 'ocid-cluster-marker',
        html: `<div style="display:flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:9999px;background:rgba(14,165,233,0.22);border:1.5px solid #38bdf8;color:#e0f2fe;font-size:10px;font-weight:800;font-family:monospace;box-shadow:0 0 12px rgba(56,189,248,0.35);">${cluster.cell_count}</div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 15]
      });

      const marker = L.marker([cluster.lat, cluster.lon], { icon: clusterIcon });

      marker.bindTooltip(`
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; padding: 3px 5px; min-width: 220px;">
          <div style="font-weight: 700; color: #38bdf8;">area cluster (${cluster.cell_count} cell records)</div>
          <div style="color: #e4e4e7; font-size: 10px;">${cluster.city}, ${cluster.state}</div>
          <div style="color: #fbbf24; font-size: 9px; font-weight: 600; margin-top: 2px;">
            approximate position (about 1 km) • 0.01° grid (&gt;2 km radius)
          </div>
          <div style="color: #a1a1aa; font-size: 9px; margin-top: 2px;">
            Radios: ${cluster.radios.join(', ')} • MCC: ${cluster.mccs.join(', ')}
          </div>
          <div style="color: #71717a; font-size: 9px; margin-top: 2px;">
            Click for sample records or zoom in (&ge;13) for individual cells
          </div>
        </div>
      `, {
        direction: 'top',
        offset: [0, -14],
        opacity: 0.96
      });

      const sampleRowsHtml = cluster.records
        .slice(0, 6)
        .map(
          (r) =>
            `<tr><td style="padding:2px 5px;">${r.radio}</td><td style="padding:2px 5px;">${r.mcc}-${r.mnc}</td><td style="padding:2px 5px;">${r.operator_label}</td><td style="padding:2px 5px;">${r.lac}</td><td style="padding:2px 5px;">${r.cellid}</td><td style="padding:2px 5px;">${r.samples}</td><td style="padding:2px 5px;">${r.fetched_at || '-'}</td></tr>`
        )
        .join('');

      marker.bindPopup(`
        <div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 11px; color: #e4e4e7; background: #09090b; padding: 4px; min-width: 310px;">
          <div style="font-weight: 700; color: #38bdf8; font-size: 12px;">OpenCellID area cluster (${cluster.cell_count} cell records)</div>
          <div style="color: #a1a1aa; font-size: 10px; margin-bottom: 4px;">${cluster.city}, ${cluster.state} • (${cluster.lat.toFixed(2)}, ${cluster.lon.toFixed(2)})</div>
          <div style="background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.3); color: #fcd34d; padding: 3px 6px; border-radius: 6px; font-size: 9px; margin-bottom: 6px;">
            ${ocidData.clustering_method || '0.01° grid binning (> 2 km effective radius)'}. Zoom to level ${INDIVIDUAL_RECORDS_MIN_ZOOM}+ to reveal individual cell records.
          </div>
          <table style="width:100%; border-collapse:collapse; font-family:monospace; font-size:9px; color:#d4d4d8;">
            <thead><tr style="border-bottom:1px solid #27272a; color:#71717a;"><th align="left" style="padding:2px 5px;">Radio</th><th align="left" style="padding:2px 5px;">MCC-MNC</th><th align="left" style="padding:2px 5px;">Operator</th><th align="left" style="padding:2px 5px;">LAC</th><th align="left" style="padding:2px 5px;">CellID</th><th align="left" style="padding:2px 5px;">Samples</th><th align="left" style="padding:2px 5px;">Fetched</th></tr></thead>
            <tbody>${sampleRowsHtml}</tbody>
          </table>
          <div style="color: #71717a; font-size: 9px; margin-top: 6px; border-top: 1px solid #27272a; padding-top: 4px;">
            ${ocidData.attribution} • Real OpenCellID fields only
          </div>
        </div>
      `, { maxWidth: 420 });

      ocidGroupRef.current?.addLayer(marker);
    });
  }, [ocidData, zoomedRecords, mapZoom, showOcidLayer]);

  // Handle Selection of a Place (Fly map & list nearest towers)
  const handleSelectPlace = (place: GeocodedPlace) => {
    setActivePlace(place);
    setShowDropdown(false);
    if (mapInstanceRef.current) {
      mapInstanceRef.current.flyTo([place.lat, place.lon], 12, { duration: 1.2 });
    }
  };

  // Handle Selection of a Tower
  const handleSelectTowerResult = (tower: Tower) => {
    onSelectTower(tower);
    setShowDropdown(false);
    if (mapInstanceRef.current) {
      mapInstanceRef.current.flyTo([tower.lat, tower.lon], 13, { duration: 1.2 });
    }
  };

  // Enter Key Handler (Selects top match)
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      if (matchedTowers.length > 0) {
        handleSelectTowerResult(matchedTowers[0]);
      } else if (placeResults.length > 0) {
        handleSelectPlace(placeResults[0]);
      }
    }
  };

  // Nearest towers to active place
  const nearestTowersToPlace = useMemo(() => {
    if (!activePlace) return [];
    return towers
      .map((t) => ({
        tower: t,
        distanceKm: haversineKm(activePlace.lat, activePlace.lon, t.lat, t.lon)
      }))
      .sort((a, b) => a.distanceKm - b.distanceKm)
      .slice(0, 5);
  }, [activePlace, towers]);

  const quickRegions = [
    { label: "All India", center: [22.0, 78.9], zoom: 5 },
    { label: "Andhra Pradesh", center: [16.5, 80.6], zoom: 7 },
    { label: "Telangana", center: [17.4, 78.48], zoom: 11 },
    { label: "Karnataka", center: [13.0, 77.6], zoom: 10 },
    { label: "Maharashtra", center: [19.07, 72.88], zoom: 9 },
    { label: "Delhi NCR", center: [28.61, 77.21], zoom: 10 },
    { label: "Gujarat", center: [23.05, 72.58], zoom: 9 },
    { label: "Tamil Nadu", center: [13.04, 80.23], zoom: 9 },
    { label: "Kerala", center: [10.0, 76.35], zoom: 9 },
    { label: "Uttar Pradesh", center: [26.85, 81.0], zoom: 8 },
    { label: "West Bengal", center: [22.58, 88.4], zoom: 10 },
    { label: "Punjab", center: [30.9, 75.8], zoom: 8 }
  ];

  return (
    <div className="relative w-full h-[calc(100vh-125px)] overflow-hidden bg-black flex">
      {/* =========================================================================
          LEFT SIDEBAR: "NEEDS ATTENTION" LIST & NEAREST TOWERS (RESPONSIVE)
      ========================================================================= */}
      <div className={`hidden md:flex flex-col w-80 bg-zinc-950/90 backdrop-blur-2xl border-r border-white/10 z-20 transition-all ${
        isSidebarOpen ? 'translate-x-0' : '-translate-x-full'
      }`}>
        {/* Status Strip Header (A5: Computed attention heading) */}
        <div className="p-4 border-b border-white/[0.08] space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 font-mono">
              {translate(language, 'attention_strip_title')}
            </span>
            <span className="px-2 py-0.5 rounded-full text-[9px] font-mono font-bold bg-amber-500/10 text-amber-300 border border-amber-500/20">
              {criticalCount} CRIT • {atRiskCount + weakCoverageTowers.length} WARN
            </span>
          </div>
          <h2 className="text-sm font-bold text-white leading-snug" data-testid="attention-heading">
            {translate(language, 'attention_heading', {
              total: attentionTowers.length,
              overloaded: overloadedTowers.length,
              weak: weakCoverageTowers.length,
            })}
          </h2>
          <p className="text-[11px] text-zinc-400">
            {translate(language, 'attention_threshold_note')}
          </p>
        </div>

        {/* Scrollable List: Separate Overloaded Sites & Weak-Coverage Sites */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {activePlace && (
            <div className="p-3 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-cyan-400 font-bold font-mono text-[10px] uppercase">
                  Nearest to {activePlace.name}
                </span>
                <button
                  onClick={() => setActivePlace(null)}
                  className="text-zinc-400 hover:text-white"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="space-y-1.5">
                {nearestTowersToPlace.map(({ tower, distanceKm }) => (
                  <div
                    key={tower.tower_id}
                    onClick={() => handleSelectTowerResult(tower)}
                    className="p-2 rounded-xl bg-black/40 hover:bg-white/10 transition-colors cursor-pointer text-xs flex items-center justify-between"
                  >
                    <div>
                      <span className="text-white font-semibold block truncate max-w-[170px]">{tower.name}</span>
                      <span className="text-[10px] text-zinc-400 font-mono">{tower.city} • {tower.tower_id}</span>
                    </div>
                    <span className="text-[11px] font-bold font-mono text-cyan-300">
                      {distanceKm} km
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {attentionTowers.length === 0 ? (
            <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 font-medium text-center">
              {translate(language, 'no_attention_sites')}
            </div>
          ) : (
            <>
              {/* Separate List 1: Overloaded / Outage Sites */}
              <div className="space-y-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-red-400 font-mono block px-1">
                  {translate(language, 'overloaded_sites_title', { count: overloadedTowers.length })}
                </span>
                {overloadedTowers.map((tower) => {
                  const load = tower.current_load_pct ?? 85.0;
                  const isOutage = tower.status === 'OUTAGE' || load < 5.0;
                  const isCritical = tower.status === 'CRITICAL' || load >= 95.0;
                  const reasonText = isOutage
                    ? `Outage: sector load ${load.toFixed(1)}% (< 3% backhaul drop)`
                    : `Load ${load.toFixed(1)}% >= 85% threshold`;
                  return (
                    <div
                      key={tower.tower_id}
                      onClick={() => handleSelectTowerResult(tower)}
                      className={`p-3 rounded-2xl border transition-all cursor-pointer ${
                        selectedTowerId === tower.tower_id
                          ? 'bg-white/10 border-cyan-400/50'
                          : 'apple-glass hover:bg-white/[0.04] border-white/[0.06]'
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="font-mono text-[10px] text-zinc-400 font-bold">{tower.tower_id}</span>
                        <span className={`text-[9px] font-bold px-2 py-0.2 rounded-full uppercase ${
                          (isCritical || isOutage)
                            ? 'bg-red-500/20 text-red-300 border border-red-500/30'
                            : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        }`}>
                          {load.toFixed(1)}% Load
                        </span>
                      </div>
                      <h3 className="text-xs font-bold text-white truncate">{tower.name}</h3>
                      <p className="text-[10px] text-zinc-300 mt-0.5 font-mono">{reasonText}</p>
                      <p className="text-[10px] text-zinc-400 mt-0.5">{tower.city} • {tower.area_type}</p>
                    </div>
                  );
                })}
              </div>

              {/* Separate List 2: Weak-Coverage Sites (never mixed as Overloaded) */}
              {weakCoverageTowers.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-white/[0.06]">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400 font-mono block px-1">
                    {translate(language, 'weak_coverage_sites_title', { count: weakCoverageTowers.length })}
                  </span>
                  {weakCoverageTowers.map((tower) => {
                    const rsrp = tower.rsrp_dbm ?? -116.0;
                    const load = tower.current_load_pct ?? 28.0;
                    return (
                      <div
                        key={tower.tower_id}
                        onClick={() => handleSelectTowerResult(tower)}
                        className={`p-3 rounded-2xl border transition-all cursor-pointer ${
                          selectedTowerId === tower.tower_id
                            ? 'bg-white/10 border-amber-400/50'
                            : 'apple-glass hover:bg-white/[0.04] border-amber-500/25'
                        }`}
                      >
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="font-mono text-[10px] text-zinc-400 font-bold">{tower.tower_id}</span>
                          <span className="text-[9px] font-bold px-2 py-0.2 rounded-full uppercase bg-amber-500/20 text-amber-300 border border-amber-500/30">
                            {rsrp.toFixed(1)} dBm
                          </span>
                        </div>
                        <h3 className="text-xs font-bold text-white truncate">{tower.name}</h3>
                        <p className="text-[10px] text-amber-200 mt-0.5 font-mono">
                          Weak coverage: RSRP {rsrp.toFixed(1)} dBm (&lt; -110 dBm) • Load {load.toFixed(1)}%
                        </p>
                        <p className="text-[10px] text-zinc-400 mt-0.5">{tower.city} • {tower.area_type}</p>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* =========================================================================
          MAIN MAP CANVAS & FLOATING SEARCH BAR
      ========================================================================= */}
      <div className="flex-1 relative h-full">
        {/* Leaflet Map Div */}
        <div ref={mapContainerRef} className="w-full h-full z-0" />

        {/* Floating Search Container (Engineered with zero overlap) */}
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-40 w-full max-w-xl px-4 pointer-events-auto">
          <div className="apple-glass rounded-full p-2 pl-4 flex items-center space-x-3 shadow-2xl relative">
            <Search className="w-4 h-4 text-cyan-400 flex-shrink-0" />
            <input
              type="text"
              placeholder={translate(language, 'search_placeholder')}
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setShowDropdown(true);
              }}
              onFocus={() => setShowDropdown(true)}
              onKeyDown={handleKeyDown}
              className="flex-1 bg-transparent border-none text-white text-xs sm:text-sm focus:outline-none placeholder-zinc-400 font-medium"
            />

            {isSearchingPlaces && (
              <Loader2 className="w-4 h-4 text-cyan-400 animate-spin flex-shrink-0" />
            )}

            {searchQuery && (
              <button
                onClick={() => {
                  setSearchQuery('');
                  setShowDropdown(false);
                }}
                className="p-1 rounded-full text-zinc-400 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            {/* Filter Pills */}
            <div className="flex items-center space-x-1 bg-black/40 rounded-full p-1 border border-white/5">
              {(['ALL', 'CRITICAL', 'WARNING', 'HEALTHY'] as const).map((st) => (
                <button
                  key={st}
                  onClick={() => setFilterStatus(st)}
                  className={`px-2.5 py-1 rounded-full text-[9px] font-bold uppercase transition-all whitespace-nowrap cursor-pointer ${
                    filterStatus === st
                      ? (st === 'CRITICAL' ? 'bg-red-500 text-white' : st === 'WARNING' ? 'bg-amber-400 text-black' : st === 'HEALTHY' ? 'bg-emerald-400 text-black' : 'bg-white text-black')
                      : 'text-zinc-400 hover:text-white'
                  }`}
                >
                  {translate(language, `filter_${st.toLowerCase()}`)}
                </button>
              ))}
            </div>
          </div>

          {/* Autocomplete Search Dropdown (Towers & Indian Places) */}
          {showDropdown && searchQuery.trim().length >= 2 && (
            <div className="mt-2 apple-glass-card rounded-2xl border border-white/10 overflow-hidden shadow-2xl bg-zinc-950/95 max-h-80 overflow-y-auto divide-y divide-white/[0.06]">
              {/* Towers Section */}
              {matchedTowers.length > 0 && (
                <div className="p-2 space-y-1">
                  <span className="text-[10px] font-mono font-bold text-zinc-500 uppercase px-3 block pt-1">
                    {translate(language, 'search_matching_towers')}
                  </span>
                  {matchedTowers.map((tower) => (
                    <div
                      key={tower.tower_id}
                      onClick={() => handleSelectTowerResult(tower)}
                      className="px-3 py-2 rounded-xl hover:bg-white/10 transition-colors cursor-pointer flex items-center justify-between text-xs"
                    >
                      <div>
                        <span className="text-white font-semibold block">{tower.name}</span>
                        <span className="text-[10px] text-zinc-400 font-mono">{tower.city} • {tower.tower_id}</span>
                      </div>
                      <ChevronRight className="w-4 h-4 text-zinc-500" />
                    </div>
                  ))}
                </div>
              )}

              {/* Places Section */}
              {placeResults.length > 0 && (
                <div className="p-2 space-y-1">
                  <span className="text-[10px] font-mono font-bold text-cyan-400 uppercase px-3 block pt-1">
                    {translate(language, 'search_places_india')}
                  </span>
                  {placeResults.map((place, idx) => (
                    <div
                      key={idx}
                      onClick={() => handleSelectPlace(place)}
                      className="px-3 py-2 rounded-xl hover:bg-white/10 transition-colors cursor-pointer flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center space-x-2">
                        <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                        <div>
                          <span className="text-white font-semibold block">{place.name}</span>
                          <span className="text-[10px] text-zinc-400 font-mono">{place.state}</span>
                        </div>
                      </div>
                      <span className="text-[10px] font-mono text-cyan-300">{translate(language, 'search_fly_find')}</span>
                    </div>
                  ))}
                </div>
              )}

              {matchedTowers.length === 0 && placeResults.length === 0 && !isSearchingPlaces && (
                <div className="p-4 text-center text-xs text-zinc-500 font-mono">
                  {searchError ? translate(language, 'search_error') : translate(language, 'search_no_results')}
                </div>
              )}
            </div>
          )}

          {/* Region Quick-Jump Chips (Hidden while dropdown open for zero overlap) */}
          {!(showDropdown && searchQuery.trim().length >= 2) && (
            <div className="flex items-center space-x-2 mt-2 overflow-x-auto py-1 scrollbar-none">
              <span className="text-[10px] font-mono text-zinc-400 whitespace-nowrap">
                {translate(language, 'quick_jump')}
              </span>
              {quickRegions.map((reg) => (
                <button
                  key={reg.label}
                  onClick={() => {
                    if (mapInstanceRef.current) {
                      mapInstanceRef.current.flyTo(reg.center as [number, number], reg.zoom, { duration: 1.2 });
                    }
                  }}
                  className="apple-pill px-2.5 py-0.5 text-[10px] font-medium text-zinc-300 hover:text-white hover:bg-white/15 transition-all whitespace-nowrap cursor-pointer"
                >
                  {reg.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Floating Status & Attribution Pill Bottom Left */}
        <div className="absolute bottom-5 left-5 z-20 apple-glass px-3.5 py-2 rounded-2xl flex flex-wrap items-center gap-2 text-[11px] text-zinc-300 font-medium max-w-[90%]">
          <span className="flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>{translate(language, 'simulated_sites_count', { count: filteredTowers.length })}</span>
          </span>

          <button
            onClick={() => setShowOcidLayer(!showOcidLayer)}
            className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold border transition-all cursor-pointer ${
              showOcidLayer
                ? 'bg-sky-500/20 text-sky-300 border-sky-500/40'
                : 'bg-white/5 text-zinc-400 border-white/10'
            }`}
            title={ocidData?.clustering_method || 'Toggle OpenCellID area clusters; zoom >= 13 reveals individual cell records'}
          >
            {showOcidLayer ? '✓ ' : ''}
            {mapZoom >= INDIVIDUAL_RECORDS_MIN_ZOOM && zoomedRecords.length > 0
              ? `${zoomedRecords.length} individual OpenCellID records shown (zoom ${mapZoom})`
              : `${ocidData?.cluster_count ?? 0} area clusters (${(ocidData?.valid_india_polygon_count ?? 0).toLocaleString()} cell records)`}
          </button>

          <button
            onClick={() => setShowOoklaLayer(!showOoklaLayer)}
            className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold border transition-all cursor-pointer ${
              showOoklaLayer
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                : 'bg-white/5 text-zinc-400 border-white/10'
            }`}
            title="Real mobile speed (Ookla Open Data, quarterly)"
          >
            {showOoklaLayer ? '✓ ' : ''}
            Ookla {ooklaData?.quarter || 'Q3 2026'} ({ooklaData?.total_india_tiles ? `${ooklaData.total_india_tiles.toLocaleString()} India tiles` : 'Loading'})
          </button>

          <span className="text-zinc-400 text-[10px] font-mono pl-2 border-l border-white/10">
            {ocidData?.attribution || 'Cell data: OpenCellID, CC BY-SA 4.0, fetched N/A'}
          </span>
        </div>
      </div>
    </div>
  );
};
