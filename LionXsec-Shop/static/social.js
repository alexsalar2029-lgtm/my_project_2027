import {esc,lang} from './shared.js';

const svg = body => `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">${body}</svg>`;
export const SOCIALS = [
 {id:'youtube',label:'YouTube',icon:svg('<rect x="2" y="5" width="20" height="14" rx="4" fill="currentColor"/><path d="m10 9 6 3-6 3Z" fill="#fff"/>')},
 {id:'telegram',label:'Telegram',icon:svg('<path fill="currentColor" d="M21 3 2 10.5c-.9.4-.8 1.1.1 1.4l4.8 1.5L9 20c.2.7.7.8 1.1.3l3-3.1 4.8 3.5c.6.5 1.2.2 1.4-.6l3-15.6C22.5 3.2 22 2.6 21 3ZM9 13l9.2-6-7.4 7.4-.5 3.2L9 13Z"/>')},
 {id:'instagram',label:'Instagram',icon:svg('<g fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/></g><circle cx="17.5" cy="6.5" r="1.2" fill="currentColor"/>')},
 {id:'x',label:'X',icon:svg('<path fill="currentColor" d="M18.9 2H22l-6.8 7.8L23 22h-6.3l-4.9-7.4L5.3 22H2.1l8.2-9.4L1 2h6.5l4.4 6.7L18.9 2ZM17.8 20h1.7L6.4 4H4.5l13.3 16Z"/>')},
 {id:'discord',label:'Discord',icon:svg('<path fill="currentColor" d="M19 5a17 17 0 0 0-4-1l-.5 1h-5L9 4a17 17 0 0 0-4 1C2 9 1 13 2 17l5 3 1-2-2-1 1-.5a15 15 0 0 0 10 0l1 .5-2 1 1 2 5-3c1-4 0-8-3-12ZM8 14c-2 0-2-4 0-4s2 4 0 4Zm8 0c-2 0-2-4 0-4s2 4 0 4Z"/>')},
 {id:'whatsapp',label:'WhatsApp',icon:svg('<path d="M20 12a8 8 0 0 1-12 7L3 21l1.5-5A8 8 0 1 1 20 12Z" fill="none" stroke="currentColor" stroke-width="2"/><path d="M8 7c-3 3 3 10 7 9l2-2-3-2-1 1c-2-1-3-2-3-3l1-1-3-2Z" fill="currentColor"/>')},
 {id:'github',label:'GitHub',icon:svg('<path fill="currentColor" d="M12 2a10 10 0 0 0-3.2 19.5v-2c-2.6.5-3.2-1.1-3.2-1.1-.4-1-1-1.3-1-1.3-.9-.6.1-.6.1-.6 1 .1 1.5 1 1.5 1 .8 1.4 2.1 1 2.7.7.1-.6.4-1 .7-1.3-2.1-.2-4.3-1-4.3-4.9 0-1.1.4-2 1-2.7-.1-.3-.4-1.3.1-2.7 0 0 .8-.3 2.8 1a9 9 0 0 1 5.1 0c2-1.3 2.8-1 2.8-1 .5 1.4.2 2.4.1 2.7.6.7 1 1.6 1 2.7 0 3.9-2.2 4.7-4.3 4.9.4.3.7.9.7 1.8v2.8A10 10 0 0 0 12 2Z"/>')},
 {id:'tiktok',label:'TikTok',icon:svg('<path fill="currentColor" d="M14 2h3c.3 3 1.7 4.3 5 5v3a10 10 0 0 1-5-2v8a6 6 0 1 1-6-6v3a3 3 0 1 0 3 3V2Z"/>')},
];
export const DEFAULT_LINKS = {youtube:'https://www.youtube.com/@ComboList-qe7yy',telegram:'https://t.me/LionXSec'};
export function telegramURL(value){
 if(typeof value!=='string'||/[\s\\\x00-\x1f]/.test(value))return '';
 try{
  const url=new URL(value);
  return url.protocol==='https:'&&['t.me','telegram.me'].includes(url.hostname)&&
   !url.username&&!url.password&&!url.port ? url.href : '';
 }catch{return '';}
}
export const socialText = () => ({
 fa:{title:'شبکه‌های اجتماعی',help:'لینک کامل HTTPS حساب خود را وارد کنید. با خالی گذاشتن هر لینک، آیکون آن پنهان می‌شود.',error:'لینک معتبر HTTPS متعلق به همان شبکه وارد کنید.'},
 en:{title:'Social networks',help:'Enter your full HTTPS profile links. Leave a link blank to hide its icon.',error:'Enter a valid HTTPS link for the matching social network.'},
 ar:{title:'شبكات التواصل الاجتماعي',help:'أدخل روابط حساباتك الكاملة باستخدام HTTPS. اترك الرابط فارغًا لإخفاء الأيقونة.',error:'أدخل رابط HTTPS صالحًا للشبكة المحددة.'},
 es:{title:'Redes sociales',help:'Introduce los enlaces HTTPS completos. Deja un enlace vacío para ocultar su icono.',error:'Introduce un enlace HTTPS válido de la red correspondiente.'},
}[lang]);

export function renderSocialLinks(links=DEFAULT_LINKS){
 const nav=document.getElementById('social-links');if(!nav)return;
 nav.setAttribute('aria-label',socialText().title);
 nav.innerHTML=SOCIALS.filter(s=>{
  try{return links[s.id] && new URL(links[s.id]).protocol==='https:';}catch{return false;}
 }).map(s=>`<a class="social-link" data-social="${s.id}" href="${esc(links[s.id])}" target="_blank" rel="noopener noreferrer" aria-label="${s.label}" title="${s.label}">${s.icon}<span dir="ltr">${s.label}</span></a>`).join('');
 nav.hidden=!nav.children.length;
}
