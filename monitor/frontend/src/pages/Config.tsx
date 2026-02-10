import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchThresholds,
  updateThresholds,
  fetchWeights,
  updateWeights,
} from "../api/client";
import {
  getThresholdImplication,
  getWeightImplication,
} from "../data/configImplications";

type Tab = "thresholds" | "weights";

const THRESHOLD_DEFS: {
  key: string;
  label: string;
  desc: string;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
}[] = [
  {
    key: "share_cagr_min",
    label: "Share CAGR Min",
    desc: "Minimum annualized share growth to flag",
    min: 0,
    max: 0.5,
    step: 0.01,
    format: (v) => `${(v * 100).toFixed(0)}%`,
  },
  {
    key: "fcf_negative_quarters",
    label: "Negative FCF Quarters",
    desc: "Minimum negative FCF quarters to flag",
    min: 1,
    max: 12,
    step: 1,
    format: (v) => `${v}`,
  },
  {
    key: "share_cagr_ceiling",
    label: "Share CAGR Ceiling",
    desc: "CAGR at which score maxes out",
    min: 0.1,
    max: 1.0,
    step: 0.05,
    format: (v) => `${(v * 100).toFixed(0)}%`,
  },
  {
    key: "fcf_burn_ceiling",
    label: "FCF Burn Ceiling",
    desc: "Burn rate at which score maxes out",
    min: 0.1,
    max: 1.0,
    step: 0.05,
    format: (v) => `${(v * 100).toFixed(0)}%`,
  },
  {
    key: "sbc_revenue_ceiling",
    label: "SBC/Revenue Ceiling",
    desc: "SBC/Revenue ratio at which score maxes out",
    min: 0.1,
    max: 1.0,
    step: 0.05,
    format: (v) => `${(v * 100).toFixed(0)}%`,
  },
  {
    key: "offering_freq_ceiling",
    label: "Offering Freq Ceiling",
    desc: "Number of offerings at which score maxes out",
    min: 1,
    max: 15,
    step: 1,
    format: (v) => `${v}`,
  },
  {
    key: "cash_runway_max_months",
    label: "Cash Runway Max",
    desc: "Months below which score increases",
    min: 6,
    max: 48,
    step: 3,
    format: (v) => `${v} months`,
  },
  {
    key: "critical_percentile",
    label: "Critical Percentile",
    desc: "Top X% of scores = Critical tier",
    min: 80,
    max: 99,
    step: 1,
    format: (v) => `Top ${100 - v}%`,
  },
  {
    key: "watchlist_percentile",
    label: "Watchlist Percentile",
    desc: "Top X% of scores = Watchlist tier (below Critical)",
    min: 30,
    max: 80,
    step: 5,
    format: (v) => `Top ${100 - v}%`,
  },
];

const WEIGHT_DEFS: {
  key: string;
  label: string;
  desc: string;
}[] = [
  { key: "weight_share_cagr", label: "Share CAGR", desc: "Weight for share growth score" },
  { key: "weight_fcf_burn", label: "FCF Burn", desc: "Weight for cash burn score" },
  { key: "weight_sbc_revenue", label: "SBC/Revenue", desc: "Weight for stock compensation score" },
  { key: "weight_offering_freq", label: "Offering Freq", desc: "Weight for offering frequency score" },
  { key: "weight_cash_runway", label: "Cash Runway", desc: "Weight for cash runway score" },
  { key: "weight_atm_active", label: "ATM Active", desc: "Weight for ATM program score" },
];

