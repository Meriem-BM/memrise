import { MemoryDetailPanel } from "@/features/memories/memory-detail-panel";

type Props = {
  params: Promise<{ id: string }>;
};

export default async function MemoryDetailPage({ params }: Props) {
  const { id } = await params;
  return <MemoryDetailPanel memoryId={id} />;
}
