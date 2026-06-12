import { useEffect, useState } from "react";
import { fetchHealth } from "../api/client";

interface FeatureCard {
  title: string;
  description: string;
  milestone: string;
}

const ROADMAP: FeatureCard[] = [
  { title: "Assets & VLANs", description: "Inventory of VLANs, IP ranges and assets with owners.", milestone: "M1" },
  { title: "Scanning", description: "Distributed agents discover open ports and services.", milestone: "M2" },
  { title: "Change detection", description: "Flapping-aware diffs surface confirmed changes only.", milestone: "M3" },
  { title: "Audit & evidence", description: "Hash-chained log and one-click auditor evidence packages.", milestone: "M4" },
  { title: "Tasks & integrations", description: "In-app tasks, email and Jira on every confirmed change.", milestone: "M5" },
  { title: "AI assistant", description: "Fingerprint unknown services and operate PortWiz by chat.", milestone: "M6" },
];

export default function DashboardPage() {
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    fetchHealth()
      .then((h) => setApiHealthy(h.status === "ok"))
      .catch(() => setApiHealthy(false));
  }, []);

  return (
    <div>
      <div className="mb-8 flex items-center gap-3">
        <span
          className={`inline-block h-2.5 w-2.5 rounded-full ${
            apiHealthy === null
              ? "bg-slate-500"
              : apiHealthy
                ? "bg-emerald-500"
                : "bg-red-500"
          }`}
        />
        <span className="text-sm text-slate-400">
          API status:{" "}
          {apiHealthy === null ? "checking…" : apiHealthy ? "healthy" : "unreachable"}
        </span>
      </div>

      <h2 className="mb-4 text-lg font-semibold text-slate-200">Roadmap</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {ROADMAP.map((card) => (
          <div key={card.milestone} className="rounded-xl border border-slate-800 bg-slate-900 p-5">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="font-medium text-slate-100">{card.title}</h3>
              <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs text-emerald-400">
                {card.milestone}
              </span>
            </div>
            <p className="text-sm text-slate-400">{card.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
