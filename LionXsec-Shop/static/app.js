import {BRANDS, brandFor, brandLogo, productLogo, api, t, esc, name, amount, date, lang, setupLanguage, toast, copy, icon} from './shared.js';
import {loadResources,renderResources} from './content.js';
import {renderSocialLinks,DEFAULT_LINKS,telegramURL} from './social.js';
import {loadAssistantPosts,renderAssistantPosts} from './assistant-feed.js';
window.addEventListener('languagechange',renderAssistantPosts);
loadAssistantPosts().catch(()=>{});
setInterval(()=>loadAssistantPosts().catch(()=>{}),30000);

let catalog = {products:[],methods:[],settings:{}};
const supportURL=()=>telegramURL(catalog.support)||DEFAULT_LINKS.telegram;
function supportDraft(message){
 const url=new URL(supportURL());url.searchParams.set('text',message);return url.href;
}
function renderSupport(){
 const url=supportURL();
 for(const link of document.querySelectorAll('[data-support-link]')){
  link.href=url;
  if(link.hasAttribute('data-support-handle'))link.textContent='@'+new URL(url).pathname.slice(1).replace(/\/$/,'')+' ↗';
 }
}
let filter = 'all', search = '', currentOrder = null, submitting = false;
let cart = [];
try {
 const saved = JSON.parse(localStorage.getItem('lx-cart') || '[]');
 if (Array.isArray(saved)) cart=saved.filter(x => typeof x?.id==='string' && Number.isInteger(x.quantity) && x.quantity>=5 && x.quantity<=10000);
} catch {}
const $ = id => document.getElementById(id);
const cartRows = () => cart.map(x => ({...x,product:catalog.products.find(p => p.id===x.id)})).filter(x => x.product);
const cartTotal = () => cartRows().reduce((sum,x)=>sum+x.quantity*x.product.price_cents,0);
function persist() { localStorage.setItem('lx-cart',JSON.stringify(cart)); renderCount(); }
function renderCount() { $('cart-count').textContent=cartRows().reduce((n,x)=>n+x.quantity,0); }

function renderProducts() {
 $('service-logos').innerHTML=['nordvpn','crunchyroll','dazn','netflix','spotify','youtube','surfshark'].map(b=>`<div class="service-chip" data-brand="${b}">${brandLogo(b,'strip-logo')}<span dir="ltr">${BRANDS[b]}</span></div>`).join('');
 $('filters').innerHTML=['all','work','creative','learning','other'].map(c=>`<button data-filter="${c}" class="filter ${filter===c?'selected':''}" aria-pressed="${filter===c}">${esc(t(c))}</button>`).join('');
 const products=catalog.products.filter(p=>(filter==='all'||p.category===filter) && name(p.name).toLowerCase().includes(search.toLowerCase()));
 $('products').innerHTML=products.map((p,i)=>`<article class="product-card" data-category="${p.category}" data-brand="${brandFor(p)}">
  <div class="product-art"><span class="product-symbol">${productLogo(p)}</span><span class="product-service-name" dir="ltr">${esc(p.logo_id?name(p.name):BRANDS[brandFor(p)])}</span><span class="product-label">${esc(t(p.category))}</span>${p.demo?`<span class="demo-badge">${esc(t('demo'))}</span>`:''}</div>
  <div class="product-body"><span class="duration">${esc(name(p.duration))}</span><h3>${esc(name(p.name))}</h3><p class="delivery-line">${icon('check')}${esc(name(p.delivery))}</p>
  <div class="product-bottom"><div><strong dir="ltr">${amount(p.price_cents)} <small>USDT</small></strong><span>${esc(t('each'))}</span></div><div class="quantity-control"><button data-qty="minus" data-id="${p.id}" aria-label="−">−</button><input type="number" min="5" max="10000" step="1" value="5" id="quantity-${p.id}" aria-label="${esc(t('quantity'))}"><button data-qty="plus" data-id="${p.id}" aria-label="+">+</button></div></div>
  <div class="card-total"><span>${esc(t('subtotal'))}</span><strong data-product-total="${p.id}" dir="ltr">${amount(p.price_cents*5)} USDT</strong></div><p class="card-quantity-error small form-error" id="quantity-error-${p.id}" hidden>${esc(t('minimum'))}</p><button class="button add-button" data-add="${p.id}"><span>${esc(t('add'))}</span>${icon('plus')}</button></div></article>`).join('') || `<p class="empty-state">${esc(t('noResults'))}</p>`;
 $('preparing').hidden = catalog.methods.length>0 && catalog.products.some(p=>!p.demo);
 renderCount();
}

