import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import MetricTooltip, { DetailedMetricTooltipContent } from "../components/Tooltip";
import { METRICS } from "../data/metricDefinitions";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Cell,
} from "recharts";
import {
  fetchCompany,
  fetchCompanyHistory,
  fetchCompanyFilings,
  fetchCompanyPrices,
} from "../api/client";
import ScoreBadge from "../components/ScoreBadge";
import ChatPanel from "../components/chat/ChatPanel";

function formatLargeNumber(v: number | null): string {
  if (v === null || v === undefined) return "--";
  const abs = Math.abs(v);
  if (abs >= 1e12) return `${(v / 1e12).toFixed(1)}T`;
  if (abs >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return v.toFixed(0);
}

function formatPct(v: number | null): string {
  if (v === null || v === undefined) return "--";
  return `${(v * 100).toFixed(1)}%`;
}

const DILUTION_TYPE_COLORS: Record<string, string> = {
  atm: "bg-danger/20 text-danger border-danger/30",
  atm_shelf: "bg-danger/20 text-danger border-danger/30",
  registered_direct: "bg-warning/20 text-warning border-warning/30",
  follow_on: "bg-accent/20 text-accent border-accent/30",
  convertible: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  pipe: "bg-cyan-500/20 text-cyan-400 border-cyan-500/30",
};

export default function CompanyDetail() {
  const { ticker } = useParams<{ ticker: string }>();
  const navigate = useNavigate();

  const [chatOpen, setChatOpen] = useState(false);
  const [chatView, setChatView] = useState<"panel" | "full">("panel");

  const companyQ = useQuery({
    queryKey: ["company", ticker],
    queryFn: () => fetchCompany(ticker!),
    enabled: !!ticker,
  });

  const historyQ = useQuery({
    queryKey: ["history", ticker],
    queryFn: () => fetchCompanyHistory(ticker!),
    enabled: !!ticker,
  });

  const filingsQ = useQuery({
    queryKey: ["filings", ticker],
    queryFn: () => fetchCompanyFilings(ticker!),
    enabled: !!ticker,
  });

  const [priceMonths, setPriceMonths] = useState(12);
  const pricesQ = useQuery({
    queryKey: ["prices", ticker, priceMonths],
    queryFn: () => fetchCompanyPrices(ticker!, priceMonths),
    enabled: !!ticker,
  });

  if (companyQ.isLoading) {
    return (
      <div className="p-6 text-muted">Loading...</div>
    );
  }

  if (companyQ.error || !companyQ.data) {
    return (
      <div className="p-6">
        <button onClick={() => navigate("/")} className="text-accent hover:text-accent-hover text-sm mb-4">
          &larr; Back to Screener
        </button>
        <p className="text-danger">Company not found</p>
      </div>
    );
  }

  const company = companyQ.data;
  const score = company.score;
  const history = historyQ.data;
  const filings = filingsQ.data;

  // Chart data (chronological)
  const sharesData = (history?.fundamentals ?? company.fundamentals)
    .slice()
    .sort((a, b) => a.fiscal_period.localeCompare(b.fiscal_period))
    .map((f) => ({
      period: f.fiscal_period,
      shares: f.shares_outstanding_diluted,
    }));

  const fcfData = (history?.fundamentals ?? company.fundamentals)
    .slice()
    .sort((a, b) => a.fiscal_period.localeCompare(b.fiscal_period))
    .map((f) => ({
      period: f.fiscal_period,
      fcf: f.free_cash_flow,
    }));

  const severityLabel =
    (score?.composite_score ?? 0) >= 75
      ? "Critical"
      : (score?.composite_score ?? 0) >= 50
        ? "High"
        : (score?.composite_score ?? 0) >= 25
          ? "Moderate"
          : "Low";

  const severityColor =
    severityLabel === "Critical"
      ? "text-danger"
      : severityLabel === "High"
        ? "text-warning"
        : severityLabel === "Moderate"
          ? "text-accent"
          : "text-success";

  // Full-page chat view
  if (chatOpen && chatView === "full") {
    return (
      <div className="flex flex-col h-full">
        {/* Compact company header */}
        <div className="flex items-center gap-3 px-4 py-2.5 border-b border-border bg-panel-light flex-shrink-0">
          <button
            onClick={() => navigate("/")}
            className="text-muted hover:text-gray-200 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="font-mono font-bold text-gray-100">{company.ticker}</span>
          <ScoreBadge score={score?.composite_score ?? null} size="sm" />
          <span className={`text-xs font-semibold ${severityColor}`}>{severityLabel}</span>
          <span className="text-xs text-muted">{company.name}</span>

          {/* Tab switcher */}
          <div className="ml-auto flex items-center gap-1 bg-surface rounded-lg p-0.5">
            <button
              onClick={() => setChatView("panel")}
              className="px-3 py-1 rounded text-xs font-medium text-muted hover:text-gray-200 transition-colors"
            >
              Data
            </button>
            <button
              className="px-3 py-1 rounded text-xs font-medium bg-accent text-white"
            >
              Chat
            </button>
          </div>
        </div>

        {/* Full chat panel */}
        <ChatPanel
          ticker={ticker}
          onClose={() => setChatOpen(false)}
          onViewChange={(v) => setChatView(v)}
          currentView="full"
          showViewToggle
          className="flex-1"
        />
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Main company content */}
      <div className={`flex-1 overflow-y-auto p-6 ${chatOpen ? "" : "max-w-[1400px] mx-auto"}`}>
        {/* Back button */}
        <button
          onClick={() => navigate("/")}
          className="text-accent hover:text-accent-hover text-sm mb-4 flex items-center gap-1"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Screener
        </button>

        {/* Header */}
        <div className="flex items-start justify-between mb-6 gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-mono font-bold text-gray-100">
                {company.ticker}
              </h1>
              <ScoreBadge score={score?.composite_score ?? null} size="lg" />
              <span className={`text-sm font-semibold ${severityColor}`}>
                {severityLabel}
              </span>
            </div>
            <p className="text-muted mt-1">{company.name}</p>
            <div className="flex gap-4 mt-2 text-xs text-muted">
              {company.sector && <span>{company.sector}</span>}
              {company.exchange && <span>{company.exchange}</span>}
              {company.market_cap && (
                <span>
                  Mkt Cap: ${formatLargeNumber(company.market_cap)}
                </span>
              )}
            </div>
          </div>

          {/* Chat button chip */}
          {!chatOpen && (
            <button
              onClick={() => setChatOpen(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-accent hover:bg-accent-hover text-white text-sm font-medium transition-all shadow-sm hover:shadow-md flex-shrink-0 whitespace-nowrap"
              title={`Chat about ${ticker}`}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
              </svg>
              Ask AI
            </button>
          )}
        </div>

        {/* Score breakdown grid */}
        {score && (
          <div className="grid grid-cols-3 gap-3 mb-6">
            <ScoreCard
              label="Share CAGR"
              score={score.share_cagr_score}
              metric={formatPct(score.share_cagr_3y)}
              desc="3-year annualized share growth"
              metricKey="share_cagr"
            />
            <ScoreCard
              label="FCF Burn"
              score={score.fcf_burn_score}
              metric={formatPct(score.fcf_burn_rate)}
              desc="Annual FCF burn / market cap"
              metricKey="fcf_burn"
            />
            <ScoreCard
              label="SBC / Revenue"
              score={score.sbc_revenue_score}
              metric={formatPct(score.sbc_revenue_pct)}
              desc="Trailing 4Q SBC / revenue"
              metricKey="sbc_revenue"
            />
            <ScoreCard
              label="Offering Freq"
              score={score.offering_freq_score}
              metric={`${score.offering_count_3y ?? 0} filings`}
              desc="Dilutive filings in 3 years"
              metricKey="offering_freq"
            />
            <ScoreCard
              label="Cash Runway"
              score={score.cash_runway_score}
              metric={
                score.cash_runway_months !== null
                  ? `${score.cash_runway_months.toFixed(0)} months`
                  : "--"
              }
              desc="Months of cash at current burn"
              metricKey="cash_runway"
            />
            <ScoreCard
              label="ATM Active"
              score={score.atm_active_score}
              metric={score.atm_program_active ? "Yes" : "No"}
              desc="Active shelf/ATM program"
              metricKey="atm_active"
            />
          </div>
        )}

        {/* Stock Price Chart */}
        <div className="bg-surface rounded-lg border border-border p-4 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-medium text-muted uppercase tracking-wider">
              Stock Price
              {score?.price_change_12m != null && (
                <span
                  className={`ml-2 text-sm font-mono font-semibold ${
                    score.price_change_12m >= 0 ? "text-success" : "text-danger"
                  }`}
                >
                  {score.price_change_12m >= 0 ? "+" : ""}
                  {(score.price_change_12m * 100).toFixed(1)}% (12M)
                </span>
              )}
            </h3>
            <div className="flex gap-1">
              {[3, 6, 12, 24].map((m) => (
                <button
                  key={m}
                  onClick={() => setPriceMonths(m)}
                  className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                    priceMonths === m
                      ? "bg-accent text-white"
                      : "bg-panel text-muted hover:text-gray-200"
                  }`}
                >
                  {m}M
                </button>
              ))}
            </div>
          </div>
          {pricesQ.isLoading ? (
            <div className="h-[250px] flex items-center justify-center text-muted text-sm">
              Loading prices...
            </div>
          ) : pricesQ.data && pricesQ.data.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={pricesQ.data}>
                <defs>
                  <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop
                      offset="5%"
                      stopColor={
                        (pricesQ.data[pricesQ.data.length - 1]?.close ?? 0) >=
                        (pricesQ.data[0]?.close ?? 0)
                          ? "#22c55e"
                          : "#ef4444"
                      }
                      stopOpacity={0.3}
                    />
                    <stop
                      offset="95%"
                      stopColor={
                        (pricesQ.data[pricesQ.data.length - 1]?.close ?? 0) >=
                        (pricesQ.data[0]?.close ?? 0)
                          ? "#22c55e"
                          : "#ef4444"
                      }
                      stopOpacity={0}
                    />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#64748b", fontSize: 10 }}
                  axisLine={{ stroke: "#1e293b" }}
                  tickFormatter={(d) => {
                    const parts = d.split("-");
                    return `${parts[1]}/${parts[0]?.substring(2)}`;
                  }}
                  interval="preserveStartEnd"
                  minTickGap={50}
                />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fill: "#64748b", fontSize: 10 }}
                  axisLine={{ stroke: "#1e293b" }}
                  tickFormatter={(v) => `$${v.toFixed(2)}`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0f172a",
                    border: "1px solid #1e293b",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                  formatter={(v) => [`$${Number(v).toFixed(2)}`, "Close"]}
                  labelFormatter={(label) => String(label)}
                />
                <Area
                  type="monotone"
                  dataKey="close"
                  stroke={
                    (pricesQ.data[pricesQ.data.length - 1]?.close ?? 0) >=
                    (pricesQ.data[0]?.close ?? 0)
                      ? "#22c55e"
                      : "#ef4444"
                  }
                  fillOpacity={1}
                  fill="url(#priceGradient)"
                  strokeWidth={2}
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-muted text-sm">
              No price data available
            </div>
          )}
        </div>

        {/* Charts */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          {/* Shares Outstanding */}
          <div className="bg-surface rounded-lg border border-border p-4">
            <h3 className="text-xs font-medium text-muted uppercase tracking-wider mb-3">
              Shares Outstanding
            </h3>
            {sharesData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={sharesData}>
                  <defs>
                    <linearGradient id="sharesGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis
                    dataKey="period"
                    tick={{ fill: "#64748b", fontSize: 10 }}
                    axisLine={{ stroke: "#1e293b" }}
                  />
                  <YAxis
                    tickFormatter={(v) => formatLargeNumber(v)}
                    tick={{ fill: "#64748b", fontSize: 10 }}
                    axisLine={{ stroke: "#1e293b" }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      border: "1px solid #1e293b",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    formatter={(v) => [formatLargeNumber(v as number), "Shares"]}
                  />
                  <Area
                    type="monotone"
                    dataKey="shares"
                    stroke="#ef4444"
                    fillOpacity={1}
                    fill="url(#sharesGradient)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[200px] flex items-center justify-center text-muted text-sm">
                No data available
              </div>
            )}
          </div>

          {/* Free Cash Flow */}
          <div className="bg-surface rounded-lg border border-border p-4">
            <h3 className="text-xs font-medium text-muted uppercase tracking-wider mb-3">
              Free Cash Flow
            </h3>
            {fcfData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={fcfData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis
                    dataKey="period"
                    tick={{ fill: "#64748b", fontSize: 10 }}
                    axisLine={{ stroke: "#1e293b" }}
                  />
                  <YAxis
                    tickFormatter={(v) => formatLargeNumber(v)}
                    tick={{ fill: "#64748b", fontSize: 10 }}
                    axisLine={{ stroke: "#1e293b" }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      border: "1px solid #1e293b",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                    formatter={(v) => [`$${formatLargeNumber(v as number)}`, "FCF"]}
                  />
                  <Bar dataKey="fcf" radius={[4, 4, 0, 0]}>
                    {fcfData.map((entry, i) => (
                      <Cell
                        key={i}
                        fill={
                          (entry.fcf ?? 0) < 0 ? "#ef4444" : "#22c55e"
                        }
                        fillOpacity={0.8}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[200px] flex items-center justify-center text-muted text-sm">
                No data available
              </div>
            )}
          </div>
        </div>

        {/* Filing Timeline */}
        {filings && filings.length > 0 && (
          <div className="bg-surface rounded-lg border border-border p-4">
            <h3 className="text-xs font-medium text-muted uppercase tracking-wider mb-3">
              SEC Filings
            </h3>
            <div className="space-y-2">
              {filings.map((f) => (
                <div
                  key={f.accession_number}
                  className="flex items-center gap-3 py-2 border-b border-border/50 last:border-0"
                >
                  <div className="text-xs font-mono text-muted w-24 flex-shrink-0">
                    {f.filed_date ?? "--"}
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded border text-xs font-medium flex-shrink-0 ${
                      DILUTION_TYPE_COLORS[f.dilution_type ?? ""] ??
                      "bg-border/50 text-muted border-border"
                    }`}
                  >
                    {f.filing_type}
                  </span>
                  {f.dilution_type && (
                    <span className="text-xs text-muted">
                      {f.dilution_type.replace(/_/g, " ")}
                    </span>
                  )}
                  {f.offering_amount_dollars && (
                    <span className="text-xs font-mono text-warning">
                      ${formatLargeNumber(f.offering_amount_dollars)}
                    </span>
                  )}
                  {f.is_dilution_event && (
                    <span className="ml-auto text-xs text-danger font-medium">
                      Dilutive
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Side panel chat */}
      {chatOpen && chatView === "panel" && (
        <ChatPanel
          ticker={ticker}
          onClose={() => setChatOpen(false)}
          onViewChange={(v) => setChatView(v)}
          currentView="panel"
          showViewToggle
          className="w-[420px] flex-shrink-0 border-l border-border"
        />
      )}
    </div>
  );
}

function ScoreCard({
  label,
  score,
  metric,
  desc,
  metricKey,
}: {
  label: string;
  score: number | null;
  metric: string;
  desc: string;
  metricKey?: string;
}) {
  const color =
    score === null
      ? "border-border"
      : score >= 75
        ? "border-danger/50"
        : score >= 50
          ? "border-warning/50"
          : score >= 25
            ? "border-accent/50"
            : "border-success/50";

  const metricDef = metricKey ? METRICS[metricKey] : undefined;

  return (
    <div className={`bg-surface rounded-lg border ${color} p-4`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-muted uppercase tracking-wider">
          {metricDef ? (
            <MetricTooltip
              position="top"
              maxWidth="max-w-sm"
              content={
                <DetailedMetricTooltipContent
                  detailedDesc={metricDef.detailedDesc}
                  calculation={metricDef.calculation}
                  timePeriod={metricDef.timePeriod}
                  scoreInterpretation={metricDef.scoreInterpretation}
                  defaultWeight={metricDef.defaultWeight}
                  caveat={metricDef.caveat}
                />
              }
            >
              <span>{label}</span>
            </MetricTooltip>
          ) : (
            label
          )}
        </span>
        <ScoreBadge score={score} size="sm" />
      </div>
      <div className="font-mono text-lg font-semibold text-gray-100">
        {metric}
      </div>
      <div className="text-xs text-muted mt-1">{desc}</div>
    </div>
  );
}
