import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  fetchCompanies,
  fetchStats,
  fetchSectors,
  type CompanyListItem,
} from "../api/client";
import ScoreBadge from "../components/ScoreBadge";
import SparklineChart from "../components/SparklineChart";

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

export default function Screener() {
  const navigate = useNavigate();
  const [sector, setSector] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("composite_score");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const statsQ = useQuery({ queryKey: ["stats"], queryFn: fetchStats });
  const sectorsQ = useQuery({ queryKey: ["sectors"], queryFn: fetchSectors });
  const companiesQ = useQuery({
    queryKey: ["companies", sector],
    queryFn: () =>
      fetchCompanies({
        limit: 200,
        ...(sector ? { sector } : {}),
      }),
  });

  const sorted = useMemo(() => {
    if (!companiesQ.data) return [];
    return [...companiesQ.data].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      if (typeof av === "boolean") return (av === bv ? 0 : av ? -1 : 1) * (sortDir === "desc" ? 1 : -1);
      if (typeof av === "string") return av.localeCompare(bv as string) * (sortDir === "desc" ? -1 : 1);
      return ((av as number) - (bv as number)) * (sortDir === "desc" ? -1 : 1);
    });
  }, [companiesQ.data, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const stats = statsQ.data;
  const sectors = sectorsQ.data;

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
        <div className="grid grid-cols-4 gap-4 mb-6">
          <StatCard label="Tracked" value={stats.total_companies.toLocaleString()} />
          <StatCard label="Watchlist" value={stats.watchlist_count.toString()} color="text-warning" />
          <StatCard
            label="Critical"
            value={stats.critical_count.toString()}
            color="text-danger"
          />
          <StatCard
            label="Avg Score"
            value={stats.avg_score ? stats.avg_score.toFixed(1) : "--"}
            color="text-accent"
          />
        </div>
      )}

      {/* Sector tabs */}
      {sectors && sectors.length > 0 && (
        <div className="flex gap-2 mb-4 flex-wrap">
          <button
            onClick={() => setSector(null)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              !sector
                ? "bg-accent text-white"
                : "bg-surface text-muted hover:text-gray-200"
            }`}
          >
            All
          </button>
          {sectors.map((s) => (
            <button
              key={s.sector}
              onClick={() => setSector(s.sector)}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                sector === s.sector
                  ? "bg-accent text-white"
                  : "bg-surface text-muted hover:text-gray-200"
              }`}
            >
              {s.sector} ({s.count})
            </button>
          ))}
        </div>
      )}

      {/* Table */}
      <div className="bg-surface rounded-lg border border-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-panel-light">
                <SortHeader label="Company" field="ticker" current={sortKey} dir={sortDir} onClick={toggleSort} />
                <SortHeader label="Score" field="composite_score" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-right" />
                <SortHeader label="Price 12M" field="price_change_12m" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-right" />
                <SortHeader label="Share CAGR" field="share_cagr_3y" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-right" />
                <th className="px-3 py-2.5 text-left text-xs font-medium text-muted uppercase tracking-wider">Trend</th>
                <SortHeader label="FCF Burn" field="fcf_burn_rate" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-right" />
                <SortHeader label="SBC/Rev" field="sbc_revenue_pct" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-right" />
                <SortHeader label="Offerings" field="offering_count_3y" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-right" />
                <SortHeader label="Runway" field="cash_runway_months" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-right" />
                <SortHeader label="ATM" field="atm_active_score" current={sortKey} dir={sortDir} onClick={toggleSort} className="text-center" />
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
              {sorted.map((c) => (
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
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    <ScoreBadge score={c.composite_score} />
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
}: {
  label: string;
  field: SortKey;
  current: SortKey;
  dir: SortDir;
  onClick: (key: SortKey) => void;
  className?: string;
}) {
  const isActive = current === field;
  return (
    <th
      className={`px-3 py-2.5 text-xs font-medium uppercase tracking-wider cursor-pointer select-none transition-colors hover:text-gray-200 ${
        isActive ? "text-accent" : "text-muted"
      } ${className}`}
      onClick={() => onClick(field)}
    >
      {label}
      {isActive && (
        <span className="ml-1">{dir === "desc" ? "\u25BC" : "\u25B2"}</span>
      )}
    </th>
  );
}
