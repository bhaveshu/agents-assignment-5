"use client";

import { useState, useEffect } from "react";
import { CopilotChat } from "@copilotkit/react-ui";
import { useCoAgent } from "@copilotkit/react-core";
import "@copilotkit/react-ui/styles.css";
import ApprovalPanel from "@/components/ApprovalPanel";
import RequestForm from "@/components/RequestForm";
import WorkflowStatus from "@/components/WorkflowStatus";
import RequestHistory from "@/components/RequestHistory";
import ApprovalDashboard, { DashboardRequest } from "@/components/ApprovalDashboard";
import { ApprovalResult, ApprovalStatus, RiskLevel, Department } from "@/lib/types";

// Seed requests representing historical pipeline activity
const INITIAL_SEED_REQUESTS: DashboardRequest[] = [
  {
    request_id: "REQ-001",
    title: "Cloud Infrastructure Upgrade",
    amount: 45000,
    department: "engineering",
    requester: "Alice Chen",
    risk_level: "high",
    status: "approved",
    human_reviews: 2,
    created_at: "2026-10-27 10:15",
  },
  {
    request_id: "REQ-002",
    title: "Q3 Marketing Campaign",
    amount: 15000,
    department: "marketing",
    requester: "Bob Martinez",
    risk_level: "medium",
    status: "approved",
    human_reviews: 1,
    created_at: "2026-10-27 11:30",
  },
  {
    request_id: "REQ-003",
    title: "Office Supply Restock",
    amount: 2500,
    department: "operations",
    requester: "Carol White",
    risk_level: "low",
    status: "approved",
    human_reviews: 0,
    created_at: "2026-10-27 13:00",
  },
  {
    request_id: "REQ-004",
    title: "AI Research Equipment",
    amount: 85000,
    department: "research",
    requester: "David Kim",
    risk_level: "high",
    status: "approved",
    human_reviews: 2,
    created_at: "2026-10-27 14:45",
  },
  {
    request_id: "REQ-005",
    title: "Employee Training Program",
    amount: 12000,
    department: "hr",
    requester: "Eva Johnson",
    risk_level: "medium",
    status: "approved",
    human_reviews: 2,
    created_at: "2026-10-27 16:10",
  },
];

