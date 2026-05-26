const starsEl = document.getElementById('stars');

// Stars
for(let i=0;i<45;i++){
  const s=document.createElement('div');
  s.className='star';
  const sz=Math.random()*3+1.2;
  s.style.cssText=`width:${sz}px;height:${sz}px;left:${Math.random()*100}%;top:${Math.random()*100}%;animation-delay:${Math.random()*2}s;animation-duration:${1.5+Math.random()*2}s;`;
  starsEl.appendChild(s);
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
