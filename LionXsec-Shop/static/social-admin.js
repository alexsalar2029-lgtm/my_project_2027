import {SOCIALS,socialText} from './social.js';
import {esc,t,toast} from './shared.js';

export function renderSocialSettings(container,catalog,mutate){
 const text=socialText(),links=catalog.settings.social_links||{};
 container.innerHTML=`<form id="social-form" class="panel settings-panel"><h2>${esc(text.title)}</h2><p class="notice">${esc(text.help)}</p><div class="form-grid">${SOCIALS.map(s=>`<label class="field">${s.label}<input name="${s.id}" type="url" dir="ltr" maxlength="2000" autocomplete="off" placeholder="https://…" value="${esc(links[s.id]||'')}"></label>`).join('')}</div><p id="social-error" class="form-error" role="alert" hidden></p><button class="button primary" type="submit">${esc(t('save'))}</button></form>`;
 const form=container.querySelector('form');
 form.addEventListener('submit',async event=>{
  event.preventDefault();const button=form.querySelector('[type=submit]'),error=form.querySelector('#social-error');button.disabled=true;error.hidden=true;
  try{catalog.settings.social_links=await mutate('/api/admin/social-links','PUT',Object.fromEntries(new FormData(form)));toast(t('saved'));}
  catch(err){error.textContent=err.code==='invalid_social_url'?text.error:err.message;error.hidden=false;}
  finally{button.disabled=false;}
 });
}
