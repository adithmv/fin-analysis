import { NewsDetail } from "@/components/news-detail";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <NewsDetail id={id} />;
}
