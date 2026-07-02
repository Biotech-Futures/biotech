import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { BRAND_NAME, BRAND_TAGLINE } from "@/lib/brand";

export function Logo() {
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton
          size="lg"
          className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground cursor-default hover:bg-transparent active:bg-transparent"
        >
          <div className="flex aspect-square size-8 items-center justify-center rounded-lg text-sidebar-primary-foreground">
            <img src="/logo.png" alt={BRAND_NAME} />
          </div>
          <div className="grid flex-1 text-left text-sm leading-tight">
            <span className="truncate font-medium">{BRAND_NAME}</span>
            <span className="truncate text-xs">{BRAND_TAGLINE}</span>
          </div>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