function changeCardQty(pid, op) {
 const el=$('quantity-'+pid);
 el.value=Math.min(10000,Math.max(5,(Number(el.value)||5)+(op==='plus'?1:-1)));
 updateCardTotal(pid);
}
function updateCardTotal(pid){
 const product=catalog.products.find(p=>p.id===pid),input=$('quantity-'+pid);if(!product||!input)return;
 const n=Number(input.value),valid=Number.isInteger(n)&&n>=5&&n<=10000;
 input.setAttribute('aria-invalid',String(!valid));$('quantity-error-'+pid).hidden=valid;
 document.querySelector(`[data-product-total="${pid}"]`).textContent=valid?amount(n*product.price_cents)+' USDT':'—';
}
function add(pid) {
 const quantity=Number($('quantity-'+pid).value);
 if (!Number.isInteger(quantity)||quantity<5||quantity>10000) return toast(t('minimum'),true);
 const existing=cart.find(x=>x.id===pid);
 if (existing) existing.quantity=Math.min(10000,existing.quantity+quantity);
 else cart.push({id:pid,quantity});
 persist(); toast(t('added'));
}

function cartHeader() { return `<div class="dialog-heading"><h2>${esc(t('cart'))}</h2><button class="icon-button" data-close="cart-dialog" aria-label="${esc(t('close'))}">${icon('close')}</button></div>`; }
function renderCart() {
 const rows=cartRows();
 $('cart-content').innerHTML=cartHeader()+ (rows.length ? `<div class="cart-items">${rows.map(x=>`<article class="cart-item"><div class="cart-item-symbol" data-category="${x.product.category}">${icon(x.product.category)}</div><div class="cart-item-copy"><h3>${esc(name(x.product.name))}</h3><p>${esc(name(x.product.duration))}</p><strong dir="ltr">${amount(x.product.price_cents)} USDT</strong></div><button class="remove-button" data-remove="${x.id}">${esc(t('remove'))}</button><div class="quantity-control"><button data-cart-qty="minus" data-id="${x.id}" aria-label="−">−</button><input data-cart-input="${x.id}" type="number" min="5" max="10000" step="1" value="${x.quantity}" aria-label="${esc(t('quantity'))}"><button data-cart-qty="plus" data-id="${x.id}" aria-label="+">+</button></div><strong class="item-total" dir="ltr">${amount(x.quantity*x.product.price_cents)} USDT</strong></article>`).join('')}</div><div class="cart-footer"><div class="total-row"><span>${esc(t('total'))}</span><strong dir="ltr">${amount(cartTotal())} USDT</strong></div><p class="muted">${esc(t('minimum'))}</p><button class="button primary full" id="checkout">${esc(t('checkout'))}${icon('arrow')}</button><p class="small muted">${esc(t('manual'))}</p></div>` : `<div class="empty-state">${icon('bag')}<p>${esc(t('empty'))}</p><button class="button primary" data-close="cart-dialog">${esc(t('browse'))}</button></div>`)
 + (localStorage.getItem('lx-order-token') ? `<button class="text-link previous-order" id="previous-order">${esc(t('previousOrder'))}</button>`:'');
 document.querySelectorAll('.cart-item').forEach((el,i)=>{el.querySelector('.cart-item-symbol').innerHTML=productLogo(rows[i].product,'list-logo');});
}