export default function Home() {
  const [activeTab, setActiveTab] = useState<"chat" | "dashboard">("chat");
  const [pipelineRequests, setPipelineRequests] = useState<DashboardRequest[]>(INITIAL_SEED_REQUESTS);

  // Synchronize with backend SQLite checkpoints across ALL browser windows
  const fetchHistory = async () => {
    try {
      const res = await fetch("/api/pipeline/history");
      if (!res.ok) return;
      const data: DashboardRequest[] = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        setPipelineRequests((prev) => {
          const map = new Map<string, DashboardRequest>();
          // Keep initial demonstration seeds
          for (const s of INITIAL_SEED_REQUESTS) {
            map.set(s.request_id, s);
          }
          // Preserve any in-memory state
          for (const p of prev) {
            map.set(p.request_id, p);
          }
          // Overlay real completed requests from the SQLite database
          for (const d of data) {
            map.set(d.request_id, {
              ...d,
              created_at: d.created_at || "Live Run",
            });
          }
          return Array.from(map.values());
        });
      }
    } catch {
      // Ignore network errors
    }
  };

  useEffect(() => {
    fetchHistory();
    const interval = setInterval(fetchHistory, 2500);
    return () => clearInterval(interval);
  }, []);

  // Synchronize with the live LangGraph agent state via CopilotKit
  const { state: agentState } = useCoAgent<{
    request_id?: string;
    title?: string;
    amount?: number;
    department?: string;
    requester?: string;
    risk_level?: string;
    status?: string;
    current_stage?: string;
    human_reviews?: number;
    decisions?: Array<{ stage: string; decision: string; reasoning?: string }>;
  }>({ name: "approval_agent" });

  // Whenever the agent completes a request (approved or rejected), record it in pipeline telemetry
  useEffect(() => {
    if (!agentState?.request_id) return;
    const finalStatus = agentState.status;

    if (finalStatus === "approved" || finalStatus === "rejected") {
      setPipelineRequests((prev) => {
        const existingIdx = prev.findIndex((r) => r.request_id === agentState.request_id);
        const updatedEntry: DashboardRequest = {
          request_id: agentState.request_id || `REQ-${Date.now()}`,
          title: agentState.title || "Untitled Request",
          amount: Number(agentState.amount) || 0,
          department: (agentState.department || "engineering") as Department,
          requester: agentState.requester || "Current User",
          risk_level: (agentState.risk_level || "low") as RiskLevel,
          status: finalStatus as ApprovalStatus,
          human_reviews: agentState.human_reviews || (agentState.decisions ? agentState.decisions.length : 0),
          created_at: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        };

        if (existingIdx >= 0) {
          const next = [...prev];
          next[existingIdx] = updatedEntry;
          return next;
        }
        return [updatedEntry, ...prev];
      });
    }
  }, [agentState?.request_id, agentState?.status]);

  // Convert pipeline requests to the format expected by RequestHistory
  const historyRequests: ApprovalResult[] = pipelineRequests.map((r) => ({
    request_id: r.request_id,
    status: r.status,
    risk_level: r.risk_level,
    decisions: [],
    total_approvals: r.status === "approved" ? 1 : 0,
    total_rejections: r.status === "rejected" ? 1 : 0,
    final_comments: "",
  }));

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header with Navigation Tabs */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 shadow-sm sticky top-0 z-30">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <span>💳</span> Financial Approval System
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              AI-powered multi-stage approval workflow with human-in-the-loop review
            </p>
          </div>

          {/* Tab Navigation */}
          <div className="flex bg-gray-100 p-1 rounded-xl border border-gray-200">
            <button
              onClick={() => setActiveTab("chat")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition ${
                activeTab === "chat"
                  ? "bg-white text-blue-600 shadow-sm"
                  : "text-gray-600 hover:text-gray-900"
              }`}
            >
              <span>💬</span> Workflow Chat
            </button>
            <button
              onClick={() => setActiveTab("dashboard")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition ${
                activeTab === "dashboard"
                  ? "bg-white text-blue-600 shadow-sm"
                  : "text-gray-600 hover:text-gray-900"
              }`}
            >
              <span>📊</span> Pipeline Dashboard
              <span className="px-1.5 py-0.5 text-xs bg-blue-100 text-blue-800 rounded-full font-bold">
                {pipelineRequests.length}
              </span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 p-4 max-w-7xl mx-auto w-full">
        {activeTab === "chat" ? (
          <div className="flex flex-col lg:flex-row gap-4">
            {/* Left Column - Chat */}
            <div className="flex-1 min-w-0">
              <div className="bg-white rounded-lg shadow-md h-[calc(100vh-160px)] overflow-hidden border border-gray-200">
                <CopilotChat
                  instructions="You are a financial approval assistant. Help users submit financial requests and guide them through the multi-stage approval workflow. When a request is submitted, process it through risk assessment, manager review, budget validation, finance review, and final sign-off. Explain each stage clearly and help users understand the approval status."
                  labels={{
                    title: "Approval Assistant",
                    initial: "Submit a financial request for approval. You can use the form on the right or describe your request here.",
                  }}
                />
              </div>
            </div>

            {/* Right Column - Controls */}
            <div className="w-full lg:w-80 space-y-4">
              <RequestForm />
              <WorkflowStatus
                currentStage={agentState?.current_stage}
                status={agentState?.status}
              />
              <RequestHistory requests={historyRequests} />
            </div>
          </div>
        ) : (
          <ApprovalDashboard
            requests={pipelineRequests}
            onClearHistory={() => setPipelineRequests([])}
          />
        )}
      </main>

      {/* Approval Panel - renders as modal overlay when interrupt fires */}
      <ApprovalPanel />
    </div>
  );
}
