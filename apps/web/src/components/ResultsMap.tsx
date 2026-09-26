"use client";

import "leaflet/dist/leaflet.css";

import type { Map as LeafletMap } from "leaflet";
import { useEffect, useRef, useState } from "react";

import type { ConfidenceLabel } from "@/lib/api";

export interface Marker {
  id: string;
  name: { fa: string | null; latin: string | null };
  label: ConfidenceLabel | null;
  lat: number;
  lng: number;
}

interface Text {
  show: string;
  hide: string;
  loading: string;
  failed: string;
  none: string;
  count: string;
}

// OpenStreetMap's own tiles: fine for light use with attribution
// (https://operations.osmfoundation.org/policies/tiles/); set NEXT_PUBLIC_MAP_TILES to
// another provider's URL template before heavy traffic.
const TILES = process.env.NEXT_PUBLIC_MAP_TILES ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
// Same tones as the confidence badges.
const COLORS: Record<ConfidenceLabel, string> = { high: "#0f766e", medium: "#b45309", low: "#6b7280" };

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

export function ResultsMap({ markersUrl, lang, text }: { markersUrl: string; lang: "fa" | "en"; text: Text }) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<"idle" | "loading" | "ready" | "failed">("idle");
  const [count, setCount] = useState(0);
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<LeafletMap | null>(null);

  useEffect(() => {
    if (!open || !container.current) return;
    let cancelled = false;
    setState("loading");
    Promise.all([import("leaflet"), fetch(markersUrl).then((r) => (r.ok ? r.json() : Promise.reject()))])
      .then(([L, data]: [typeof import("leaflet"), { bbox: [number, number, number, number]; markers: Marker[] }]) => {
        if (cancelled || !container.current) return;
        const m = L.map(container.current, { scrollWheelZoom: false });
        map.current = m;
        L.tileLayer(TILES, { maxZoom: 19, attribution: ATTRIBUTION }).addTo(m);
        const [west, south, east, north] = data.bbox;
        const points: [number, number][] = [];
        for (const marker of data.markers) {
          const title = lang === "fa" ? marker.name.fa ?? marker.name.latin : marker.name.latin ?? marker.name.fa;
          const color = COLORS[marker.label ?? "low"];
          L.circleMarker([marker.lat, marker.lng], { radius: 7, color, fillColor: color, fillOpacity: 0.8, weight: 1 })
            .bindPopup(`<a href="#b-${marker.id}" dir="auto">${escapeHtml(title ?? "")}</a>`)
            .addTo(m);
          points.push([marker.lat, marker.lng]);
        }
        if (points.length) m.fitBounds(points, { padding: [24, 24], maxZoom: 15 });
        else m.fitBounds([[south, west], [north, east]]);
        setCount(points.length);
        setState("ready");
      })
      .catch(() => {
        if (!cancelled) setState("failed");
      });
    return () => {
      cancelled = true;
      map.current?.remove();
      map.current = null;
    };
  }, [open, markersUrl, lang]);

  return (
    <section className="space-y-2">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="rounded-full border border-border px-4 py-1.5 text-sm hover:border-primary"
      >
        {open ? text.hide : text.show}
      </button>
      {open && (
        <div className="space-y-1">
          {/* Leaflet's controls assume a left-to-right container. */}
          <div
            ref={container}
            dir="ltr"
            role="region"
            aria-label={text.show}
            className="h-[26rem] w-full overflow-hidden rounded-2xl border border-border"
          />
          <p className="text-xs text-muted" aria-live="polite">
            {state === "loading" && text.loading}
            {state === "failed" && text.failed}
            {state === "ready" && (count ? text.count.replace("{count}", count.toLocaleString(lang === "fa" ? "fa-IR" : "en-US")) : text.none)}
          </p>
        </div>
      )}
    </section>
  );
}