function renderCheckout() {
 if (!cartRows().length) return renderCart();
 if (!catalog.methods.length || cartRows().some(x=>x.product.demo)) return toast(t('notReady'),true);
 $('cart-content').innerHTML=cartHeader()+`<button class="text-link" id="checkout-back">← ${esc(t('back'))}</button><h3>${esc(t('payment'))}</h3><form id="checkout-form"><div class="payment-options">${['USDT_BEP20','LTC'].map(m=>`<label class="payment-option ${catalog.methods.includes(m)?'':'unavailable'}"><input type="radio" name="method" value="${m}" ${m===catalog.methods[0]?'checked':''} ${catalog.methods.includes(m)?'':'disabled'}><span><strong dir="ltr">${m==='LTC'?'LTC':'USDT'}</strong><small>${m==='LTC'?'Litecoin':'BEP-20 · BNB Smart Chain'}</small>${catalog.methods.includes(m)?'':`<small>${esc(t('unavailable'))}</small>`}</span></label>`).join('')}</div><p class="small muted">${esc(t('quoteNotice'))}</p>${catalog.methods.includes('LTC')?`<p class="rate-display">${esc(t('ltcRate'))} <b dir="ltr">${esc(catalog.settings.ltc_usdt_rate)} USDT</b></p>`:''}<label class="field">${esc(t('telegram'))}<input name="telegram" dir="ltr" maxlength="33" placeholder="@your_username" autocomplete="off"><small>${esc(t('telegramHint'))}</small></label><div class="total-row"><span>${esc(t('total'))}</span><strong dir="ltr">${amount(cartTotal())} USDT</strong></div><p class="notice">${esc(t('receiptInstructions'))}</p><p id="checkout-error" class="form-error" role="alert" hidden></p><button class="button primary full" type="submit">${esc(t('place'))}</button></form>`;
 $('checkout-form').addEventListener('submit',placeOrder);
}

async function placeOrder(e) {
 e.preventDefault(); if (submitting) return;
 submitting=true;
 const form=e.currentTarget, button=form.querySelector('[type=submit]'), data=new FormData(form);
 button.disabled=true; button.textContent=t('ordering'); $('checkout-error').hidden=true;
 try {
  currentOrder=await api('/api/orders',{method:'POST',body:JSON.stringify({items:cartRows().map(x=>({id:x.id,quantity:x.quantity})),method:data.get('method'),telegram:data.get('telegram'),language:lang})});
  localStorage.setItem('lx-order-token',currentOrder.access_token);
  cart=[]; persist(); $('cart-dialog').close(); renderOrder(); $('order-dialog').showModal(); toast(t('orderSaved'));
 } catch(err) { $('checkout-error').textContent=err.message; $('checkout-error').hidden=false; }
 finally { submitting=false; if (button.isConnected) {button.disabled=false;button.textContent=t('place');} }
}
function messageForOrder(o) {
 return [t('receiptDraft'),`${t('order')}: ${o.id}`,...o.items.map(x=>`${name(x.name)} / ${name(x.duration)} × ${x.quantity}`),`${t('total')}: ${(o.total_cents/100).toFixed(2)} USDT`,`${t('payAmount')}: ${o.amount} ${o.method==='LTC'?'LTC':'USDT (BEP-20)'}`,t('txPlaceholder')].join('\n');
}
function renderOrder() {
 const o=currentOrder; if(!o) return;
 const expired=Date.now()/1000>o.quote_expires;
 const payable=['awaiting_payment','under_review'].includes(o.status);
 $('order-content').innerHTML=`<div class="dialog-heading"><span class="eyebrow">${esc(t('order'))}</span><button class="icon-button" data-close="order-dialog" aria-label="${esc(t('close'))}">${icon('close')}</button></div><h2 class="order-number" dir="ltr">${esc(o.id)}</h2><span class="status-badge" data-status="${o.status}">${esc(t(o.status))}</span><div class="order-lines">${o.items.map(x=>`<div><span>${esc(name(x.name))} <small>× ${x.quantity}</small></span><b dir="ltr">${amount(x.unit_cents*x.quantity)} USDT</b></div>`).join('')}</div><div class="total-row"><span>${esc(t('total'))}</span><strong dir="ltr">${amount(o.total_cents)} USDT</strong></div>${payable?`<div class="payment-details"><span>${esc(t('payAmount'))}</span><div class="payment-amount" dir="ltr">${esc(o.amount)} <small>${o.method==='LTC'?'LTC':'USDT'}</small><button class="copy-button" data-copy="amount">${esc(t('copy'))}</button></div><p><b>${esc(t('network'))}:</b> ${o.method==='LTC'?'Litecoin':'BEP-20 · BNB Smart Chain'}</p><label class="field">${esc(t('address'))}<div class="copy-field"><input readonly dir="ltr" value="${esc(o.address)}" aria-label="${esc(t('address'))}"><button class="copy-button" data-copy="address">${esc(t('copy'))}</button></div></label><p class="small">${esc(t('expires'))}: ${date(o.quote_expires)}</p><p class="notice ${expired?'warning':''}">${esc(t(expired?'expired':'networkWarning'))}</p></div>`:''}<p>${esc(t('receiptInstructions'))}</p><div class="order-actions"><button class="button secondary" data-copy="message">${esc(t('copyMessage'))}</button><a class="button primary" href="${esc(supportDraft(messageForOrder(o)))}" target="_blank" rel="noopener noreferrer">${esc(t('sendTelegram'))} ↗</a></div><p class="small muted">${esc(t('draftHelp'))}</p><button class="text-link" id="refresh-order">↻ ${esc(t('refresh'))}</button>`;
}
async function loadOrder() {
 const token=localStorage.getItem('lx-order-token'); if(!token) return;
 try { currentOrder=await api('/api/orders/'+encodeURIComponent(token));renderOrder();if(!$('order-dialog').open)$('order-dialog').showModal(); }
 catch(err) {toast(err.message,true);}
}

