/* SOM-ALPHA-V2 — som de ganho confiavel em todos os bots e navegadores */
(function () {
  if (window.AlphaSom) return;
  var LOCAL = '/sounds/cash-register.mp3';
  var DCB = LOCAL;
  var AC = window.AudioContext || window.webkitAudioContext;
  var outros = [];
  if (AC) {
    var W = function (o) { var c = o ? new AC(o) : new AC(); outros.push(c); return c; };
    W.prototype = AC.prototype;
    try { window.AudioContext = W; if (window.webkitAudioContext) window.webkitAudioContext = W; } catch (e) {}
  }
  try { if (navigator.audioSession) navigator.audioSession.type = 'playback'; } catch (e) {}

  var origPlay = HTMLMediaElement.prototype.play;
  var ctx = null;
  function getCtx() { if (!ctx && AC) { try { ctx = new AC(); } catch (e) {} } return ctx; }
  function rodando() { return ctx && ctx.state === 'running'; }

  /* ---- sons do proprio site: Web Audio com buffer decodificado ---- */
  var buffers = {}, ruins = {};
  function carregar(url) {
    if (ruins[url]) return Promise.reject(new Error('ruim'));
    if (buffers[url]) return buffers[url];
    var c = getCtx();
    if (!c) return Promise.reject(new Error('sem audio'));
    buffers[url] = fetch(url, { cache: 'force-cache' })
      .then(function (r) {
        if (!r.ok) throw new Error('http ' + r.status);
        var t = r.headers.get('content-type') || '';
        if (t && !/audio|octet/i.test(t)) throw new Error('nao e audio');
        return r.arrayBuffer();
      })
      .then(function (ab) { return new Promise(function (ok, ko) { c.decodeAudioData(ab, ok, ko); }); })
      .catch(function (e) { ruins[url] = 1; delete buffers[url]; throw e; });
    return buffers[url];
  }
  function tocarBuffer(buf, vol) {
    var c = getCtx();
    var s = c.createBufferSource(), g = c.createGain();
    s.buffer = buf; g.gain.value = (vol == null ? 1 : vol);
    s.connect(g); g.connect(c.destination); s.start(0);
  }

  /* ---- sons de outros sites (ex: DC Bots): copias pre-carregadas e liberadas ---- */
  var pools = {};
  function pool(u) {
    var p = pools[u];
    if (!p) {
      p = pools[u] = { els: [], i: 0 };
      for (var k = 0; k < 3; k++) {
        var a = new Audio();
        a.preload = 'auto'; a.src = u;
        try { a.load(); } catch (e) {}
        p.els.push(a);
      }
    }
    return p;
  }
  function primar() {
    Object.keys(pools).forEach(function (u) {
      pools[u].els.forEach(function (a) {
        if (a.__primado || a.__primando) return;
        a.__primando = 1; a.muted = true;
        var r = origPlay.call(a);
        var fim = function () { try { a.pause(); a.currentTime = 0; } catch (e) {} a.muted = false; a.__primando = 0; };
        if (r && r.then) r.then(function () { fim(); a.__primado = 1; }).catch(fim); else fim();
      });
    });
  }
  function tocarPool(u, vol) {
    var p = pool(u);
    var a = p.els[p.i++ % p.els.length];
    try { a.pause(); a.currentTime = 0; } catch (e) {}
    a.muted = false; a.volume = (vol == null ? 1 : vol);
    return origPlay.call(a);
  }

  /* ---- reserva: ka-ching sintetizado ---- */
  function synth() {
    var c = getCtx();
    if (!c || c.state !== 'running') return false;
    var t = c.currentTime;
    [[1318, 0], [1760, 0.08], [2637, 0.08]].forEach(function (n) {
      var o = c.createOscillator(), g = c.createGain();
      o.type = 'triangle'; o.frequency.value = n[0];
      g.gain.setValueAtTime(0.0001, t + n[1]);
      g.gain.exponentialRampToValueAtTime(0.3, t + n[1] + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, t + n[1] + 0.5);
      o.connect(g); g.connect(c.destination);
      o.start(t + n[1]); o.stop(t + n[1] + 0.55);
    });
    return true;
  }

  /* ---- aviso quando o navegador bloqueia ---- */
  var pill = null;
  function avisar() {
    if (pill || !document.body) return;
    pill = document.createElement('button');
    pill.type = 'button';
    pill.textContent = '🔇 Toque aqui para ativar o som dos ganhos';
    pill.style.cssText = 'position:fixed;left:50%;transform:translateX(-50%);bottom:calc(88px + env(safe-area-inset-bottom,0px));z-index:2147483600;background:#f5c542;color:#111;border:0;border-radius:999px;padding:10px 16px;font:700 13px system-ui,sans-serif;box-shadow:0 6px 20px rgba(0,0,0,.45);cursor:pointer;max-width:calc(100vw - 32px)';
    pill.addEventListener('click', function () { desbloquear(); setTimeout(tocarGanho, 150); });
    document.body.appendChild(pill);
  }
  function tirarAviso() { if (pill) { pill.remove(); pill = null; } }

  function desbloquear() {
    var c = getCtx();
    if (c) {
      try { if (c.state !== 'running') c.resume(); } catch (e) {}
      try { var b = c.createBuffer(1, 1, 22050), s = c.createBufferSource(); s.buffer = b; s.connect(c.destination); s.start(0); } catch (e) {}
    }
    outros.forEach(function (x) { try { if (x.state !== 'running') x.resume(); } catch (e) {} });
    primar();
    carregar(LOCAL).catch(function () {});
    setTimeout(function () { if (rodando()) tirarAviso(); }, 250);
  }
  ['pointerdown', 'touchend', 'click', 'keydown'].forEach(function (ev) {
    window.addEventListener(ev, desbloquear, { capture: true, passive: true });
  });
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) return;
    try { if (ctx && ctx.state !== 'running') ctx.resume(); } catch (e) {}
    outros.forEach(function (x) { try { if (x.state !== 'running') x.resume(); } catch (e) {} });
  });

  /* ---- intercepta o play() de todos os bots ---- */
  function info(el) {
    if (!(el instanceof HTMLAudioElement) || el.loop || el.__alphaPool) return null;
    var u = el.src || el.currentSrc;
    if (!u || !/^data:audio|\.(mp3|wav|ogg|m4a|aac)(\?|#|$)/i.test(u)) return null;
    if (/^data:/.test(u)) return { u: u, fora: false };
    try { return { u: u, fora: new URL(u, location.href).origin !== location.origin }; } catch (e) { return null; }
  }
  function falhou() { if (!synth()) avisar(); }

  HTMLMediaElement.prototype.play = function () {
    var el = this, args = arguments, s = null;
    try { s = info(el); } catch (e) {}
    if (s) {
      var vol = el.muted ? 0 : el.volume;
      if (s.fora) {
        var r = tocarPool(s.u, vol);
        return (r && r.catch) ? r.catch(falhou) : Promise.resolve();
      }
      if (getCtx() && !ruins[s.u]) {
        try { if (ctx.state !== 'running') ctx.resume(); } catch (e) {}
        return carregar(s.u).then(function (buf) {
          if (!rodando()) throw new Error('bloqueado');
          tocarBuffer(buf, vol);
        }).catch(function () {
          var p2 = origPlay.apply(el, args);
          return (p2 && p2.catch) ? p2.catch(falhou) : Promise.resolve();
        });
      }
    }
    var p = origPlay.apply(el, args);
    if (p && p.catch) p.catch(function (err) { if (err && err.name === 'NotAllowedError') avisar(); });
    return p;
  };

  /* ---- som de ganho direto: proprio > DC Bots > sintetizado ---- */
  function tocarGanho() {
    return carregar(LOCAL).then(function (b) {
      if (!rodando()) throw new Error('bloqueado');
      tocarBuffer(b, 1);
    }).catch(function () {
      var r = tocarPool(DCB, 1);
      if (r && r.catch) return r.catch(falhou);
    });
  }

  pool(DCB);
  window.AlphaSom = { ganho: tocarGanho, desbloquear: desbloquear, testar: tocarGanho };
})();
