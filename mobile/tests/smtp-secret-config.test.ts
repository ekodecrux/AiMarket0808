import net from "node:net";
import tls from "node:tls";
import { afterEach, describe, expect, it } from "vitest";

type LineSocket = net.Socket | tls.TLSSocket;
const openSockets: LineSocket[] = [];
const smtpCredentialsAvailable = Boolean(process.env.SMTP_USER && process.env.SMTP_PASSWORD);
const protectedSmtpIt = smtpCredentialsAvailable ? it : it.skip;

function readReply(socket: LineSocket): Promise<string> {
  return new Promise((resolve, reject) => {
    let response = "";
    const timeout = setTimeout(() => finish(new Error("SMTP response timed out")), 12_000);
    const onData = (chunk: Buffer) => {
      response += chunk.toString("utf8");
      if (/^\d{3} /m.test(response)) finish();
    };
    const onError = (error: Error) => finish(error);
    const finish = (error?: Error) => {
      clearTimeout(timeout);
      socket.off("data", onData);
      socket.off("error", onError);
      if (error) reject(error); else resolve(response);
    };
    socket.on("data", onData);
    socket.once("error", onError);
  });
}

async function command(socket: LineSocket, value: string, expected: number): Promise<void> {
  socket.write(`${value}\r\n`);
  const reply = await readReply(socket);
  expect(Number(reply.slice(0, 3))).toBe(expected);
}

async function connectSocket(): Promise<net.Socket> {
  return new Promise((resolve, reject) => {
    const socket = net.connect({ host: process.env.SMTP_HOST ?? "smtp.gmail.com", port: Number(process.env.SMTP_PORT ?? 587) });
    const timeout = setTimeout(() => reject(new Error("SMTP connection timed out")), 12_000);
    socket.once("connect", () => { clearTimeout(timeout); openSockets.push(socket); resolve(socket); });
    socket.once("error", (error) => { clearTimeout(timeout); reject(error); });
  });
}

describe("protected SMTP configuration", () => {
  afterEach(() => openSockets.splice(0).forEach((socket) => socket.destroy()));

  protectedSmtpIt("authenticates to the configured SMTP service without sending mail", async () => {
    const user = process.env.SMTP_USER;
    const password = process.env.SMTP_PASSWORD;

    const plain = await connectSocket();
    expect(Number((await readReply(plain)).slice(0, 3))).toBe(220);
    await command(plain, "EHLO aimarket.expertaitutor.com", 250);
    await command(plain, "STARTTLS", 220);
    const secure = await new Promise<tls.TLSSocket>((resolve, reject) => {
      const socket = tls.connect({ socket: plain, servername: process.env.SMTP_HOST ?? "smtp.gmail.com" }, () => { openSockets.push(socket); resolve(socket); });
      socket.once("error", reject);
    });
    await command(secure, "EHLO aimarket.expertaitutor.com", 250);
    await command(secure, "AUTH LOGIN", 334);
    await command(secure, Buffer.from(user!).toString("base64"), 334);
    await command(secure, Buffer.from(password!).toString("base64"), 235);
    await command(secure, "QUIT", 221);
  }, 40_000);
});
