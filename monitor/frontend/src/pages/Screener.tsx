import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  fetchCompanies,
  fetchStats,
  type CompanyListItem,
} from "../api/client";
import ScoreBadge from "../components/ScoreBadge";
import SparklineChart from "../components/SparklineChart";
import Tooltip, { MetricTooltipContent } from "../components/Tooltip";
import PipelineExplainer from "../components/PipelineExplainer";
import { METRICS } from "../data/metricDefinitions";
import type { MetricDefinition } from "../data/metricDefinitions";

type SortKey = keyof CompanyListItem;
type SortDir = "asc" | "desc";

function formatMarketCap(v: number | null): string {
  if (!v) return "--";
  if (v >= 1e12) return `$${(v / 1e12).toFixed(1)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${v.toLocaleString()}`;
}

function formatPct(v: number | null): string {
  if (v === null || v === undefined) return "--";
  return `${(v * 100).toFixed(1)}%`;
}

function formatMonths(v: number | null): string {
  if (v === null || v === undefined) return "--";
  return `${v.toFixed(0)}mo`;
}

// ── Search / metric filter parser ──────────────────────────────────

type MetricFilter = {
  field: keyof CompanyListItem;
  op: ">" | "<" | ">=" | "<=";
  value: number;
  isPct: boolean; // whether the raw field is a 0-1 ratio displayed as %
};

const METRIC_ALIASES: Record<string, { field: keyof CompanyListItem; isPct: boolean }> = {
  "score": { field: "composite_score", isPct: false },
  "composite": { field: "composite_score", isPct: false },
  "share cagr": { field: "share_cagr_3y", isPct: true },
  "cagr": { field: "share_cagr_3y", isPct: true },
  "shares": { field: "share_cagr_3y", isPct: true },
  "fcf burn": { field: "fcf_burn_rate", isPct: true },
  "fcf": { field: "fcf_burn_rate", isPct: true },
  "burn": { field: "fcf_burn_rate", isPct: true },
  "sbc": { field: "sbc_revenue_pct", isPct: true },
  "sbc/rev": { field: "sbc_revenue_pct", isPct: true },
  "sbc revenue": { field: "sbc_revenue_pct", isPct: true },
  "offerings": { field: "offering_count_3y", isPct: false },
  "offering": { field: "offering_count_3y", isPct: false },
  "runway": { field: "cash_runway_months", isPct: false },
  "cash runway": { field: "cash_runway_months", isPct: false },
  "market cap": { field: "market_cap", isPct: false },
  "mcap": { field: "market_cap", isPct: false },
  "price": { field: "price_change_12m", isPct: true },
  "price 12m": { field: "price_change_12m", isPct: true },
  "12m": { field: "price_change_12m", isPct: true },
};

function parseSearchQuery(query: string): { text: string; filters: MetricFilter[] } {
  const filters: MetricFilter[] = [];
  let remaining = query;

  // Match patterns like "score > 50", "cagr >= 12%", "runway < 6"
  const filterRegex = /([a-z/ ]+?)\s*(>=|<=|>|<)\s*(-?[\d.]+)%?/gi;
  let match;
  while ((match = filterRegex.exec(query)) !== null) {
    const name = match[1].trim().toLowerCase();
    const op = match[2] as MetricFilter["op"];
    const numVal = parseFloat(match[3]);
    const alias = METRIC_ALIASES[name];
    if (alias) {
      filters.push({
        field: alias.field,
        op,
        value: alias.isPct ? numVal / 100 : numVal,
        isPct: alias.isPct,
      });
      remaining = remaining.replace(match[0], "");
    }
  }

  // Also match ">{number}" patterns like "> 50 score"
  const reverseRegex = /(>=|<=|>|<)\s*(-?[\d.]+)%?\s+([a-z/ ]+)/gi;
  while ((match = reverseRegex.exec(query)) !== null) {
    const op = match[1] as MetricFilter["op"];
    const numVal = parseFloat(match[2]);
    const name = match[3].trim().toLowerCase();
    const alias = METRIC_ALIASES[name];
    if (alias && !filters.some((f) => f.field === alias.field)) {
      filters.push({
        field: alias.field,
        op,
        value: alias.isPct ? numVal / 100 : numVal,
        isPct: alias.isPct,
      });
      remaining = remaining.replace(match[0], "");
    }
  }

  return { text: remaining.trim(), filters };
}

