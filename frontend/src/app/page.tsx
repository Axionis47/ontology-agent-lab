import { Suspense } from "react";
import { Workspace } from "@/features/workspace/workspace";

export default function Page() {
  return (
    <Suspense
      fallback={<p className="p-10 text-muted-foreground">Opening Oak...</p>}
    >
      <Workspace />
    </Suspense>
  );
}
