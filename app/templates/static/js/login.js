const branding = document.getElementById('branding');
const bgLayer  = document.getElementById('bgLayer');
const botWrap  = document.getElementById('botWrap');
const brandName = document.getElementById('brandName');
const tagline   = document.getElementById('tagline');
const flames    = document.getElementById('flames');
const starsEl   = document.getElementById('stars');

// Stars
for(let i=0;i<45;i++){
  const s=document.createElement('div');
  s.className='star';
  const sz=Math.random()*3+1.2;
  s.style.cssText=`width:${sz}px;height:${sz}px;left:${Math.random()*100}%;top:${Math.random()*100}%;animation-delay:${Math.random()*2}s;animation-duration:${1.5+Math.random()*2}s;`;
  starsEl.appendChild(s);
}

// Flame flicker
let flameT=0;
function animateFlames(){
  flameT+=0.18;
  const ells=flames.querySelectorAll('ellipse');
  ells[0].setAttribute('ry', 9+Math.sin(flameT)*3);
  ells[1].setAttribute('ry', 6+Math.sin(flameT*1.3)*2.5);
  ells[2].setAttribute('ry', 9+Math.sin(flameT+1)*3);
  ells[3].setAttribute('ry', 6+Math.sin(flameT*1.3+1)*2.5);
  requestAnimationFrame(animateFlames);
}
animateFlames();

// Eye blink
let blinkTimer=0;
function blinkEyes(){
  const eyeG=document.getElementById('eyeGroup');
  eyeG.style.transform='scaleY(0.05)';
  eyeG.style.transformOrigin='55px 42px';
  setTimeout(()=>{eyeG.style.transform='scaleY(1)';},120);
}
setInterval(blinkEyes, 3200+Math.random()*1000);

// Particles
function spawnParticles(){
  const colors=['#00d4ff','#00aaff','#ffffff','#80ffee','#c0f0ff','#ffee00'];
  for(let i=0;i<24;i++){
    const p=document.createElement('div');
    p.className='particle';
    const sz=Math.random()*10+4;
    const ang=Math.random()*360;
    const dist=50+Math.random()*110;
    const tx=Math.cos(ang*Math.PI/180)*dist+'px';
    const ty=Math.sin(ang*Math.PI/180)*dist+'px';
    const col=colors[Math.floor(Math.random()*colors.length)];
    const dur=0.7+Math.random()*0.5;
    p.style.cssText=`width:${sz}px;height:${sz}px;background:${col};left:${20+Math.random()*60}%;top:${20+Math.random()*60}%;--tx:${tx};--ty:${ty};animation:pburst ${dur}s ease-out forwards;animation-delay:${Math.random()*0.15}s;`;
    branding.appendChild(p);
    setTimeout(()=>p.remove(),1600);
  }
}

// PATH: Astro bot moves slowly across the branding panel
// Bounding box of branding (known ~flex 1.3 of 100% widget)
// We animate in JS with requestAnimationFrame for smooth slow arc

let botX = -130;  // start off left
let botY = 50;    // percent of branding height
let phase = 0;    // 0=going right, 1=pause, 2=going left, 3=pause
let progress = 0; // 0..1 for current phase
let colorLit = false;
let lastColorState = false;

const SPEED = 0.0008; // very slow
const WAVE_AMP = 22;  // vertical wave amplitude (px)

function getTextRect(){
  const bc = document.querySelector('.brand-content');
  const br = branding.getBoundingClientRect();
  const bcr = bc.getBoundingClientRect();
  return {
    left: bcr.left - br.left,
    right: bcr.right - br.left,
    top: bcr.top - br.top,
    bottom: bcr.bottom - br.top,
    cx: (bcr.left+bcr.right)/2 - br.left,
    cy: (bcr.top+bcr.bottom)/2 - br.top
  };
}

function isOverText(bx, by){
  // bx/by = top-left of bot in branding px coords
  const bw=110, bh=130;
  const t = getTextRect();
  // check overlap
  return bx < t.right && bx+bw > t.left && by < t.bottom && by+bh > t.top;
}

let bh_cache=600, bw_cache=300;
function updateCache(){
  bh_cache = branding.offsetHeight;
  bw_cache = branding.offsetWidth;
}
updateCache();
window.addEventListener('resize', updateCache);

let lastTime=null;
function loop(ts){
  if(!lastTime) lastTime=ts;
  const dt = Math.min(ts-lastTime, 40);
  lastTime=ts;

  const bw = bw_cache;
  const bh = bh_cache;

  if(phase===0){
    // flying left → right (slow)
    progress += SPEED * dt;
    const t = progress;
    botX = -130 + (bw+260)*t;
    botY = bh*0.35 + Math.sin(t*Math.PI*2)*WAVE_AMP;

    // flip: facing right (normal)
    botWrap.style.transform = `scaleX(1)`;
    flames.style.display='';

    if(progress>=1){ phase=1; progress=0; }
  }
  else if(phase===1){
    // off-screen right, brief pause
    botX = bw+20; botY=bh*0.35;
    progress += SPEED*dt*4;
    if(progress>=1){ phase=2; progress=0; }
  }
  else if(phase===2){
    // flying right → left
    progress += SPEED * dt;
    const t=progress;
    botX = bw+20 - (bw+260)*t;
    botY = bh*0.55 + Math.sin(t*Math.PI*2+1)*WAVE_AMP;

    // flip: facing left
    botWrap.style.transform=`scaleX(-1)`;
    flames.style.display='';

    if(progress>=1){ phase=3; progress=0; }
  }
  else if(phase===3){
    botX=-130; botY=bh*0.35;
    progress+=SPEED*dt*4;
    if(progress>=1){ phase=0; progress=0; }
  }

  botWrap.style.left = botX+'px';
  botWrap.style.top  = botY+'px';

  // Check if bot is over the text region
  const over = isOverText(botX, botY);
  if(over !== colorLit){
    colorLit = over;
    if(over){
      bgLayer.classList.add('crystal');
      brandName.classList.add('lit');
      tagline.classList.add('lit');
      spawnParticles();
      starsEl.querySelectorAll('.star').forEach(s=>{
        s.style.background='rgba(180,240,255,.95)';
        s.style.boxShadow='0 0 6px rgba(0,212,255,.8)';
      });
    } else {
      bgLayer.classList.remove('crystal');
      brandName.classList.remove('lit');
      tagline.classList.remove('lit');
      starsEl.querySelectorAll('.star').forEach(s=>{
        s.style.background='rgba(255,255,255,.65)';
        s.style.boxShadow='';
      });
    }
  }

  requestAnimationFrame(loop);
}

requestAnimationFrame(loop);