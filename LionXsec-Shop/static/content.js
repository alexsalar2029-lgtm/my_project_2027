import {api,t,esc,name,icon} from './shared.js';
let resources=[];
export async function loadResources(){resources=(await api('/api/resources')).resources;renderResources();}
export function renderResources(){
 const tutorials=document.getElementById('tutorial-list'),tools=document.getElementById('tool-list');if(!tutorials||!tools)return;
 tutorials.innerHTML=resources.filter(r=>r.kind==='tutorial').map(r=>`<article class="tutorial-card">${resourcePlayer(r)}<div class="resource-body"><h3>${esc(name(r.title))}</h3><p>${esc(name(r.description))}</p></div></article>`).join('')||`<p class="resource-empty">${esc(t('noTutorials'))}</p>`;
 tools.innerHTML=resources.filter(r=>r.kind==='tool').map(r=>`<article class="tool-card"><span class="tool-symbol">${icon('work')}</span><div class="grow"><h3>${esc(name(r.title))}</h3><p>${esc(name(r.description))}</p></div><a class="button secondary" href="${esc(r.download_url)}" target="_blank" rel="noopener noreferrer">${esc(t('download'))}${icon('arrow')}</a></article>`).join('')||`<p class="resource-empty">${esc(t('noTools'))}</p>`;
}
function resourcePlayer(r) {
 const url=esc(r.video_url),label=esc(name(r.title)),mime=r.video_mime||'';
 if(mime.startsWith('video/'))return `<video controls preload="metadata" playsinline aria-label="${label}"><source src="${url}" type="${esc(mime)}"></video>`;
 if(mime.startsWith('audio/'))return `<audio controls preload="metadata" aria-label="${label}"><source src="${url}" type="${esc(mime)}"></audio>`;
 if(mime.startsWith('image/'))return `<img src="${url}" alt="${label}" loading="lazy">`;
 return `<a class="button secondary resource-download" href="${url}" target="_blank" rel="noopener noreferrer">${esc(t('download'))}${icon('arrow')}</a>`;
}
