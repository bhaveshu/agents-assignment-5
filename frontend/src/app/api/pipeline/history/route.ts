import { NextResponse } from "next/server";

export async function GET() {
  const backendUrl = process.env.LANGGRAPH_DEPLOYMENT_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${backendUrl}/api/pipeline/history`, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json([]);
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json([]);
  }
}
