"use client";

import { useMemo } from "react";
import { Department, RiskLevel, ApprovalStatus } from "@/lib/types";

export interface DashboardRequest {
  request_id: string;
  title: string;
  amount: number;
  department: Department;
  requester: string;
  risk_level: RiskLevel;
  status: ApprovalStatus;
  human_reviews: number;
  created_at?: string;
}

export const DEPARTMENT_BUDGET_LIMITS: Record<Department, number> = {
  engineering: 50000,
  marketing: 30000,
  operations: 40000,
  research: 60000,
  hr: 5000,
};

interface ApprovalDashboardProps {
  requests: DashboardRequest[];
  onSelectSample?: (sample: DashboardRequest) => void;
  onClearHistory?: () => void;
}

export default function ApprovalDashboard({
  requests,
  onSelectSample,
  onClearHistory,
}: ApprovalDashboardProps) {
  // Aggregate statistics across all pipeline requests
  const stats = useMemo(() => {
    const total = requests.length;
    const approved = requests.filter((r) => r.status === "approved");
    const rejected = requests.filter((r) => r.status === "rejected");
    const pending = requests.filter((r) => r.status === "pending" || r.status === "needs_review");

    const totalApprovedAmount = approved.reduce((sum, r) => sum + r.amount, 0);
    const totalRequestedAmount = requests.reduce((sum, r) => sum + r.amount, 0);

    const escalatedCount = requests.filter((r) => r.human_reviews > 0).length;
    const autoApprovedCount = approved.filter((r) => r.human_reviews === 0).length;

    // Department spend mapping
    const deptSpend: Record<Department, number> = {
      engineering: 0,
      marketing: 0,
      operations: 0,
      research: 0,
      hr: 0,
    };
    for (const r of approved) {
      if (deptSpend[r.department] !== undefined) {
        deptSpend[r.department] += r.amount;
      }
    }

    // Risk counts
    const riskCounts: Record<RiskLevel, number> = {
      low: requests.filter((r) => r.risk_level === "low").length,
      medium: requests.filter((r) => r.risk_level === "medium").length,
      high: requests.filter((r) => r.risk_level === "high").length,
      critical: requests.filter((r) => r.risk_level === "critical").length,
    };

    return {
      total,
      approvedCount: approved.length,
      rejectedCount: rejected.length,
      pendingCount: pending.length,
      approvalRate: total > 0 ? (approved.length / total) * 100 : 0,
      escalationRate: total > 0 ? (escalatedCount / total) * 100 : 0,
      totalApprovedAmount,
      totalRequestedAmount,
      autoApprovedCount,
      deptSpend,
      riskCounts,
    };
  }, [requests]);

  const riskBadgeColors: Record<RiskLevel, string> = {
    low: "bg-green-100 text-green-800 border-green-200",
    medium: "bg-blue-100 text-blue-800 border-blue-200",
    high: "bg-amber-100 text-amber-800 border-amber-200",
    critical: "bg-red-100 text-red-800 border-red-200",
  };

  const statusBadgeColors: Record<ApprovalStatus, string> = {
    approved: "bg-green-500 text-white",
    rejected: "bg-red-500 text-white",
    pending: "bg-yellow-500 text-white",
    needs_review: "bg-indigo-500 text-white animate-pulse",
  };

  return (
    <div className="space-y-6">
      {/* Top Banner / Toolbar */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 flex flex-wrap justify-between items-center gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <span>📊</span> Financial Approval Pipeline Dashboard
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Real-time telemetry, human-in-the-loop escalation metrics, and department budget tracking
          </p>
        </div>
        <div className="flex items-center gap-2">
          {onClearHistory && requests.length > 0 && (
            <button
              onClick={onClearHistory}
              className="px-3 py-1.5 text-xs text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg font-medium transition"
            >
              Reset Metrics
            </button>
          )}
        </div>
      </div>

      {/* KPI Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Requests Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                Total Requests
              </p>
              <h3 className="text-3xl font-extrabold text-gray-900 mt-2">{stats.total}</h3>
            </div>
            <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg text-lg">📝</div>
          </div>
          <p className="text-xs text-gray-500 mt-3 flex items-center gap-1">
            <span className="font-semibold text-green-600">{stats.approvedCount} approved</span>
            <span>•</span>
            <span className="font-semibold text-red-600">{stats.rejectedCount} rejected</span>
          </p>
        </div>

        {/* Approval Rate Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                Approval Rate
              </p>
              <h3 className="text-3xl font-extrabold text-gray-900 mt-2">
                {stats.approvalRate.toFixed(0)}%
              </h3>
            </div>
            <div className="p-2.5 bg-green-50 text-green-600 rounded-lg text-lg">✅</div>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-1.5 mt-3 overflow-hidden">
            <div
              className="bg-green-500 h-1.5 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, stats.approvalRate)}%` }}
            />
          </div>
        </div>

        {/* Approved Capital Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                Approved Capital
              </p>
              <h3 className="text-2xl font-extrabold text-gray-900 mt-2">
                ${stats.totalApprovedAmount.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </h3>
            </div>
            <div className="p-2.5 bg-emerald-50 text-emerald-600 rounded-lg text-lg">💰</div>
          </div>
          <p className="text-xs text-gray-500 mt-3">
            Out of ${stats.totalRequestedAmount.toLocaleString(undefined, { maximumFractionDigits: 0 })} requested
          </p>
        </div>

        {/* Human-in-the-Loop Rate Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                HITL Escalation Rate
              </p>
              <h3 className="text-3xl font-extrabold text-amber-700 mt-2">
                {stats.escalationRate.toFixed(0)}%
              </h3>
            </div>
            <div className="p-2.5 bg-amber-50 text-amber-600 rounded-lg text-lg">🛡️</div>
          </div>
          <p className="text-xs text-gray-500 mt-3">
            <span className="font-semibold text-cyan-600">{stats.autoApprovedCount} auto-approved</span> (no humans)
          </p>
        </div>
      </div>

      {/* Two Column Grid: Risk Distribution + Department Budgets */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Risk Distribution Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-base font-bold text-gray-900 flex items-center gap-2 mb-4">
            <span>🎯</span> AI Risk Level Distribution
          </h3>
          <div className="grid grid-cols-2 gap-4">
            {(["low", "medium", "high", "critical"] as RiskLevel[]).map((level) => {
              const count = stats.riskCounts[level];
              const pct = stats.total > 0 ? (count / stats.total) * 100 : 0;
              const descriptions: Record<RiskLevel, string> = {
                low: "Auto-approved (≤ $10k)",
                medium: "Manager review ($10k-$50k)",
                high: "Manager + Finance ($50k-$100k)",
                critical: "Executive sign-off (Urgent >$50k)",
              };

              return (
                <div
                  key={level}
                  className="p-3.5 rounded-lg border border-gray-100 bg-gray-50/50 flex flex-col justify-between"
                >
                  <div className="flex justify-between items-center mb-1">
                    <span
                      className={`text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${riskBadgeColors[level]}`}
                    >
                      {level}
                    </span>
                    <span className="text-lg font-extrabold text-gray-900">{count}</span>
                  </div>
                  <p className="text-[11px] text-gray-500 mb-2">{descriptions[level]}</p>
                  <div className="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
                    <div
                      className={`h-1.5 rounded-full ${
                        level === "low"
                          ? "bg-green-500"
                          : level === "medium"
                          ? "bg-blue-500"
                          : level === "high"
                          ? "bg-amber-500"
                          : "bg-red-500"
                      }`}
                      style={{ width: `${Math.min(100, pct)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Department Budget Utilization Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-base font-bold text-gray-900 flex items-center gap-2 mb-4">
            <span>🏢</span> Department Budget Utilization
          </h3>
          <div className="space-y-4">
            {(Object.keys(DEPARTMENT_BUDGET_LIMITS) as Department[]).map((dept) => {
              const limit = DEPARTMENT_BUDGET_LIMITS[dept];
              const spent = stats.deptSpend[dept] || 0;
              const pct = (spent / limit) * 100;
              const isOver = spent > limit;

              return (
                <div key={dept} className="space-y-1.5">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-semibold text-gray-800 capitalize">{dept}</span>
                    <span className="text-gray-500 font-mono">
                      ${spent.toLocaleString()} / ${limit.toLocaleString()}
                      <span className={`ml-1.5 font-bold ${isOver ? "text-red-600" : "text-gray-700"}`}>
                        ({pct.toFixed(0)}%)
                      </span>
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                    <div
                      className={`h-2 rounded-full transition-all duration-500 ${
                        isOver
                          ? "bg-red-600 animate-pulse"
                          : pct >= 80
                          ? "bg-amber-500"
                          : "bg-blue-600"
                      }`}
                      style={{ width: `${Math.min(100, pct)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Activity Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h3 className="text-base font-bold text-gray-900 flex items-center gap-2">
            <span>📋</span> Pipeline Execution Log
          </h3>
          <span className="text-xs text-gray-500 font-medium">
            {requests.length} total recorded
          </span>
        </div>

        {requests.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm italic">
            No pipeline requests executed yet. Submit a request through the form or chat to see real-time updates!
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-gray-50 text-[11px] font-semibold uppercase tracking-wider text-gray-500 border-b border-gray-200">
                  <th className="py-3 px-4">Request ID</th>
                  <th className="py-3 px-4">Title</th>
                  <th className="py-3 px-4">Dept</th>
                  <th className="py-3 px-4">Requester</th>
                  <th className="py-3 px-4">Amount</th>
                  <th className="py-3 px-4">Risk</th>
                  <th className="py-3 px-4">Human Reviews</th>
                  <th className="py-3 px-4 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-xs">
                {requests.map((r, i) => (
                  <tr key={r.request_id || i} className="hover:bg-gray-50/75 transition">
                    <td className="py-3 px-4 font-mono font-medium text-gray-600">
                      {r.request_id}
                    </td>
                    <td className="py-3 px-4 font-semibold text-gray-900">{r.title}</td>
                    <td className="py-3 px-4 capitalize text-gray-700">{r.department}</td>
                    <td className="py-3 px-4 text-gray-600">{r.requester}</td>
                    <td className="py-3 px-4 font-bold text-gray-900">
                      ${r.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border ${
                          riskBadgeColors[r.risk_level] || "bg-gray-100 text-gray-800"
                        }`}
                      >
                        {r.risk_level}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {r.human_reviews === 0 ? (
                        <span className="text-cyan-700 font-medium">⚡ 0 (Auto)</span>
                      ) : (
                        <span className="text-amber-700 font-medium">
                          👤 {r.human_reviews} stage{r.human_reviews > 1 ? "s" : ""}
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded-full text-[11px] font-bold capitalize ${
                          statusBadgeColors[r.status] || "bg-gray-300 text-gray-700"
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
