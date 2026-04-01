import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_auth/email')({
  component: RouteComponent,
})

function RouteComponent() {
  return <div>Hello "/_auth/email"!</div>
}
