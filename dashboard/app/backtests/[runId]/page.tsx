import { Backtests } from "@/components/backtests";
export default async function Page({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  return <Backtests runId={runId} />;
}