export default function Config() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("thresholds");
  const [localThresholds, setLocalThresholds] = useState<Record<string, number>>({});
  const [localWeights, setLocalWeights] = useState<Record<string, number>>({});
  const [saved, setSaved] = useState(false);

  const thresholdsQ = useQuery({
    queryKey: ["thresholds"],
    queryFn: fetchThresholds,
  });
  const weightsQ = useQuery({
    queryKey: ["weights"],
    queryFn: fetchWeights,
  });

  useEffect(() => {
    if (thresholdsQ.data) setLocalThresholds(thresholdsQ.data);
  }, [thresholdsQ.data]);

  useEffect(() => {
    if (weightsQ.data) setLocalWeights(weightsQ.data);
  }, [weightsQ.data]);

  const saveThresholdsMut = useMutation({
    mutationFn: updateThresholds,
    onSuccess: (data) => {
      queryClient.setQueryData(["thresholds"], data);
      flash();
    },
  });

  const saveWeightsMut = useMutation({
    mutationFn: updateWeights,
    onSuccess: (data) => {
      queryClient.setQueryData(["weights"], data);
      flash();
    },
  });

  function flash() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function handleReset() {
    if (tab === "thresholds" && thresholdsQ.data) {
      setLocalThresholds(thresholdsQ.data);
    } else if (weightsQ.data) {
      setLocalWeights(weightsQ.data);
    }
  }

  const weightTotal = Object.values(localWeights).reduce((s, v) => s + v, 0);

  return (
    <div className="p-6 max-w-[1000px] mx-auto">
      <h1 className="text-xl font-semibold text-gray-100 mb-1">
        Configuration
      </h1>
      <p className="text-sm text-muted mb-6">
        Adjust scoring thresholds and weights. Changes are in-memory and reset on server restart.
      </p>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setTab("thresholds")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === "thresholds"
              ? "bg-accent text-white"
              : "bg-surface text-muted hover:text-gray-200"
          }`}
        >
          Thresholds
        </button>
        <button
          onClick={() => setTab("weights")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === "weights"
              ? "bg-accent text-white"
              : "bg-surface text-muted hover:text-gray-200"
          }`}
        >
          Weights
        </button>
      </div>

      {/* Content */}
      <div className="bg-surface rounded-lg border border-border p-6">
        {tab === "thresholds" && (
          <div className="space-y-6">
            {THRESHOLD_DEFS.map((def) => (
              <div key={def.key}>
                <div className="flex justify-between mb-1">
                  <label className="text-sm font-medium text-gray-200">
                    {def.label}
                  </label>
                  <span className="font-mono text-sm text-accent">
                    {def.format(localThresholds[def.key] ?? 0)}
                  </span>
                </div>
                <input
                  type="range"
                  min={def.min}
                  max={def.max}
                  step={def.step}
                  value={localThresholds[def.key] ?? 0}
                  onChange={(e) =>
                    setLocalThresholds((prev) => ({
                      ...prev,
                      [def.key]: parseFloat(e.target.value),
                    }))
                  }
                  className="w-full"
                />
                <p className="text-xs text-muted mt-1">{def.desc}</p>
                {thresholdsQ.data &&
                  getThresholdImplication(
                    def.key,
                    thresholdsQ.data[def.key],
                    localThresholds[def.key] ?? 0
                  ) && (
                    <div className="mt-2 px-3 py-2 bg-accent/10 border border-accent/20 rounded-lg text-xs text-accent leading-relaxed">
                      <span className="font-medium">Impact: </span>
                      {getThresholdImplication(
                        def.key,
                        thresholdsQ.data[def.key],
                        localThresholds[def.key] ?? 0
                      )}
                    </div>
                  )}
              </div>
            ))}
          </div>
        )}

        {tab === "weights" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted">
                Total weight:{" "}
                <span
                  className={`font-mono font-semibold ${
                    Math.abs(weightTotal - 1.0) < 0.01
                      ? "text-success"
                      : "text-warning"
                  }`}
                >
                  {weightTotal.toFixed(2)}
                </span>
              </span>
              {Math.abs(weightTotal - 1.0) >= 0.01 && (
                <span className="text-xs text-warning">
                  Weights should sum to 1.0
                </span>
              )}
            </div>

            {WEIGHT_DEFS.map((def) => (
              <div key={def.key}>
                <div className="flex justify-between mb-1">
                  <label className="text-sm font-medium text-gray-200">
                    {def.label}
                  </label>
                  <span className="font-mono text-sm text-accent">
                    {(localWeights[def.key] ?? 0).toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={0.5}
                  step={0.05}
                  value={localWeights[def.key] ?? 0}
                  onChange={(e) =>
                    setLocalWeights((prev) => ({
                      ...prev,
                      [def.key]: parseFloat(e.target.value),
                    }))
                  }
                  className="w-full"
                />
                <p className="text-xs text-muted mt-1">{def.desc}</p>
                {weightsQ.data &&
                  getWeightImplication(
                    def.key,
                    def.label,
                    weightsQ.data[def.key],
                    localWeights[def.key] ?? 0
                  ) && (
                    <div className="mt-2 px-3 py-2 bg-accent/10 border border-accent/20 rounded-lg text-xs text-accent leading-relaxed">
                      <span className="font-medium">Impact: </span>
                      {getWeightImplication(
                        def.key,
                        def.label,
                        weightsQ.data[def.key],
                        localWeights[def.key] ?? 0
                      )}
                    </div>
                  )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex gap-3 mt-4">
        <button
          onClick={() =>
            tab === "thresholds"
              ? saveThresholdsMut.mutate(localThresholds)
              : saveWeightsMut.mutate(localWeights)
          }
          className="px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm font-medium transition-colors"
        >
          {saveThresholdsMut.isPending || saveWeightsMut.isPending
            ? "Saving..."
            : "Save"}
        </button>
        <button
          onClick={handleReset}
          className="px-4 py-2 bg-surface border border-border text-muted hover:text-gray-200 rounded-lg text-sm font-medium transition-colors"
        >
          Reset
        </button>
        {saved && (
          <span className="self-center text-sm text-success">Saved!</span>
        )}
      </div>
    </div>
  );
}