function applyMetricFilter(item: CompanyListItem, filter: MetricFilter): boolean {
  const val = item[filter.field] as number | null;
  if (val === null || val === undefined) return false;
  switch (filter.op) {
    case ">": return val > filter.value;
    case "<": return val < filter.value;
    case ">=": return val >= filter.value;
    case "<=": return val <= filter.value;
    default: return true;
  }
}

export default function Screener() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState<string | null>(null);
  const [tier, setTier] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("composite_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 100;

  const showMonitoring = localStorage.getItem("showMonitoring") === "true";

  const statsQ = useQuery({ queryKey: ["stats"], queryFn: fetchStats });
  const companiesQ = useQuery({
    queryKey: ["companies"],
    queryFn: () => fetchCompanies({ limit: 10000 }),
  });

  const parsed = useMemo(() => parseSearchQuery(search), [search]);

  const sorted = useMemo(() => {
    if (!companiesQ.data) return [];
    let filtered = [...companiesQ.data];

    // Filter by tier
    if (tier) {
      filtered = filtered.filter((c) => c.tracking_tier === tier);
    } else if (!showMonitoring) {
      filtered = filtered.filter((c) => c.tracking_tier !== "monitoring");
    }

    // Filter by sector
    if (sector) {
      filtered = filtered.filter((c) => (c.sector || "Other") === sector);
    }

    // Text search (ticker or company name)
    if (parsed.text) {
      const q = parsed.text.toLowerCase();
      filtered = filtered.filter(
        (c) =>
          c.ticker.toLowerCase().includes(q) ||
          (c.name && c.name.toLowerCase().includes(q))
      );
    }

    // Metric filters
    for (const filter of parsed.filters) {
      filtered = filtered.filter((c) => applyMetricFilter(c, filter));
    }

    return filtered.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (typeof av === "boolean") return (av === bv ? 0 : av ? -1 : 1) * (sortDir === "desc" ? 1 : -1);
      if (typeof av === "string") return av.localeCompare(bv as string) * (sortDir === "desc" ? -1 : 1);
      return ((av as number) - (bv as number)) * (sortDir === "desc" ? -1 : 1);
    });
  }, [companiesQ.data, sortKey, sortDir, tier, sector, showMonitoring, parsed]);

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const paged = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  function toggleSort(key: SortKey) {
    setPage(0);
    if (sortKey === key) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const stats = statsQ.data;

  // Compute sector counts client-side from visible companies (respects monitoring toggle)
  const sectorCounts = useMemo(() => {
    if (!companiesQ.data) return [];
    let visible = companiesQ.data;
    if (!showMonitoring) {
      visible = visible.filter((c) => c.tracking_tier !== "monitoring");
    }
    const counts: Record<string, number> = {};
    for (const c of visible) {
      const s = c.sector || "Other";
      counts[s] = (counts[s] || 0) + 1;
    }
    return Object.entries(counts)
      .map(([sector, count]) => ({ sector, count }))
      .sort((a, b) => b.count - a.count);
  }, [companiesQ.data, showMonitoring]);

  return (
    <div className="p-6 max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-100">Dilution Screener</h1>
        <p className="text-sm text-muted mt-1">
          Tracking shareholder dilution across US equities
        </p>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <StatCard label="Critical" value={stats.critical_count.toString()} color="text-danger" />
          <StatCard label="Watchlist" value={stats.watchlist_count.toString()} color="text-warning" />
          <StatCard
            label="Avg Score"
            value={stats.avg_score ? stats.avg_score.toFixed(1) : "--"}
            color="text-accent"
          />
        </div>
      )}

      {/* Pipeline explainer */}
      <PipelineExplainer />

      {/* Filters */}
      <div className="mb-4 flex gap-3 items-start">
        {/* Tier filter */}
        <select
          value={tier ?? ""}
          onChange={(e) => { setTier(e.target.value || null); setPage(0); }}
          className="bg-surface border border-border rounded-lg px-3 py-2 text-sm text-gray-100 appearance-none cursor-pointer pr-8 focus:outline-none focus:border-accent shrink-0"
          style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%239ca3af' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10z'/%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.75rem center' }}
        >
          <option value="">All Tiers</option>
          <option value="critical">Critical</option>
          <option value="watchlist">Watchlist</option>
          {showMonitoring && <option value="monitoring">Monitoring</option>}
        </select>

        {/* Sector filter */}
        {sectorCounts.length > 0 && (
          <select
            value={sector ?? ""}
            onChange={(e) => { setSector(e.target.value || null); setPage(0); }}
            className="bg-surface border border-border rounded-lg px-3 py-2 text-sm text-gray-100 appearance-none cursor-pointer pr-8 focus:outline-none focus:border-accent shrink-0"
            style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%239ca3af' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10z'/%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.75rem center' }}
          >
            <option value="">All Sectors</option>
            {sectorCounts.map((s) => (
              <option key={s.sector} value={s.sector}>
                {s.sector} ({s.count})
              </option>
            ))}
          </select>
        )}

        {/* Search / filter bar */}
        <div className="relative flex-1">
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            placeholder='Search ticker, company, or filter (e.g. "score > 50", "cagr > 12%")'
            className="w-full bg-surface border border-border rounded-lg px-3 py-2 pl-9 text-sm text-gray-100 placeholder:text-muted/60 focus:outline-none focus:border-accent"
          />
          <svg className="absolute left-3 top-2.5 w-4 h-4 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          {parsed.filters.length > 0 && (
            <div className="flex gap-1.5 mt-1.5">
              {parsed.filters.map((f, i) => (
                <span key={i} className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-accent/15 text-accent border border-accent/20">
                  {String(f.field).replace(/_/g, " ")} {f.op} {f.isPct ? `${(f.value * 100).toFixed(0)}%` : f.value}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-surface rounded-lg border border-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-panel-light">
                <SortHeader label="Company" field="ticker" current={sortKey} dir={sortDir} onClick={toggleSort} />
                <SortHeader label="Score" field="composite_score" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-right" />
                <SortHeader label="Price 12M" field="price_change_12m" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-right" />
                <SortHeader label="Share CAGR" field="share_cagr_3y" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-right" tooltip={METRICS.share_cagr} />
                <th className="px-3 py-2.5 text-left text-xs font-medium text-muted uppercase tracking-wider">Trend</th>
                <SortHeader label="FCF Burn" field="fcf_burn_rate" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-right" tooltip={METRICS.fcf_burn} />
                <SortHeader label="SBC/Rev" field="sbc_revenue_pct" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-right" tooltip={METRICS.sbc_revenue} />
                <SortHeader label="Offerings" field="offering_count_3y" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-right" tooltip={METRICS.offering_freq} />
                <SortHeader label="Runway" field="cash_runway_months" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-right" tooltip={METRICS.cash_runway} />
                <SortHeader label="ATM" field="atm_active_score" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-center" tooltip={METRICS.atm_active} />
                <SortHeader label="Mkt Cap" field="market_cap" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-right" />
              </tr>
            </thead>
            <tbody>
              {companiesQ.isLoading && (
                <tr>
                  <td colSpan={11} className="px-3 py-8 text-center text-muted">
                    Loading...
                  </td>
                </tr>
              )}
              {companiesQ.error && (
                <tr>
                  <td colSpan={11} className="px-3 py-8 text-center text-danger">
                    Error loading data: {(companiesQ.error as Error).message}
                    <br />
                    <span className="text-muted text-xs mt-1 block">
                      Make sure the API server is running on http://localhost:8000
                    </span>
                  </td>
                </tr>
              )}
              {paged.map((c) => (
                <tr
                  key={c.ticker}
                  onClick={() => navigate(`/company/${c.ticker}`)}
                  className="border-b border-border/50 hover:bg-surface/80 cursor-pointer transition-colors"
                >
                  <td className="px-3 py-2.5">
                    <div className="font-mono font-semibold text-gray-100">
                      {c.ticker}
                    </div>
                    <div className="text-xs text-muted truncate max-w-[200px]">
                      {c.name}
                    </div>
                    <div className="text-[10px] text-muted/70 mt-0.5">
                      {c.sector || "Other"}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    <ScoreBadge score={c.composite_score} tier={c.tracking_tier} />
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-xs">
                    <PriceChange value={c.price_change_12m} />
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-xs">
                    {formatPct(c.share_cagr_3y)}
                  </td>
                  <td className="px-3 py-2.5">
                    <SparklineChart
                      data={[
                        c.share_cagr_score,
                        c.fcf_burn_score,
                        c.sbc_revenue_score,
                        c.offering_freq_score,
                        c.cash_runway_score,
                        c.atm_active_score,
                      ]}
                    />
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-xs">
                    {formatPct(c.fcf_burn_rate)}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-xs">
                    {formatPct(c.sbc_revenue_pct)}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-xs">
                    {c.offering_count_3y ?? "--"}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-xs">
                    {formatMonths(c.cash_runway_months)}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    {c.atm_program_active ? (
                      <span className="inline-block w-2 h-2 rounded-full bg-danger animate-pulse" />
                    ) : (
                      <span className="inline-block w-2 h-2 rounded-full bg-border" />
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-xs text-muted">
                    {formatMarketCap(c.market_cap)}
                  </td>
                </tr>
              ))}
              {!companiesQ.isLoading && sorted.length === 0 && (
                <tr>
                  <td colSpan={11} className="px-3 py-8 text-center text-muted">
                    No companies found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border">
            <span className="text-xs text-muted">
              {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, sorted.length)} of {sorted.length}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1 rounded text-xs font-medium bg-surface text-muted hover:text-gray-200 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Prev
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="px-3 py-1 rounded text-xs font-medium bg-surface text-muted hover:text-gray-200 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────

function StatCard({
  label,
  value,
  color = "text-gray-100",
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="bg-surface rounded-lg border border-border p-4">
      <div className="text-xs text-muted uppercase tracking-wider mb-1">
        {label}
      </div>
      <div className={`text-2xl font-mono font-bold ${color}`}>{value}</div>
    </div>
  );
}

function PriceChange({ value }: { value: number | null }) {
  if (value === null || value === undefined) return <span className="text-muted">--</span>;
  const pct = (value * 100).toFixed(1);
  const isPositive = value >= 0;
  return (
    <span className={isPositive ? "text-success" : "text-danger"}>
      {isPositive ? "+" : ""}{pct}%
    </span>
  );
}

function SortHeader({
  label,
  field,
  current,
  dir,
  onClick,
  className = "",
  tooltip,
}: {
  label: string;
  field: SortKey;
  current: SortKey;
  dir: SortDir;
  onClick: (key: SortKey) => void;
  className?: string;
  tooltip?: MetricDefinition;
}) {
  const isActive = current === field;
  return (
    <th
      className={`px-3 py-2.5 text-xs font-medium uppercase tracking-wider cursor-pointer select-none transition-colors hover:text-gray-200 ${
        isActive ? "text-accent" : "text-muted"
      } ${className}`}
      onClick={() => onClick(field)}
    >
      {tooltip ? (
        <Tooltip
          position="bottom"
          content={
            <MetricTooltipContent
              shortDesc={tooltip.shortDesc}
              calculation={tooltip.calculation}
              timePeriod={tooltip.timePeriod}
              scoreInterpretation={tooltip.scoreInterpretation}
              caveat={tooltip.caveat}
            />
          }
        >
          <span>{label}</span>
        </Tooltip>
      ) : (
        label
      )}
      {isActive && (
        <span className="ml-1">{dir === "desc" ? "\u25BC" : "\u25B2"}</span>
      )}
    </th>
  );
}
