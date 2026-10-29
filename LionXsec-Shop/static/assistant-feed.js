import {api,esc,name,lang,brandLogo,brandFor,icon} from './shared.js';
import {DEFAULT_LINKS,telegramURL} from './social.js';
let posts=[];
for(const [kind,parent] of [['sale','catalog'],['tutorial','tutorials'],['article','tutorials']]){
 const section=document.createElement('section');section.id='assistant-'+kind;section.className='assistant-section';section.hidden=true;
 document.getElementById(parent)?.append(section);
}
const text=()=>({fa:{sale:'پیشنهادهای کانال',tutorial:'آموزش‌های کانال',article:'مطالب و تازه‌ها',source:'مشاهده پست اصلی',buy:'سفارش در تلگرام',price:'استعلام قیمت',details:'جزئیات بیشتر'},en:{sale:'Channel offers',tutorial:'Channel tutorials',article:'News & articles',source:'Original post',buy:'Order on Telegram',price:'Ask for price',details:'Read more'},ar:{sale:'عروض القناة',tutorial:'دروس القناة',article:'المقالات والأخبار',source:'المنشور الأصلي',buy:'اطلب عبر تيليجرام',price:'استفسر عن السعر',details:'التفاصيل'},es:{sale:'Ofertas del canal',tutorial:'Tutoriales del canal',article:'Noticias y artículos',source:'Publicación original',buy:'Pedir por Telegram',price:'Consultar precio',details:'Leer más'}}[lang]);
export async function loadAssistantPosts(){posts=(await api('/api/assistant/posts')).posts;renderAssistantPosts();}
function postCard(p,l){
 const brand=brandFor({brand:p.brand,name:p.title});
 const source=telegramURL(p.source_url);
 const order=telegramURL(p.order_url)||DEFAULT_LINKS.telegram;
 const summary=name(p.summary),body=name(p.body);
 const hasDetails=body.trim().replace(/\s+/g,' ')!==summary.trim().replace(/\s+/g,' ');
 const sourceLink=source?`<a class="assistant-source" href="${esc(source)}" target="_blank" rel="noopener noreferrer">${esc(l.source)} ${icon('arrow')}</a>`:'';
 return `<article class="assistant-card" data-brand="${esc(brand)}" data-post-id="${esc(p.id)}">
  <div class="assistant-card-heading"><span class="assistant-logo">${brandLogo('generic','assistant-lion-logo')}</span><h3>${esc(name(p.title))}</h3></div>
  <p class="assistant-summary">${esc(summary)}</p>
  ${hasDetails?`<details><summary>${esc(l.details)}</summary><p class="assistant-body">${esc(body)}</p></details>`:''}
  ${p.kind==='sale'?`<strong class="assistant-price" dir="${p.price?'ltr':'auto'}">${p.price?esc(p.price.amount+' '+p.price.currency):esc(l.price)}</strong>`:''}
  <div class="assistant-actions">${p.kind==='sale'?`<a class="button primary assistant-order" href="${esc(order)}" target="_blank" rel="noopener noreferrer">${esc(l.buy)} ${icon('arrow')}</a>`:''}${sourceLink}</div>
 </article>`;
}
export function renderAssistantPosts(){
 const l=text();
 for(const kind of ['sale','tutorial','article']){
  const section=document.getElementById('assistant-'+kind);if(!section)continue;
  const items=posts.filter(p=>p.kind===kind);section.hidden=!items.length;
  section.innerHTML=`<h2>${esc(l[kind])}</h2><div class="assistant-grid">${items.map(p=>postCard(p,l)).join('')}</div>`;
 }
}
