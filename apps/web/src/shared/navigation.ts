export type Mode = "service" | "dev" | "design" | "stickers";

export function getMode(pathname: string): Mode {
  if (pathname === "/stickers" || pathname.startsWith("/stickers/")) return "stickers";
  if (pathname.startsWith("/design-lab")) return "design";
  return pathname.startsWith("/dev") ? "dev" : "service";
}

export function getModePath(mode: Mode): string {
  if (mode === "stickers") return "/stickers";
  if (mode === "design") return "/design-lab";
  return mode === "dev" ? "/dev" : "/";
}
