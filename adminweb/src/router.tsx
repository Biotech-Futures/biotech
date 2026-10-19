import { createRouter, Link } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";

export const router = createRouter({
  routeTree,
  context: {
    auth: undefined!,
  },
  defaultViewTransition: true,
  // Silences TanStack Router's warning about the generic <p>Not Found</p>
  // fallback and gives users something reasonable when they hit a stale link
  // or a route that never existed.
  defaultNotFoundComponent: () => (
    <div className="p-8 space-y-2">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="text-sm text-muted-foreground">
        The URL you tried doesn't match any known route.
      </p>
      <Link to="/" className="text-sm text-primary underline">
        Go home
      </Link>
    </div>
  ),
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
