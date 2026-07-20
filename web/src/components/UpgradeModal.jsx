import { useEffect, useState } from "react";
import { redeem, setLicense, WALLET_ADDRESS, PRICE_USDC } from "../lib/license.js";

// In-page Pro checkout. Same rails as GRID Store: pay USDC on Base to the store
// wallet, then verify on-chain via the grid-store worker (which records the sale
// in your Supabase and mints the license). Never leaves the app.
export default function UpgradeModal({ onClose, onActivated }) {
  const [step, setStep] = useState(1); // 1 = pay, 2 = verify, 3 = done
  const [email, setEmail] = useState("");
  const [txHash, setTxHash] = useState("");
  const [status, setStatus] = useState("idle"); // idle | verifying | error
  const [message, setMessage] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const copy = () => {
    navigator.clipboard.writeText(WALLET_ADDRESS);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  async function verify() {
    if (!email.trim() || !txHash.trim()) {
      setMessage("Enter your email and the transaction hash.");
      return;
    }
    setStatus("verifying");
    setMessage("");
    try {
      const data = await redeem({ email, txHash });
      setLicense(data.token);
      setStep(3);
      onActivated?.();
    } catch (e) {
      setStatus("error");
      setMessage(e.message || "Could not verify the payment. Check the hash and retry.");
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>✕</button>

        <div className="modal-head">
          <span className="badge cat-crypto">USDC · Base</span>
          <h2 className="nomargin">CTF Flashcards Pro</h2>
          <div className="price">{PRICE_USDC} <span>USDC / 31 days</span></div>
          <p className="muted small nomargin">Unlimited puzzle solves. Renew anytime by paying again.</p>
        </div>

        {step === 1 && (
          <div className="stack">
            <ol className="steps small">
              <li>Open a Base-compatible wallet (Coinbase Wallet, MetaMask…).</li>
              <li><strong>Switch to the Base network</strong> — not Ethereum mainnet.</li>
              <li>Send exactly <strong>{PRICE_USDC} USDC</strong> to:</li>
            </ol>
            <div className="address-block">
              <code className="address">{WALLET_ADDRESS}</code>
              <button onClick={copy}>{copied ? "✓ Copied" : "Copy"}</button>
            </div>
            <p className="hint-box small">⚠ Send USDC on <strong>Base</strong> only. Sending on Ethereum mainnet loses the funds.</p>
            <button className="primary" onClick={() => setStep(2)}>I've sent the payment →</button>
          </div>
        )}

        {step === 2 && (
          <div className="stack">
            <p className="muted small">
              Paste your transaction hash and an email for the receipt. We verify the payment
              on Base and unlock Pro instantly.
            </p>
            <label>Email
              <input type="email" placeholder="you@example.com" value={email}
                onChange={(e) => setEmail(e.target.value)} />
            </label>
            <label>Transaction hash
              <input type="text" placeholder="0x… tx hash" value={txHash}
                onChange={(e) => setTxHash(e.target.value)} className={status === "error" ? "shake" : ""} />
            </label>
            {message && <p className="wrong-msg">{message}</p>}
            <button className="primary" onClick={verify} disabled={status === "verifying"}>
              {status === "verifying" ? "Verifying on-chain…" : "Verify & unlock Pro"}
            </button>
            <a className="link" href={`https://basescan.org/address/${WALLET_ADDRESS}`}
              target="_blank" rel="noopener noreferrer">Find your tx hash on BaseScan ↗</a>
          </div>
        )}

        {step === 3 && (
          <div className="success">
            <h3 className="nomargin">🎉 Pro unlocked</h3>
            <p className="muted small">
              Payment verified for <strong>{email}</strong>. Unlimited puzzle solves are on for 31 days.
              Your license is saved on this device.
            </p>
            <button className="primary" onClick={onClose}>Start solving</button>
          </div>
        )}
      </div>
    </div>
  );
}
