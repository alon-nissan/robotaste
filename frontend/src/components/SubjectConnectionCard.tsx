/**
 * SubjectConnectionCard — Shows QR code and URL for subject tablet connection.
 *
 * Fetches the server's LAN IP from /api/server-info and displays a QR code
 * (generated server-side by segno) that the subject can scan to open the
 * experiment on their tablet. Works fully offline — no external APIs needed.
 */

import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

interface ServerInfo {
  lan_ip: string;
  tailscale_ip: string | null;
  preferred_ip: string;
  port: number;
  subject_url: string;
  moderator_url: string;
}

export default function SubjectConnectionCard() {
  const [serverInfo, setServerInfo] = useState<ServerInfo | null>(null);
  const [error, setError] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    api.get('/server-info')
      .then(res => setServerInfo(res.data))
      .catch(() => setError(true));
  }, []);

  const handleCopy = useCallback(() => {
    if (!serverInfo) return;
    navigator.clipboard.writeText(serverInfo.subject_url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [serverInfo]);

  if (error || !serverInfo) {
    return null;
  }

  // QR code generated server-side (works offline, no external API)
  const qrUrl = `/api/server-info/qr?url=${encodeURIComponent(serverInfo.subject_url)}`;
  const isLocalhost = serverInfo.preferred_ip === '127.0.0.1';
  const usingTailscale = !!serverInfo.tailscale_ip;

  return (
    <div className="bg-surface rounded-xl border border-border p-6">
      <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-4">
        Subject Connection
      </h3>

      {isLocalhost ? (
        <div className="text-sm text-yellow-600 bg-yellow-50 rounded-lg p-3">
          ⚠️ Not connected to a network. Connect to WiFi to enable tablet access.
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4">
          {/* QR Code (server-generated SVG) */}
          <div className="bg-white p-3 rounded-lg shadow-sm">
            <img
              src={qrUrl}
              alt="QR code for subject connection"
              width={160}
              height={160}
              className="block"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = 'none';
              }}
            />
          </div>

          {/* URL display + copy button */}
          <div className="w-full text-center">
            <p className="text-xs text-text-secondary mb-1">
              Or enter this URL on the tablet:
            </p>
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-2 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 
                         rounded-lg text-sm font-mono text-text-primary transition-colors cursor-pointer"
              title="Click to copy"
            >
              {serverInfo.subject_url}
              <span className="text-xs text-text-secondary">
                {copied ? '✓ Copied' : '📋'}
              </span>
            </button>
          </div>

          <p className="text-xs text-text-secondary text-center">
            {usingTailscale
              ? '🔒 Connected via Tailscale (works through firewalls)'
              : 'Both devices must be on the same WiFi network'}
          </p>
        </div>
      )}
    </div>
  );
}