document.addEventListener('click',e=>{
 const close=e.target.closest('[data-close]');if(close){$(close.dataset.close).close();return;}
 const f=e.target.closest('[data-filter]');if(f){filter=f.dataset.filter;renderProducts();return;}
 const qty=e.target.closest('[data-qty]');if(qty){changeCardQty(qty.dataset.id,qty.dataset.qty);return;}
 const ad=e.target.closest('[data-add]');if(ad){add(ad.dataset.add);return;}
 const rm=e.target.closest('[data-remove]');if(rm){cart=cart.filter(x=>x.id!==rm.dataset.remove);persist();renderCart();return;}
 const cq=e.target.closest('[data-cart-qty]');if(cq){const row=cart.find(x=>x.id===cq.dataset.id);row.quantity=Math.min(10000,Math.max(5,row.quantity+(cq.dataset.cartQty==='plus'?1:-1)));persist();renderCart();return;}
 const cp=e.target.closest('[data-copy]');if(cp && currentOrder){copy(cp.dataset.copy==='message'?messageForOrder(currentOrder):currentOrder[cp.dataset.copy]);return;}
 const id=e.target.closest('button')?.id;
 if(id==='checkout')renderCheckout();
 if(id==='checkout-back')renderCart();
 if(id==='previous-order'||id==='refresh-order')loadOrder();
});
document.addEventListener('change',e=>{
 const id=e.target.dataset.cartInput;if(!id)return;
 const n=Number(e.target.value);
 if(!Number.isInteger(n)||n<5||n>10000){toast(t('minimum'),true);renderCart();return;}
 cart.find(x=>x.id===id).quantity=n;persist();renderCart();
});
document.addEventListener('input',e=>{
 if(e.target.id.startsWith('quantity-')){updateCardTotal(e.target.id.slice('quantity-'.length));return;}
 const pid=e.target.dataset.cartInput;if(!pid)return;
 const n=Number(e.target.value),valid=Number.isInteger(n)&&n>=5&&n<=10000;
 e.target.setAttribute('aria-invalid',String(!valid));
 const checkout=$('checkout');if(checkout)checkout.disabled=![...document.querySelectorAll('[data-cart-input]')].every(el=>Number.isInteger(Number(el.value))&&Number(el.value)>=5&&Number(el.value)<=10000);
 if(!valid)return;
 const row=cart.find(x=>x.id===pid),product=catalog.products.find(p=>p.id===pid);if(!row||!product)return;
 row.quantity=n;persist();e.target.closest('.cart-item').querySelector('.item-total').textContent=amount(n*product.price_cents)+' USDT';
 document.querySelector('.cart-footer .total-row strong').textContent=amount(cartTotal())+' USDT';
});
$('cart-open').addEventListener('click',()=>{renderCart();$('cart-dialog').showModal();});
$('search').addEventListener('input',e=>{search=e.target.value;renderProducts();});
window.addEventListener('languagechange',()=>{renderSocialLinks(catalog.settings.social_links||DEFAULT_LINKS);renderProducts();if($('cart-dialog').open)renderCart();renderOrder();renderResources();});
for(const dialog of document.querySelectorAll('dialog')) dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});
setInterval(()=>{if(currentOrder && $('order-dialog').open && Date.now()/1000>currentOrder.quote_expires && !document.querySelector('#order-content .warning'))renderOrder();},1000);
setupLanguage();
renderSocialLinks();
try {catalog=await api('/api/catalog');renderSupport();renderSocialLinks(catalog.settings.social_links);cart=cart.filter(x=>catalog.products.some(p=>p.id===x.id));persist();renderProducts();}
catch(err){$('products').textContent=err.message;toast(err.message,true);}
loadResources().catch(err=>toast(err.message,true));
