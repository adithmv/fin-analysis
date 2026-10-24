import { ThreadDetail } from "@/components/thread-detail";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <ThreadDetail id={(await params).id} />;
}
