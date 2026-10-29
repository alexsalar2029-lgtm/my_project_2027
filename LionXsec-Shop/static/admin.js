import {BRANDS, brandFor, brandLogo, productLogo, copyTranslations, uploadFile, LANGS, LANGUAGE_NAMES, api, t, esc, name, amount, date, lang, setupLanguage, toast, icon} from './shared.js';
import {ContentAdmin} from './content-admin.js';
import {renderSocialSettings} from './social-admin.js';
import {socialText} from './social.js';
import {renderAssistant,assistantLabel} from './assistant-ui.js';
let csrf='', catalog={products:[],settings:{}}, orders=[], tab='products', editLanguage='fa';
const $=id=>document.getElementById(id);
const contentAdmin=new ContentAdmin({csrf:()=>csrf,active:()=>tab});
const mutate=(path,method,data)=>api(path,{method,headers:{'X-CSRF-Token':csrf},body:JSON.stringify(data)});
async function load() {
 [catalog,{orders}]=await Promise.all([api('/api/admin/catalog'),api('/api/admin/orders')]);render();
}
function render() {
 if(tab==='assistant')renderAssistant($('admin-content'),mutate).catch(err=>toast(err.message,true));
 $('admin-tabs').innerHTML=['products','wallets','social','orders','tutorials','tools','uploads'].map(key=>`<button class="filter ${tab===key?'selected':''}" data-tab="${key}" aria-pressed="${tab===key}">${esc(key==='social'?socialText().title:t(key))}${key==='orders'?` <span class="count">${orders.length}</span>`:''}</button>`).join('');
 if(tab==='social')renderSocialSettings($('admin-content'),catalog,mutate);
 const aiTab=document.createElement('button');aiTab.type='button';aiTab.className='filter '+(tab==='assistant'?'selected':'');aiTab.dataset.tab='assistant';aiTab.setAttribute('aria-pressed',String(tab==='assistant'));aiTab.textContent=assistantLabel();$('admin-tabs').append(aiTab);
 if(tab==='products')renderProducts(); if(tab==='wallets')renderWallets(); if(tab==='orders')renderOrders();
 if(['tutorials','tools','uploads'].includes(tab))contentAdmin.render(tab).catch(err=>toast(err.message,true));
}
function renderProducts() {
 $('admin-content').innerHTML=`<div class="admin-toolbar"><p class="muted">${esc(t('translations'))}</p><button class="button primary" id="new-product">${icon('plus')}${esc(t('newProduct'))}</button></div><div class="admin-product-list">${catalog.products.map(p=>`<article class="admin-product"><span class="cart-item-symbol" data-category="${p.category}">${icon(p.category)}</span><div class="grow"><h3>${esc(name(p.name))} ${p.demo?`<span class="demo-inline">${esc(t('demo'))}</span>`:''}</h3><p>${esc(name(p.duration))} · ${esc(name(p.delivery))}</p></div><strong dir="ltr">${amount(p.price_cents)} USDT</strong><span class="status-badge" data-status="${p.active?'paid':'cancelled'}">${esc(t(p.active?'active':'unavailable'))}</span><button class="button secondary" data-edit-product="${p.id}">${esc(t('edit'))}</button><button class="remove-button" data-delete-product="${p.id}">${esc(t('delete'))}</button></article>`).join('')}</div>`;
 document.querySelectorAll('.admin-product').forEach((row,i)=>{row.querySelector('.cart-item-symbol').innerHTML=productLogo(catalog.products[i],'list-logo');});
}
function renderWallets() {
 const s=catalog.settings;
 $('admin-content').innerHTML=`<form id="wallet-form" class="panel settings-panel"><h2>${esc(t('wallets'))}</h2><p class="notice">${esc(t('publicOnly'))}</p><label class="field">${esc(t('usdtWallet'))}<input dir="ltr" name="usdt_bep20" value="${esc(s.usdt_bep20)}" placeholder="0x…" maxlength="42" autocomplete="off"></label><label class="field">${esc(t('ltcWallet'))}<input dir="ltr" name="ltc" value="${esc(s.ltc)}" placeholder="ltc1… / L… / M…" maxlength="90" autocomplete="off"></label><label class="field">${esc(t('rate'))}<input type="number" min="0.01" max="1000000" step="0.00000001" name="ltc_usdt_rate" value="${esc(s.ltc_usdt_rate)}" dir="ltr"><small>${esc(t('rateHelp'))}</small></label><p class="small muted">${esc(t('lastUpdated'))}: ${s.rate_updated?date(s.rate_updated):esc(t('noRate'))}</p><p id="wallet-error" class="form-error" role="alert" hidden></p><button class="button primary" type="submit">${esc(t('save'))}</button></form>`;
 $('wallet-form').addEventListener('submit',async e=>{
  e.preventDefault();const button=e.currentTarget.querySelector('[type=submit]');button.disabled=true;
  try{catalog.settings=await mutate('/api/admin/settings','PUT',Object.fromEntries(new FormData(e.currentTarget)));toast(t('saved'));renderWallets();}
  catch(err){$('wallet-error').textContent=err.message;$('wallet-error').hidden=false;}finally{button.disabled=false;}
 });
}
function renderOrders() {
 $('admin-content').innerHTML=`<div class="admin-toolbar"><p class="muted">${esc(t('statusHint'))}</p><button class="button secondary" id="reload-orders">↻ ${esc(t('refresh'))}</button></div><div class="order-list">${orders.map(o=>`<article class="admin-order"><div><strong dir="ltr">${esc(o.id)}</strong><p class="small muted">${date(o.created)} · <bdi>${esc(o.telegram||'—')}</bdi></p></div><div class="grow">${o.items.map(x=>`<p>${esc(name(x.name))} × ${x.quantity}</p>`).join('')}</div><strong dir="ltr">${amount(o.total_cents)} USDT</strong><span class="status-badge" data-status="${o.status}">${esc(t(o.status))}</span><button class="button secondary" data-edit-order="${o.id}">${esc(t('details'))}</button></article>`).join('')||`<div class="empty-state">${esc(t('noOrders'))}</div>`}</div>`;
}
function editProduct(pid) {
 const p=catalog.products.find(p=>p.id===pid);
 editLanguage=lang;
 $('edit-content').innerHTML=`<div class="dialog-heading"><h2>${esc(t(p?'edit':'newProduct'))}</h2><button class="icon-button" data-close aria-label="${esc(t('close'))}">${icon('close')}</button></div><p class="small muted">${esc(t('translations'))}</p><div class="translation-tabs">${LANGS.map(l=>`<button class="filter ${editLanguage===l?'selected':''}" data-edit-lang="${l}" type="button">${LANGUAGE_NAMES[l]}</button>`).join('')}</div><form id="product-form" data-pid="${pid||''}">${LANGS.map(l=>`<div data-language-fields="${l}" ${editLanguage!==l?'hidden':''}>${['name','duration','delivery'].map(key=>`<label class="field">${esc(t(key==='name'?'productName':key))} · ${LANGUAGE_NAMES[l]}<input name="${key}_${l}" lang="${l}" dir="${['fa','ar'].includes(l)?'rtl':'ltr'}" value="${esc(p?.[key]?.[l]||'')}" maxlength="250" aria-required="true"></label>`).join('')}</div>`).join('')}<div class="form-grid"><label class="field">${esc(t('price'))}<input type="number" name="price" min="0.01" max="100000" step="0.01" dir="ltr" value="${p?(p.price_cents/100).toFixed(2):''}" required></label><label class="field">${esc(t('category'))}<select name="category">${['work','creative','learning','other'].map(c=>`<option value="${c}" ${p?.category===c?'selected':''}>${esc(t(c))}</option>`).join('')}</select></label></div><label class="check-field"><input type="checkbox" name="active" ${p?.active!==false?'checked':''}>${esc(t('active'))}</label><p id="product-error" class="form-error" role="alert" hidden></p><div class="form-actions"><button type="submit" class="button primary">${esc(t('save'))}</button><button type="button" class="button secondary" data-close>${esc(t('cancel'))}</button></div></form>`;
 const brandField=document.createElement('label');
 brandField.className='field';
 brandField.innerHTML=`${esc(t('productLogo'))}<div class="brand-picker-preview">${productLogo(p,'picker-logo')}<select name="brand">${Object.entries(BRANDS).map(([key,label])=>`<option value="${key}" ${brandFor(p)===key?'selected':''}>${label}</option>`).join('')}</select></div><input type="hidden" name="logo_id" value="${esc(p?.logo_id||'')}"><span>${esc(t('uploadLogo'))}</span><input id="product-logo-file" type="file" accept="image/png,image/jpeg,image/webp"><small>${esc(t('logoHint'))}</small><button class="text-link" id="remove-custom-logo" type="button" ${p?.logo_id?'':'hidden'}>${esc(t('removeLogo'))}</button><progress id="logo-progress" max="100" value="0" hidden></progress>`;
 $('product-form').querySelector('.check-field').before(brandField);
 const form=$('product-form');
 const resetLogo=()=>{form.elements.logo_id.value='';brandField.querySelector('img').outerHTML=brandLogo(form.elements.brand.value,'picker-logo');$('remove-custom-logo').hidden=true;};
 brandField.querySelector('select').addEventListener('change',resetLogo);
 $('remove-custom-logo').addEventListener('click',resetLogo);
 const copyButton=document.createElement('button');copyButton.type='button';copyButton.className='button secondary copy-translations';copyButton.textContent=t('copyTranslations');
 form.prepend(copyButton);copyButton.addEventListener('click',()=>copyTranslations(form,['name','duration','delivery'],editLanguage));
 const helper=document.createElement('p');helper.className='small muted';helper.textContent=t('productHelp');form.prepend(helper);
 let pendingUpload=null;
 $('product-logo-file').addEventListener('change',async e=>{
  const file=e.target.files[0];if(!file)return;
  if(file.size>3*1024**2){toast(t('errors').upload_too_large,true);return;}
  const button=form.querySelector('[type=submit]'),progress=$('logo-progress');button.disabled=true;e.target.disabled=true;progress.hidden=false;
  pendingUpload=uploadFile(file,'logo',csrf,n=>progress.value=n);
  try{const media=await pendingUpload;form.elements.logo_id.value=media.id;brandField.querySelector('img').outerHTML=productLogo({logo_id:media.id,name:{en:file.name}},'picker-logo');$('remove-custom-logo').hidden=false;toast(t('uploadComplete'));}
  catch(err){if($('edit-dialog').open)toast(err.message,true);}finally{pendingUpload=null;button.disabled=false;e.target.disabled=false;progress.hidden=true;}
 });
 $('edit-dialog').addEventListener('close',()=>pendingUpload?.abort(),{once:true});
 $('product-form').addEventListener('submit',async e=>{
  e.preventDefault();const form=e.currentTarget, f=new FormData(form),button=form.querySelector('[type=submit]');
  if(pendingUpload)return;
  const data={price:f.get('price'),category:f.get('category'),brand:f.get('brand'),logo_id:f.get('logo_id'),active:f.get('active')==='on'};
  for(const field of ['name','duration','delivery'])data[field]=Object.fromEntries(LANGS.map(l=>[l,f.get(field+'_'+l)]));
  button.disabled=true;
  try{await mutate('/api/admin/products'+(pid?'/'+pid:''),pid?'PUT':'POST',data);$('edit-dialog').close();await load();toast(t('saved'));}
  catch(err){$('product-error').textContent=err.message;$('product-error').hidden=false;}finally{button.disabled=false;}
 });
 $('edit-dialog').showModal();
}
function editOrder(oid) {
 const o=orders.find(o=>o.id===oid);if(!o)return;
 const allowed={awaiting_payment:['under_review','paid','cancelled'],under_review:['paid','cancelled'],paid:['delivered'],delivered:[],cancelled:[]};
 $('edit-content').innerHTML=`<div class="dialog-heading"><h2 dir="ltr">${esc(o.id)}</h2><button class="icon-button" data-close aria-label="${esc(t('close'))}">${icon('close')}</button></div><div class="order-lines">${o.items.map(x=>`<div><span>${esc(name(x.name))} × ${x.quantity}<small>${esc(name(x.duration))} · ${esc(name(x.delivery))}</small></span><b dir="ltr">${amount(x.unit_cents*x.quantity)} USDT</b></div>`).join('')}</div><p dir="ltr">${esc(o.amount)} ${o.method==='LTC'?'LTC':'USDT · BEP-20'}</p><p class="wallet-address" dir="ltr">${esc(o.address)}</p><p class="small muted">${esc(t('expires'))}: ${date(o.quote_expires)}</p><form id="order-form"><label class="field">${esc(t('status'))}<select name="status">${[o.status,...allowed[o.status]].map(s=>`<option value="${s}">${esc(t(s))}</option>`).join('')}</select></label><label class="field">${esc(t('txid'))}<input dir="ltr" name="txid" value="${esc(o.txid)}" maxlength="66" autocomplete="off"></label><label class="field">${esc(t('notes'))}<textarea name="notes" maxlength="2000" rows="3">${esc(o.notes)}</textarea></label><label class="check-field"><input type="checkbox" name="manual_confirmed">${esc(t('manualConfirm'))}</label><p class="small muted">${esc(t('statusHint'))}</p><p id="order-error" class="form-error" role="alert" hidden></p><button type="submit" class="button primary">${esc(t('save'))}</button></form>`;
 $('order-form').addEventListener('submit',async e=>{
  e.preventDefault();const f=new FormData(e.currentTarget),button=e.currentTarget.querySelector('[type=submit]');button.disabled=true;
  try{await mutate('/api/admin/orders/'+oid,'PUT',{status:f.get('status'),notes:f.get('notes'),txid:f.get('txid'),manual_confirmed:f.get('manual_confirmed')==='on'});$('edit-dialog').close();await load();toast(t('saved'));}
  catch(err){$('order-error').textContent=err.message;$('order-error').hidden=false;}finally{button.disabled=false;}
 });
 $('edit-dialog').showModal();
}
function authenticated(value) { $('login-section').hidden=value;$('dashboard').hidden=!value;$('logout').hidden=!value; }
$('login-form').addEventListener('submit',async e=>{
 e.preventDefault();const button=e.currentTarget.querySelector('[type=submit]');button.disabled=true;$('login-error').hidden=true;
 try{const result=await api('/api/admin/login',{method:'POST',body:JSON.stringify({password:new FormData(e.currentTarget).get('password')})});csrf=result.csrf;e.target.reset();await load();authenticated(true);}
 catch(err){$('login-error').textContent=err.message;$('login-error').hidden=false;}finally{button.disabled=false;}
});
$('logout').addEventListener('click',async()=>{try{await mutate('/api/admin/logout','POST',{});csrf='';authenticated(false);$('admin-content').replaceChildren();}catch(err){toast(err.message,true);}});
document.addEventListener('click',async e=>{
 const close=e.target.closest('[data-close]');if(close){$('edit-dialog').close();return;}
 const langButton=e.target.closest('[data-edit-lang]');if(langButton){editLanguage=langButton.dataset.editLang;document.querySelectorAll('[data-language-fields]').forEach(el=>el.hidden=el.dataset.languageFields!==editLanguage);document.querySelectorAll('[data-edit-lang]').forEach(el=>el.classList.toggle('selected',el.dataset.editLang===editLanguage));return;}
 const tb=e.target.closest('[data-tab]');if(tb){tab=tb.dataset.tab;render();return;}
 const ep=e.target.closest('[data-edit-product]');if(ep){editProduct(ep.dataset.editProduct);return;}
 const eo=e.target.closest('[data-edit-order]');if(eo){editOrder(eo.dataset.editOrder);return;}
 const del=e.target.closest('[data-delete-product]');if(del && confirm(t('deleteConfirm'))){try{await mutate('/api/admin/products/'+del.dataset.deleteProduct,'DELETE',{});await load();toast(t('saved'));}catch(err){toast(err.message,true);}return;}
 if(e.target.closest('#new-product'))editProduct(null);
 if(e.target.closest('#reload-orders')){try{await load();}catch(err){toast(err.message,true);}}
});
$('edit-dialog').addEventListener('click',e=>{if(e.target===$('edit-dialog'))$('edit-dialog').close();});
window.addEventListener('languagechange',()=>{if(csrf)render();});
setupLanguage();
try{csrf=(await api('/api/admin/me')).csrf;await load();authenticated(true);}catch(err){if(err.status!==401)toast(err.message,true);}
