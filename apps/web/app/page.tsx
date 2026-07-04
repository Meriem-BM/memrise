import { highlightAll } from "@/features/sdk/highlight";
import { SdkPage } from "@/features/sdk/sdk-page";
import { HERO_TABS, INSTALL, SNIPPETS } from "@/features/sdk/snippets";

export default async function HomePage() {
  const highlighted = await highlightAll([...HERO_TABS, INSTALL, ...SNIPPETS]);
  return <SdkPage highlighted={highlighted} />;
}
