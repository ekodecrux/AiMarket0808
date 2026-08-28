import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { describe, expect, it } from "vitest";

const execFileAsync = promisify(execFile);
const productionAccessAvailable = Boolean(process.env.AIMARKET_PRODUCTION_SSH_PASSWORD);
const protectedProductionIt = productionAccessAvailable ? it : it.skip;

describe("protected production deployment access", () => {
  protectedProductionIt("authenticates over the protected channel and reads the lightweight backend health endpoint", async () => {
    const { stdout } = await execFileAsync(
      "sshpass",
      [
        "-e", "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
        "root@88.222.244.84", "curl -fsS --max-time 8 http://127.0.0.1:8035/api/",
      ],
      { env: { ...process.env, SSHPASS: process.env.AIMARKET_PRODUCTION_SSH_PASSWORD }, timeout: 25_000 },
    );
    expect(JSON.parse(stdout)).toMatchObject({ status: "online" });
  }, 35_000);
});
