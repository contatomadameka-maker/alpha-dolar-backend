!function(){"use strict";if(!window.__cenaPro3d){window.__cenaPro3d=!0;var e=function(e){return document.getElementById(e)},t={baixo_risco:70,preciso:60,
balanceado:52,veloz:45},a={DIGITEVEN:"PAR",DIGITODD:"ÍMPAR",DIGITOVER:"OVER",DIGITUNDER:"UNDER",DIGITMATCH:"MATCH",DIGITDIFF:"DIFF",CALL:"RISE",PUT:"FALL"}
;"loading"===document.readyState?document.addEventListener("DOMContentLoaded",n):n()}function n(){var r=document.querySelector("#alphaIaProModal .p2-lead")
;if(!r)return setTimeout(n,700);!function(e){if(window.THREE)return e();var t=document.createElement("script")
;t.src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js",t.onload=e,document.head.appendChild(t)}(function(){try{!function(n){
var r=window.THREE,o=matchMedia("(max-width: 760px)").matches,i=matchMedia("(prefers-reduced-motion: reduce)").matches,s='"JetBrains Mono","IBM Plex Mono",monospace',l=document.createElement("style")
;l.textContent=".pro3d{position:relative;height:"+(o?300:380)+"px;margin-bottom:12px;border-radius:18px;overflow:hidden;background:#04030a;border:1px solid rgba(167,139,250,.25);box-shadow:0 18px 50px rgba(0,0,0,.45)}.pro3d canvas{position:absolute;inset:0;width:100%;height:100%;display:block}.pro3d .q3h{position:absolute;left:12px;right:12px;display:flex;justify-content:space-between;gap:8px;pointer-events:none}.pro3d .q3h.t{top:12px}.pro3d .q3h.b{bottom:12px;align-items:flex-end}.pro3d .q3p{padding:6px 10px;border-radius:10px;background:rgba(6,4,14,.74);border:1px solid rgba(167,139,250,.3);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);font:700 11px "+s+";letter-spacing:1px;color:#ddd6fe;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:62%}.pro3d .q3p small{display:block;font:600 9px "+s+";letter-spacing:1.2px;color:#8b87a8;margin-bottom:2px}.pro3d .q3p b{font-size:16px;color:#fff}.pro3d .q3p.ok{border-color:#4ade80;color:#bbf7d0}",
document.head.appendChild(l);var d=document.createElement("div");d.className="pro3d",d.setAttribute("aria-hidden","true"),
d.innerHTML='<canvas></canvas><div class="q3h t"><div class="q3p" id="q3S"><small>SCORE</small><b>—</b></div><div class="q3p" id="q3C"><small>CONSENSO</small><b>—</b></div></div><div class="q3h b"><div class="q3p" id="q3Ev">TRÊS NÚCLEOS LENDO OS DÍGITOS</div><div class="q3p"><small>CONTRATO</small><b id="q3T">—</b></div></div>',
n.parentNode.insertBefore(d,n);var c,p=d.querySelector("canvas");try{c=new r.WebGLRenderer({canvas:p,antialias:!o,alpha:!1})}catch(e){return void d.remove()}
c.setClearColor(262922,1);var h=new r.Scene;h.fog=new r.FogExp2(262922,.03);var u=new r.PerspectiveCamera(42,1,.1,200);function m(){
var e=p.getBoundingClientRect();e.width&&(c.setPixelRatio(Math.min(o?1.5:2,window.devicePixelRatio||1)),c.setSize(e.width,Math.max(1,e.height),!1),
u.aspect=e.width/Math.max(1,e.height),u.updateProjectionMatrix())}m(),window.ResizeObserver?new ResizeObserver(m).observe(p):addEventListener("resize",m)
;function v(e){var t=document.createElement("canvas");t.width=t.height=128;var a=t.getContext("2d"),n=a.createRadialGradient(64,64,0,64,64,64)
;return n.addColorStop(0,"rgba(255,255,255,1)"),n.addColorStop(.22,e),n.addColorStop(1,"rgba(0,0,0,0)"),a.fillStyle=n,a.fillRect(0,0,128,128),
new r.CanvasTexture(t)}var f=v("rgba(255,255,255,.85)");function w(e,t){var a=new r.Sprite(new r.SpriteMaterial({map:f,color:t||16777215,
blending:r.AdditiveBlending,depthWrite:!1,transparent:!0}));return a.scale.set(e,e,1),a}function b(e){var t=document.createElement("canvas");t.width=320,
t.height=72;var a=new r.CanvasTexture(t),n=new r.Sprite(new r.SpriteMaterial({map:a,transparent:!0,depthWrite:!1}));return n.userData={c:t,t:a},
n.scale.set(e,72*e/320,1),n}function M(e,t,a,n){var r=t+a;if(e.userData.k!==r){e.userData.k=r;var o=e.userData.c.getContext("2d");o.clearRect(0,0,320,72),
n||(o.fillStyle="rgba(6,4,14,.84)",o.strokeStyle=a,o.lineWidth=2,o.beginPath(),o.roundRect?o.roundRect(4,8,312,56,12):o.rect(4,8,312,56),o.fill(),o.stroke()),
o.fillStyle=n?a:"#f1edff",o.font=(n?"800 42px ":"700 23px ")+s,o.textAlign="center",o.textBaseline="middle",o.shadowColor="rgba(0,0,0,.8)",o.shadowBlur=n?8:0,
o.fillText(t,160,37),e.userData.t.needsUpdate=!0}}h.add(new r.AmbientLight(10194897,.55));var g=new r.PointLight(14208255,2.2,40);g.position.set(0,7,0),h.add(g)
;for(var x=1;x<=5;x++){var y=new r.Mesh(new r.RingGeometry(1.8*x-.02,1.8*x+.02,128),new r.MeshBasicMaterial({color:7166928,transparent:!0,opacity:3===x?.38:.13,
side:r.DoubleSide}));y.rotation.x=-Math.PI/2,h.add(y)}var E=new r.Vector3(0,3,0),C=[{a:"PAR",b:"ÍMPAR",ca:2282478,cb:16020150,base:.5},{a:"OVER 4",b:"UNDER 5",
ca:10980346,cb:16498468,base:.5},{a:"MATCH",b:"DIFF",ca:4906624,cb:9741240,base:.1}];C.forEach(function(e,t){var a=-Math.PI/2+t/3*Math.PI*2,n=new r.Group
;n.position.set(5.4*Math.cos(a),2.6,5.4*Math.sin(a)),h.add(n),e.g=n,e.pa=e.base,e.f=0,e.mat=new r.MeshPhongMaterial({color:9144232,emissive:3018853,
emissiveIntensity:.5,shininess:100,transparent:!0,opacity:.9}),e.sf=new r.Mesh(new r.SphereGeometry(.8,32,16),e.mat),n.add(e.sf),e.gl=w(3,12891645),n.add(e.gl),
e.r1=new r.Mesh(new r.TorusGeometry(1.25,.03,8,80),new r.MeshBasicMaterial({color:12891645,transparent:!0,opacity:.55})),e.r1.rotation.x=1.2,n.add(e.r1),
e.r2=new r.Mesh(new r.TorusGeometry(1.5,.02,8,80),new r.MeshBasicMaterial({color:12891645,transparent:!0,opacity:.3})),e.r2.rotation.set(.4,.9,0),n.add(e.r2)
;for(var i=[],s=0;s<36;s++){var l=s/36*Math.PI*2;i.push(1.85*Math.cos(l),0,1.85*Math.sin(l))}var d=new r.BufferGeometry
;d.setAttribute("position",new r.Float32BufferAttribute(i,3)),e.op=new r.Points(d,new r.PointsMaterial({color:12891645,size:.09,transparent:!0,opacity:.8,
blending:r.AdditiveBlending,depthWrite:!1})),n.add(e.op),e.agM=new r.MeshBasicMaterial({color:e.ca}),e.ag=new r.Mesh(new r.ConeGeometry(.24,.8,16),e.agM),
e.ag.position.y=1.6,n.add(e.ag),e.lb=b(o?4.2:3.8),e.lb.position.y=2.6,n.add(e.lb),
e.ln=new r.Line((new r.BufferGeometry).setFromPoints([n.position.clone(),E.clone()]),new r.LineBasicMaterial({color:12891645,transparent:!0,opacity:.12})),
h.add(e.ln)});var S=new r.Group;S.position.copy(E),h.add(S);var A=new r.TetrahedronGeometry(1.25,0),R=new r.MeshPhongMaterial({color:4988309,emissive:3018853,
transparent:!0,opacity:.5,shininess:120,side:r.DoubleSide});S.add(new r.Mesh(A,R)),S.add(new r.LineSegments(new r.EdgesGeometry(A),new r.LineBasicMaterial({
color:15324671})));var I=w(4,12891645);S.add(I);var T=b(3.6);T.position.set(0,5.6,0),h.add(T)
;var q=new r.Mesh(new r.CylinderGeometry(.22,.22,1,16,1,!0),new r.MeshBasicMaterial({color:4906624,transparent:!0,opacity:0,blending:r.AdditiveBlending,
depthWrite:!1,side:r.DoubleSide}));h.add(q);var P=b(3.2);P.material.opacity=0,h.add(P)
;for(var D=0,O=[],B=0;B<(o?200:420);B++)O.push(24*(Math.random()-.5),11*Math.random(),24*(Math.random()-.5));var G=new r.BufferGeometry
;G.setAttribute("position",new r.Float32BufferAttribute(O,3));var N=new r.Points(G,new r.PointsMaterial({color:14208255,size:.05,transparent:!0,opacity:.5,
blending:r.AdditiveBlending,depthWrite:!1}));h.add(N);var L=[],F=[],H=null,z=!1,k=!1,U=!1,W=null;function _(e,t,a){
var n=new r.Mesh(new r.RingGeometry(.3,.42,64),new r.MeshBasicMaterial({color:t,transparent:!0,side:r.DoubleSide,blending:r.AdditiveBlending,depthWrite:!1}))
;n.position.copy(e),h.add(n),F.push({m:n,p:0,mx:a})}function j(e){C.forEach(function(t){var a=new Float32Array(3*26),n=new r.BufferGeometry
;n.setAttribute("position",new r.BufferAttribute(a,3));var o=new r.Points(n,new r.PointsMaterial({color:e,size:.15,transparent:!0,blending:r.AdditiveBlending,
depthWrite:!1}));h.add(o),L.push({n:t,pt:o,arr:a,p:0,cor:e})})}function V(e){var t=String(null==e?"":e).replace(",",".").match(/-?\d+(\.\d+)?/)
;return t?parseFloat(t[0]):null}function Y(){var n=window._proState||{};U=!!n.running;var r=(n.digits||[]).map(Number).filter(function(e){return!isNaN(e)
}).slice(-20),o=r.length;if(o){var i=r[o-1];C[0].pa=r.filter(function(e){return e%2==0}).length/o,C[1].pa=r.filter(function(e){return e>4}).length/o,
C[2].pa=r.filter(function(e){return e===i}).length/o,C[2].a="MATCH "+i,C[2].b="DIFF "+i,C.forEach(function(e){
e.f=Math.min(1,Math.abs(e.pa-e.base)/(.5===e.base?.5:.9))})}H=V((e("proScore")||{}).textContent);var s=t[window._proModoNeg]||52;z=U&&null!==H&&H>=s
;var l=String((e("proTipo")||{}).textContent||"").trim();if(!l||"—"===l||"-"===l){var d=e("proContractType");l=d?d.value:""}e("q3T").textContent=a[l]||l||"—",
e("q3S").innerHTML="<small>SCORE · MÍN "+s+"</small><b>"+(null===H?"—":Math.round(H))+"</b>",e("q3S").classList.toggle("ok",z)
;var c=C.slice().sort(function(e,t){return t.f-e.f})[0];e("q3C").innerHTML="<small>NÚCLEO MAIS FORTE</small><b>"+(o?c.pa>=c.base?c.a:c.b:"—")+"</b>",
z&&!k?(j(4906624),
e("q3Ev").textContent="SINAL FORTE · ENTRANDO EM "+e("q3T").textContent):U?z||/GANHOU|PERDEU/.test(e("q3Ev").textContent)||(e("q3Ev").textContent="SINAL ABAIXO DO MÍNIMO · ESPERANDO"):e("q3Ev").textContent="CONFIGURE E CLIQUE EM INICIAR",
k=z;var p=+n.wins||0,h=+n.losses||0,u=(+n.lucro||0)-(+n.perda||0);if(W&&p+h>W.w+W.l){var m=p>W.w,v=u-W.liq,f=(v<0?"−$":"+$")+Math.abs(v).toFixed(2)
;_(E,m?4906624:16478597,9),M(P,f,m?"#86efac":"#fda4af",!0),D=1,e("q3Ev").textContent=(m?"GANHOU ":"PERDEU ")+f,setTimeout(function(){
/GANHOU|PERDEU/.test(e("q3Ev").textContent)&&(e("q3Ev").textContent="…")},4e3)}W={w:p,l:h,liq:u}}setInterval(function(){try{Y()}catch(e){}},400),Y()
;var $=0,J=o?1e3/30:0,Q=i?.4:1,X=new r.Color,K=new r.Color,Z=new r.Color(9144232);function ee(e){if(requestAnimationFrame(ee),
!document.hidden&&document.body.classList.contains("ia-pro-open")&&d.offsetWidth&&!(J&&e-$<J)){$=e,
(!c.domElement.width||Math.abs(c.domElement.width/c.getPixelRatio()-d.offsetWidth)>2)&&m();var t=e/1e3*Q,a=.05*t,n=u.aspect<.9?23:18.5
;u.position.set(Math.cos(a)*n,9+.4*Math.sin(.2*t),Math.sin(a)*n),u.lookAt(0,2.4,0),C.forEach(function(e,a){e.r1.rotation.z=.8*t,e.r2.rotation.z=.6*-t,
e.op.rotation.y=t*(.6+1.5*e.f),e.g.position.y=2.6+.15*Math.sin(1.1*t+2*a);var n=e.pa>=e.base,r=n?e.ca:e.cb;X.setHex(r),
e.mat.color.lerp(K.copy(Z).lerp(X,.3+.7*e.f),.08),e.mat.emissive.lerp(K.copy(X).multiplyScalar(.35),.08);var o=1+.35*e.f+.02*Math.sin(3*t+a)
;e.sf.scale.set(o,o,o),e.gl.material.color.lerp(X,.1),e.gl.material.opacity=.25+.7*e.f,e.op.material.color.lerp(X,.1),e.r1.material.color.lerp(X,.05)
;var i=n?0:Math.PI;e.ag.rotation.z+=.12*(i-e.ag.rotation.z),e.agM.color.setHex(r),e.ln.material.opacity+=.1*((z?.85:.12+.3*e.f)-e.ln.material.opacity),
e.ln.material.color.setHex(z?4906624:12891645),M(e.lb,(n?e.a:e.b)+" "+Math.round(100*(n?e.pa:1-e.pa))+"%","#"+X.getHexString())}),S.rotation.y=.5*t,
S.rotation.x=.3*Math.sin(.3*t);var r=z?1.3+.08*Math.sin(6*t):1;if(I.scale.set(4*r,4*r,1),I.material.color.setHex(z?4906624:12891645),
R.emissive.setHex(z?1332013:3018853),M(T,"SCORE "+(null===H?"—":Math.round(H)),z?"rgba(74,222,128,.8)":"rgba(196,181,253,.6)"),z){var o=9+.5*Math.sin(4*t)
;q.scale.set(1+.15*Math.sin(20*t),o,1+.15*Math.sin(20*t)),q.position.y=3+o/2,q.material.opacity+=.1*(.38-q.material.opacity)
}else q.material.opacity+=.1*(0-q.material.opacity);for(var i=N.geometry.attributes.position,s=0;s<i.count;s++){var l=i.getY(s)+.006;l>11&&(l=0),i.setY(s,l)}
i.needsUpdate=!0,L=L.filter(function(e){e.p+=.03;for(var t=e.n.g.position,a=E,n=function(e){
return[t.x+(a.x-t.x)*e,t.y+(a.y-t.y)*e+.8*Math.sin(e*Math.PI),t.z+(a.z-t.z)*e]},r=0;r<e.arr.length/3;r++){var o=n(Math.max(0,Math.min(1,e.p-.018*r)))
;e.arr[3*r]=o[0],e.arr[3*r+1]=o[1],e.arr[3*r+2]=o[2]}return e.pt.geometry.attributes.position.needsUpdate=!0,!(e.p>=1.45)||(h.remove(e.pt),
e.pt.geometry.dispose(),!1)}),F=F.filter(function(e){e.p+=.02;var t=1+e.p*e.mx;return e.m.scale.set(t,t,1),e.m.lookAt(u.position),
e.m.material.opacity=Math.max(0,1-e.p),!(e.p>=1)||(h.remove(e.m),e.m.geometry.dispose(),e.m.material.dispose(),!1)}),D>0&&(D-=.007,
P.material.opacity=Math.min(1,2*D),P.position.set(0,4.4+2*(1-D),0)),c.render(h,u)}}requestAnimationFrame(ee)}(r)}catch(e){
window.console&&console.warn("cena 3D",e)}})}}();
