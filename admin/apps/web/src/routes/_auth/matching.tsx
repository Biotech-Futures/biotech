import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_auth/matching')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/_auth/matching"!</div>
}
