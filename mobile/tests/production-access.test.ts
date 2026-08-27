import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { describe, expect, it } from "vitest";

const execFileAsync = promisify(execFile);

describe("protected production deployment access", () => {
  it("authenticates over the protected channel and reads the lightweight backend health endpoint", async () => {
    expect(process.env.AIMARKET_PRODUCTION_SSH_PASSWORD).toBeTruthy();
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
