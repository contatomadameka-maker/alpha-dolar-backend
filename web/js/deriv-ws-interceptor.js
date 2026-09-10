(function() {
    const ORI_WS = window.WebSocket;
    const APP_ID = '34lv1PuWzjElEuwWcDLyr';
    let otpCache = {};

    function getAccountId() {
        try {
            const contas = JSON.parse(localStorage.getItem('deriv_accounts') || '[]');
            const tipo = localStorage.getItem('deriv_conta_ativa') || 'demo';
            return (contas.find(c => Boolean(c.isDemo) === (tipo === 'demo')) || contas[0])?.acct;
        } catch { return null; }
    }

    async function getOTP(accountId) {
        const bearer = localStorage.getItem('deriv_bearer_token');
        if (!bearer || !accountId) return null;
        // Cache por 90s mas cada URL só pode ser usada UMA VEZ
        // Então não cachear - sempre gerar novo
        try {
            const res = await fetch(
                `https://api.derivws.com/trading/v1/options/accounts/${accountId}/otp`,
                { method: 'POST',
                  headers: { 'Authorization': 'Bearer ' + bearer,
                             'Content-Type': 'application/json',
                             'Deriv-App-ID': APP_ID },
                  body: '{}' }
            );
            const d = await res.json();
            return d?.data?.url || null;
        } catch { return null; }
    }

    window.getDerivOTP = getOTP;
    window.getDerivAccountId = getAccountId;

    function DerivWS(url, protocols) {
        const bearer = localStorage.getItem('deriv_bearer_token');
        if (bearer && url && url.includes('ws.derivws.com')) {
            const accountId = getAccountId();
            // Cria WebSocket real via OTP
            let ws = null;
            const queue = [];
            const evts = {};

            const attach = (realWs) => {
                ws = realWs;
                ['onopen','onmessage','onerror','onclose'].forEach(k => {
                    if (evts[k]) realWs[k] = evts[k];
                });
                realWs.addEventListener('open', () => {
                    queue.splice(0).forEach(m => realWs.send(m));
                });
            };

            getOTP(accountId).then(otpUrl => {
                attach(otpUrl ? new ORI_WS(otpUrl) : new ORI_WS(url, protocols));
            });

            return new Proxy({}, {
                get(_, p) {
                    if (p === 'send') return m => ws?.readyState === 1 ? ws.send(m) : queue.push(m);
                    if (p === 'close') return () => ws?.close();
                    if (p === 'readyState') return ws?.readyState ?? 0;
                    if (['onopen','onmessage','onerror','onclose'].includes(p)) return evts[p];
                    if (p === 'addEventListener') return (e,f) => { evts[e]=f; ws?.addEventListener(e,f); };
                    return ws?.[p];
                },
                set(_, p, v) {
                    if (['onopen','onmessage','onerror','onclose'].includes(p)) {
                        evts[p] = v;
                        if (ws) ws[p] = v;
                    }
                    return true;
                }
            });
        }
        return new ORI_WS(url, protocols);
    }

    DerivWS.CONNECTING = 0; DerivWS.OPEN = 1;
    DerivWS.CLOSING = 2; DerivWS.CLOSED = 3;
    window.WebSocket = DerivWS;
    console.log('✅ Deriv WS Interceptor ativo');
})();
