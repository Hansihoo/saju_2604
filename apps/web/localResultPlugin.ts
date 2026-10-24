import { readFile, realpath } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import type { Plugin } from "vite";

// Snapshots stay outside public/ and production assets. Only the dev server reads them.
export function localResultPlugin(): Plugin {
  return {
    name: "temporary-local-results",
    apply: "serve",
    configureServer(server) {
      const root = resolve(server.config.root, "../../.dev-runtime/local-results");
      server.middlewares.use(async (request, response, next) => {
        const pathname = (request.url ?? "").split("?", 1)[0];
        if (!pathname.startsWith("/__local-results/")) return next();
        response.setHeader("Cache-Control", "no-store");
        response.setHeader("X-Content-Type-Options", "nosniff");
        const address = request.socket.remoteAddress;
        if (!["127.0.0.1", "::1", "::ffff:127.0.0.1"].includes(address ?? "") ||
            request.headers["sec-fetch-site"] === "cross-site") {
          response.statusCode = 403;
          response.end("Local access only");
          return;
        }
        const match = /^\/__local-results\/([a-f0-9]{32})\.json$/.exec(pathname);
        if (!match || request.method !== "GET") {
          response.statusCode = 404;
          response.end("Result not found");
          return;
        }
        try {
          const actualRoot = await realpath(root);
          const file = await realpath(resolve(root, `${match[1]}.json`));
          if (dirname(file) !== actualRoot) throw new Error("Invalid result path");
          const contents = await readFile(file, "utf8");
          response.setHeader("Content-Type", "application/json; charset=utf-8");
          response.end(contents);
        } catch {
          response.statusCode = 404;
          response.end("Result not found");
        }
      });
    },
  };
}
