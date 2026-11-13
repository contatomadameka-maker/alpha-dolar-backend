!function(){"use strict";if(!window.__scannerPonte){window.__scannerPonte=!0;var e={simples:{n:"IA Simples"},avancado:{n:"IA Avançado",modal:"iaAvancadoModal",
abre:/iaAvancadoModal|abrirIaAvancado|IaAvancado/i},pro:{n:"IA Pro",modal:"alphaIaProModal",abre:/alphaIaProModal|abrirIaPro|IaPro\b|abrirAlphaIaPro/i},ctx:{
n:"IA Contextual",modal:"alphaCtxIaModal",abre:/alphaCtxIaModal|abrirCtxIa|CtxIa/i}},t=null;try{t=JSON.parse(localStorage.getItem("alpha_scanner_ir")||"null")
}catch(e){}if(t&&t.s&&e[t.bot]&&!(Date.now()-(t.t||0)>6e5)){try{localStorage.removeItem("alpha_scanner_ir")}catch(e){}var a=e[t.bot],n=t.nome||t.s
;"loading"===document.readyState?document.addEventListener("DOMContentLoaded",function(){setTimeout(s,800)}):setTimeout(s,800)}}function o(e){
return document.getElementById(e)}function r(e){var t=(e=String(e||"")).match(/1HZ(\d+)/i)||e.match(/R_(\d+)/i)||e.match(/(\d+)/)
;return(t?t[1]:"")+(/1s|1HZ/i.test(e)?"s":"")}function i(e){if(!e||!e.options)return!1;var a=Array.prototype.filter.call(e.options,function(e){
return e.value===t.s})[0];if(!a){var n=r(t.s);a=Array.prototype.filter.call(e.options,function(e){
return r(e.value)===n||r(e.textContent)===n&&/vol/i.test(e.textContent)})[0]}return!!a&&(e.value=a.value,["input","change"].forEach(function(t){try{
e.dispatchEvent(new Event(t,{bubbles:!0}))}catch(e){}}),!0)}function c(){try{if("simples"===t.bot||"avancado"===t.bot){var e=n.replace(/\s*Index$/i,"")+" Index"
;return"function"==typeof window.selectMarketGlobal?window.selectMarketGlobal({symbol:t.s,id:t.s,name:e
}):(window.selectedMarketSymbol=window.selectedSymbol=t.s,window.selectedMarketName=e,o("selectedMarket")&&(o("selectedMarket").innerText=e)),
"avancado"===t.bot&&o("advSelectedMarket")&&(o("advSelectedMarket").innerText=e),!0}if("pro"===t.bot)return i(o("proSymbol"))
;if("ctx"===t.bot)return i(o("ctxMercado"))}catch(e){}return!1}function l(e){var t=document.createElement("style")
;t.textContent='.scp-av{position:fixed;left:50%;bottom:calc(18px + env(safe-area-inset-bottom,0px));transform:translateX(-50%);z-index:99999;display:flex;align-items:center;gap:10px;flex-wrap:wrap;justify-content:center;max-width:calc(100vw - 32px);padding:10px 12px 10px 14px;border-radius:14px;background:rgba(6,12,9,.94);border:1px solid #1F6B4A;box-shadow:0 18px 50px rgba(0,0,0,.55),0 0 24px rgba(74,222,154,.18);color:#E9FFF4;font:500 13px/1.4 "IBM Plex Sans",system-ui,sans-serif}.scp-av b{color:#9FF0C8}.scp-av button{min-height:36px;border-radius:10px;border:0;cursor:pointer;font:700 12px "Chakra Petch",system-ui,sans-serif;letter-spacing:.1em;padding:0 12px}.scp-av .ab{background:linear-gradient(180deg,#1F8A5B,#146B45);color:#E9FFF4}.scp-av .x{background:transparent;color:#ADA795;font-size:16px;padding:0 6px}',
document.head.appendChild(t);var o=document.createElement("div");o.className="scp-av",o.setAttribute("role","status"),
o.innerHTML="<span>📡 "+(e?"Mercado do Scanner no <b></b>: ":"Não consegui selecionar no <b></b>. Escolha manualmente: ")+'<b class="m"></b></span>',
o.querySelector("b").textContent=a.n,o.querySelector(".m").textContent=n;var r=function(){if(!a.abre)return null
;var e=Array.prototype.filter.call(document.querySelectorAll("[onclick],a[href]"),function(e){
var t=(e.getAttribute("onclick")||"")+" "+(e.getAttribute("href")||"");return a.abre.test(t)&&!(a.modal&&e.closest("#"+a.modal))&&!/fechar|close/i.test(t)})
;return e.filter(function(e){return e.offsetParent})[0]||e[0]||null}();if(r){var i=document.createElement("button");i.type="button",i.className="ab",
i.textContent="ABRIR "+a.n.toUpperCase(),i.onclick=function(){try{r.click()}catch(e){}setTimeout(c,400),o.remove()},o.appendChild(i)}
var l=document.createElement("button");l.type="button",l.className="x",l.setAttribute("aria-label","Fechar"),l.textContent="✕",l.onclick=function(){o.remove()},
o.appendChild(l),document.body.appendChild(o),setTimeout(function(){o.parentNode&&o.remove()},15e3)}function s(){var e=0;!function t(){var n=c()
;if(!n&&e++<10)return setTimeout(t,500);l(n),function(){var e=a.modal&&o(a.modal);if(e&&window.MutationObserver){var t=!1,n=new MutationObserver(function(){
if(!t){var a=getComputedStyle(e);"none"!==a.display&&"hidden"!==a.visibility&&(t=!0,setTimeout(c,350),setTimeout(c,1200),setTimeout(function(){n.disconnect()
},1500))}});n.observe(e,{attributes:!0,attributeFilter:["style","class"]})}}()}()}}();
