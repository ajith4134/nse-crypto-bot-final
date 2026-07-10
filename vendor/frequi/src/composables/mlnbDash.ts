// mlnb shared composable (BN-U2/U3, 2026-07-10) — MLNetworkBrain dashboard base-URL
// discovery + JSON reads for the native brain views (Mission Control, Pro Terminal).
// Same discovery chain as BrainControlView: the dashboard's tunnel URL rotates per
// launch, so the deployed overlay file `mlnb_status.json` (same-origin, written by the
// dashboard deploy) is the source of truth; localStorage caches the last good value and
// the hardcoded default is only the first-boot fallback. Readers get `null` on any
// failure so panels render an honest "dashboard unreachable" state — never fake data.
import { ref } from 'vue';

const DASH_KEY = 'mlnb_dashboard_url';
const DEFAULT_DASH = 'https://between-payroll-postal-glossary.trycloudflare.com';

const dashUrl = ref<string>(localStorage.getItem(DASH_KEY) || DEFAULT_DASH);
let synced = false;

async function syncDashUrl(): Promise<void> {
  try {
    // Resolve against the app base (/frequi/ behind the Caddy gateway) — a site-root
    // fetch at :8100 gets the dashboard SPA's HTML fallback, not this overlay.
    const r = await fetch(`${import.meta.env.BASE_URL}mlnb_status.json?t=${Date.now()}`);
    const j = await r.json();
    const u = String(j?.dashboard_url || '').replace(/\/$/, '');
    if (u && u !== dashUrl.value) {
      dashUrl.value = u;
      localStorage.setItem(DASH_KEY, u);
    }
  } catch {
    /* overlay not deployed yet — keep localStorage/default fallback */
  }
}

/** GET `${dashUrl}${path}` as JSON; null on any failure (honest empty state). */
async function dashJson(path: string): Promise<any | null> {
  try {
    const r = await fetch(`${dashUrl.value}${path}`);
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

export function useMlnbDash() {
  if (!synced) {
    synced = true;
    syncDashUrl();
  }
  return { dashUrl, syncDashUrl, dashJson };
}
