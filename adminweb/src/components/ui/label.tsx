import * as React from "react"
import { Label as LabelPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

function Label({
  className,
  children,
  requiredMarker,
  ...props
}: React.ComponentProps<typeof LabelPrimitive.Root> & {
  requiredMarker?: boolean
}) {
  return (
    <LabelPrimitive.Root
      data-slot="label"
      className={cn(
        "flex items-center gap-2 text-sm leading-none font-medium select-none group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50 peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        className
      )}
      {...props}
    >
      {children}
      {requiredMarker ? (
        <span aria-hidden="true" className="-ml-1 text-destructive">
          *
        </span>
      ) : null}
    </LabelPrimitive.Root>
  )
}

export { Label }
