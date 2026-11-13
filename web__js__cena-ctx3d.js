!function(){"use strict";if(!window.__cenaCtx3d){window.__cenaCtx3d=!0;var e=function(e){return document.getElementById(e)}
;"loading"===document.readyState?document.addEventListener("DOMContentLoaded",t):t()}function t(){var n=document.querySelector("#alphaCtxIaModal .c2-think")
;if(!n)return setTimeout(t,700);!function(e){if(window.THREE)return e();var t=document.createElement("script")
;t.src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js",t.onload=e,document.head.appendChild(t)}(function(){try{!function(t){
var n=window.THREE,r=matchMedia("(max-width: 760px)").matches,o=matchMedia("(prefers-reduced-motion: reduce)").matches,i='"JetBrains Mono","IBM Plex Mono",monospace',l=document.createElement("style")
;l.textContent=".ctx3d{position:relative;height:"+(r?300:370)+"px;border-radius:18px;overflow:hidden;background:#05020a;border:1px solid rgba(232,121,249,.25);box-shadow:0 18px 50px rgba(0,0,0,.45);flex:none}.ctx3d canvas{position:absolute;inset:0;width:100%;height:100%;display:block}.ctx3d .n3h{position:absolute;left:12px;right:12px;display:flex;justify-content:space-between;gap:8px;pointer-events:none}.ctx3d .n3h.t{top:12px}.ctx3d .n3h.b{bottom:12px;align-items:flex-end}.ctx3d .n3p{padding:6px 10px;border-radius:10px;background:rgba(8,3,14,.74);border:1px solid rgba(232,121,249,.3);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);font:700 11px "+i+";letter-spacing:1px;color:#f5d0fe;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:62%}.ctx3d .n3p small{display:block;font:600 9px "+i+";letter-spacing:1.2px;color:#93809e;margin-bottom:2px}.ctx3d .n3p b{font-size:16px;color:#fff}",
document.head.appendChild(l);var s=document.createElement("div");s.className="ctx3d",s.setAttribute("aria-hidden","true"),
s.innerHTML='<canvas></canvas><div class="n3h t"><div class="n3p"><small>CONFIANÇA</small><b id="n3C">—</b></div><div class="n3p"><small>DECISÃO</small><b id="n3D">—</b></div></div><div class="n3h b"><div class="n3p" id="n3Ev">REDE LENDO O CONTEXTO</div></div>',
t.parentNode.insertBefore(s,t);var d,c=s.querySelector("canvas");try{d=new n.WebGLRenderer({canvas:c,antialias:!r,alpha:!1})}catch(e){return void s.remove()}
d.setClearColor(328202,1);var p=new n.Scene;p.fog=new n.FogExp2(328202,.028);var h=new n.PerspectiveCamera(42,1,.1,200);function u(){
var e=c.getBoundingClientRect();e.width&&(d.setPixelRatio(Math.min(r?1.5:2,window.devicePixelRatio||1)),d.setSize(e.width,Math.max(1,e.height),!1),
h.aspect=e.width/Math.max(1,e.height),h.updateProjectionMatrix())}u(),window.ResizeObserver?new ResizeObserver(u).observe(c):addEventListener("resize",u)
;function v(e){var t=document.createElement("canvas");t.width=t.height=128;var a=t.getContext("2d"),r=a.createRadialGradient(64,64,0,64,64,64)
;return r.addColorStop(0,"rgba(255,255,255,1)"),r.addColorStop(.22,e),r.addColorStop(1,"rgba(0,0,0,0)"),a.fillStyle=r,a.fillRect(0,0,128,128),
new n.CanvasTexture(t)}var m=v("rgba(255,255,255,.85)");function f(e,t){var a=new n.Sprite(new n.SpriteMaterial({map:m,color:t||16777215,
blending:n.AdditiveBlending,depthWrite:!1,transparent:!0}));return a.scale.set(e,e,1),a}function x(e){var t=document.createElement("canvas");t.width=320,
t.height=72;var a=new n.CanvasTexture(t),r=new n.Sprite(new n.SpriteMaterial({map:a,transparent:!0,depthWrite:!1}));return r.userData={c:t,t:a},
r.scale.set(e,72*e/320,1),r}function w(e,t,a,n){var r=t+a;if(e.userData.k!==r){e.userData.k=r;var o=e.userData.c.getContext("2d");o.clearRect(0,0,320,72),
n||(o.fillStyle="rgba(8,3,14,.84)",o.strokeStyle=a,o.lineWidth=2,o.beginPath(),o.roundRect?o.roundRect(4,8,312,56,12):o.rect(4,8,312,56),o.fill(),o.stroke()),
o.fillStyle=n?a:"#fbeaff",o.font=(n?"800 42px ":"700 22px ")+i,o.textAlign="center",o.textBaseline="middle",o.shadowColor="rgba(0,0,0,.8)",o.shadowBlur=n?8:0,
o.fillText(t,160,37),e.userData.t.needsUpdate=!0}}p.add(new n.AmbientLight(11833297,.55));var g=new n.PointLight(15772668,2,40);g.position.set(0,6,6),p.add(g)
;var M=["RSI","MÉDIAS","BOLLINGER","VELAS"],b=[[],[],[],[]];function y(e,t,a,r){var o=new n.Mesh(new n.SphereGeometry(r,24,12),new n.MeshPhongMaterial({
color:5774471,emissive:3868516,shininess:90}));o.position.set(e,t,a),p.add(o);var i=f(4*r,15772668);return o.add(i),{m:o,g:i,p:o.position,v:.5}}
for(var E=0;E<4;E++)b[0].push(y(-6.4,1.2+1.5*E,E%2?.7:-.7,.42));for(E=0;E<6;E++)b[1].push(y(-2,1+E%3*1.9,E<3?-1.2:1.2,.28))
;for(E=0;E<4;E++)b[2].push(y(2.2,1.4+1.3*E,E%2?.8:-.8,.28));b[3].push(y(6.4,3.4,0,.95));for(var C=b[3][0],S=[],A=[],R=0;R<3;R++)b[R].forEach(function(e){
b[R+1].forEach(function(t){S.push([e,t,R]),A.push(e.p.x,e.p.y,e.p.z,t.p.x,t.p.y,t.p.z)})});var I=new n.BufferGeometry
;I.setAttribute("position",new n.Float32BufferAttribute(A,3));var P=new n.LineBasicMaterial({color:12616956,transparent:!0,opacity:.13})
;p.add(new n.LineSegments(I,P));var D=[];for(E=0;E<(r?40:70);E++){var L=f(.36,15772668);p.add(L),D.push({sp:L,e:S[Math.floor(Math.random()*S.length)],
p:Math.random(),v:.008+.012*Math.random()})}for(var B=M.map(function(e,t){var a=x(r?3.6:3.4);return a.position.set(-9.2,b[0][t].p.y,b[0][t].p.z),p.add(a),a
}),O=[],N=0;N<40;N++){var k=Math.PI/2-N/40*Math.PI*2,z=new n.Mesh(new n.BoxGeometry(.1,.26,.1),new n.MeshBasicMaterial({color:1973067}))
;z.position.set(6.4+1.6*Math.cos(k),3.4+1.6*Math.sin(k),0),z.rotation.z=k-Math.PI/2,p.add(z),O.push(z)}
var q=new n.Mesh(new n.BoxGeometry(.12,.5,.12),new n.MeshBasicMaterial({color:16498468}));p.add(q);var F=x(3);F.position.set(6.4,5.65,0),p.add(F);var H=x(3.2)
;H.material.opacity=0,p.add(H);var G=0,T=[];function U(e,t,a){var r=new n.Mesh(new n.RingGeometry(.3,.42,64),new n.MeshBasicMaterial({color:t,transparent:!0,
side:n.DoubleSide,blending:n.AdditiveBlending,depthWrite:!1}));r.position.copy(e),p.add(r),T.push({m:r,p:0,mx:a})}
var W=null,j=65,_=null,V=!1,$=0,J="",X=null,K=0,Q=0;function Y(){V=!!(window._ctxState||{}).running,j=a((e("ctxConfLabel")||{}).textContent)||65
;var n=t.querySelector(".c2-ring .c b");W=n?a(n.textContent):null,K=null===W?0:W;var r=(t.querySelector("h3")||{}).textContent||""
;_=/RISE|▲/.test(r)?"UP":/FALL|▼/.test(r)?"DOWN":null;var o=document.querySelectorAll("#alphaCtxIaModal .c2-ind");M.forEach(function(e,t){var a=o[t],n=.5,r=""
;if(a){var i=a.querySelector("p i");n=i?(parseFloat(i.style.left)||50)/100:.5,r=(a.querySelector("b")||{}).textContent||""}b[0][t].v=n,
w(B[t],e+(r&&"—"!==r?" · "+r.split(" · ")[0]:""),n>.6?"rgba(74,222,128,.7)":n<.4?"rgba(248,113,113,.7)":"rgba(251,191,36,.6)")});var i=null!==W&&_&&W>=j
;e("n3C").textContent=null===W?"—":Math.round(W)+" / mín "+j,e("n3D").textContent=V?null!==W&&_?i?"UP"===_?"▲ RISE":"▼ FALL":"ESPERAR":"ANALISANDO":"PARADO",
e("n3D").style.color=i?"UP"===_?"#4ade80":"#f87171":"";var l=(t.querySelector("p")||{}).textContent||"";l&&l.slice(0,40)!==J&&(J=l.slice(0,40),$=1)
;var s=window._ctxState||{},d=+s.trades||0,c=+s.wins||0,p=(+s.lucro||0)-(+s.perda||0);if(null!==X&&d>X.n){
var h=c>X.w,u=p-X.liq,v=(u<0?"−$":"+$")+Math.abs(u).toFixed(2);U(C.p,h?4906624:16478597,8),w(H,v,h?"#86efac":"#fda4af",!0),G=1,
e("n3Ev").textContent=(h?"GANHOU ":"PERDEU ")+v
}else $>.9?e("n3Ev").textContent="NOVA ANÁLISE DA IA":V||(e("n3Ev").textContent="INICIE O ROBÔ PARA A REDE PENSAR");X={n:d,w:c,liq:p}}setInterval(function(){
try{Y()}catch(e){}},400),Y();var Z=0,ee=r?1e3/30:0,te=o?.4:1,ae=new n.Color(4674921),ne=new n.Color;function re(t){if(requestAnimationFrame(re),
!document.hidden&&function(){var t=e("alphaCtxIaModal");if(!t)return!1;var a=getComputedStyle(t);return"none"!==a.display&&"hidden"!==a.visibility
}()&&s.offsetWidth&&!(ee&&t-Z<ee)){Z=t,Math.abs(d.domElement.width/d.getPixelRatio()-s.offsetWidth)>2&&u();var a=t/1e3*te,n=h.aspect<.9?1.5:1
;h.position.set(5*Math.sin(.09*a)*n,4.6+.5*Math.sin(.13*a),16.5*n),h.lookAt(-.4,3.4,0),b[0].forEach(function(e){var t=2*Math.abs(e.v-.5)
;e.g.material.opacity=.2+.8*t;var a=e.v>.6?4906624:e.v<.4?16281969:16498468;e.g.material.color.setHex(a),
e.m.material.emissive.setHex(a).multiplyScalar(.35+.4*t);var n=1+.4*t;e.m.scale.set(n,n,n)}),b[1].concat(b[2]).forEach(function(e,t){
e.g.material.opacity=.2+.25*Math.sin(2*a+t)+.4*$}),$>0&&($-=.008);var r=$>0?1+2*$:V?1:.35;P.opacity=.1+.15*Math.max(0,$),D.forEach(function(e){e.p+=e.v*r,
e.p>=1&&(e.p=0,e.e=S[Math.floor(Math.random()*S.length)]);var t=e.e[0].p,a=e.e[1].p;e.sp.position.set(t.x+(a.x-t.x)*e.p,t.y+(a.y-t.y)*e.p,t.z+(a.z-t.z)*e.p),
e.sp.material.opacity=Math.sin(e.p*Math.PI)*(V?1:.45)});var o=(Q+=.06*(K-Q))/100,i=null!==W&&_&&W>=j;ne.setHex(i?"UP"===_?4906624:16281969:15235577),
C.m.material.color.copy(ae).lerp(ne,Math.min(1,o+.1)),C.m.material.emissive.setHex(i?"UP"===_?1332013:8330525:3868516);var l=1+.3*o+.03*Math.sin(3*a)
;C.m.scale.set(l,l,l),C.g.material.opacity=.3+.7*o,C.g.material.color.copy(ne);var c=Math.round(40*o),v=Math.round(j/100*40);O.forEach(function(e,t){
var a=t<c?t>=v?ne.getHex():11032055:1973067;e.userData.c!==a&&(e.material.color.setHex(a),e.userData.c=a)});var m=Math.PI/2-v/40*Math.PI*2
;q.position.set(6.4+1.6*Math.cos(m),3.4+1.6*Math.sin(m),0),q.rotation.z=m-Math.PI/2,
w(F,"CONFIANÇA "+(null===W?"—":Math.round(W)),i?"rgba(74,222,128,.8)":"rgba(232,121,249,.6)"),T=T.filter(function(e){e.p+=.02;var t=1+e.p*e.mx
;return e.m.scale.set(t,t,1),e.m.lookAt(h.position),e.m.material.opacity=Math.max(0,1-e.p),!(e.p>=1)||(p.remove(e.m),e.m.geometry.dispose(),
e.m.material.dispose(),!1)}),G>0&&(G-=.007,H.material.opacity=Math.min(1,2*G),H.position.set(6.4,5+1.8*(1-G),0)),d.render(p,h)}}requestAnimationFrame(re)}(n)
}catch(e){window.console&&console.warn("cena 3D",e)}})}function a(e){var t=String(null==e?"":e).replace(",",".").match(/-?\d+(\.\d+)?/)
;return t?parseFloat(t[0]):null}}();
