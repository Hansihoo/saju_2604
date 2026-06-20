export type Mode = "service" | "dev" | "design";

export function getMode(pathname: string): Mode {
  if (pathname.startsWith("/design-lab")) return "design";
  return pathname.startsWith("/dev") ? "dev" : "service";
}

export function getModePath(mode: Mode): string {
  if (mode === "design") return "/design-lab";
  return mode === "dev" ? "/dev" : "/";
}
