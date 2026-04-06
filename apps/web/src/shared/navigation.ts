export type Mode = "service" | "dev";

export function getMode(pathname: string): Mode {
  return pathname.startsWith("/dev") ? "dev" : "service";
}

export function getModePath(mode: Mode): string {
  return mode === "dev" ? "/dev" : "/";
}
