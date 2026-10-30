import {api,esc,lang} from './shared.js';
import {assistantStates,assistantError} from './assistant-status.js';
export const assistantLabel=()=>({fa:'دستیار تلگرام',en:'Telegram assistant',ar:'مساعد تيليجرام',es:'Asistente Telegram'}[lang]);
const labels=()=>({
 fa:{help:'کانال تحت مدیریت خود را وارد کنید و ربات اختصاصی را به آن اضافه کنید. پس از فعال‌سازی، دریافت، تحلیل و انتشار خودکار است. فیلدهای دارای ✓ را خالی بگذارید تا مقدار ذخیره‌شده حفظ شود.',channel:'کانال (@channel، ‎-100… یا لینک دعوت خصوصی در حالت حساب)',bot:'توکن ربات تلگرام',key:'کلید API OpenAI',model:'مدل هوش مصنوعی',enable:'فعال‌سازی انتشار خودکار',save:'ذخیره تنظیمات',saved:'ذخیره شد؛ دستیار در اجرای عادی سایت خودکار شروع می‌شود.',status:'وضعیت پردازش',recent:'آخرین پست‌ها',placeholder:'فقط برای جایگزینی مقدار جدید وارد کنید',error:'تنظیمات معتبر نیست.',privacy:'کلیدها فقط روی دستگاه میزبان در پوشه data ذخیره می‌شوند و در پاسخ API نمایش داده نمی‌شوند. در روش محلی، متن و تصویر روی همین دستگاه تحلیل می‌شوند. فقط روش OpenAI داده را به سرویس آنلاین می‌فرستد و هزینهٔ API دارد.'},
 en:{help:'Add a dedicated bot to your own channel. Once enabled, intake, analysis and publishing run automatically. Empty secret fields preserve saved values.',channel:'Channel (@channel or -100…)',bot:'Telegram bot token',key:'OpenAI API key',model:'AI model',enable:'Enable automatic publishing',save:'Save settings',saved:'Saved; the assistant starts automatically when running the site normally.',status:'Processing status',recent:'Recent posts',placeholder:'Enter a new value to replace',error:'Check the channel, model, Telegram token and OpenAI key.',privacy:'Keys are stored in the local data folder and never returned by the API. Local providers analyze text and images on this device. Only OpenAI sends them to an online service with API billing.'},
 ar:{help:'أضف بوتًا مخصصًا إلى قناتك. بعد التفعيل يتم التحليل والنشر تلقائيًا.',channel:'معرّف القناة',bot:'توكن البوت',key:'مفتاح OpenAI',model:'نموذج الذكاء الاصطناعي',enable:'تفعيل النشر التلقائي',save:'حفظ',saved:'تم الحفظ.',status:'حالة المعالجة',recent:'آخر المنشورات',placeholder:'قيمة جديدة للاستبدال',error:'تحقق من إعدادات القناة والمفاتيح.',privacy:'تُحفظ المفاتيح محليًا في data. تُحلل النماذج المحلية النص والصورة على هذا الجهاز؛ يرسل خيار OpenAI البيانات إلى خدمة مدفوعة فقط.'},
 es:{help:'Añade un bot dedicado a tu canal. Al activar, la clasificación y publicación son automáticas.',channel:'Canal',bot:'Token de Telegram',key:'Clave de OpenAI',model:'Modelo de IA',enable:'Activar publicación automática',save:'Guardar',saved:'Guardado.',status:'Estado',recent:'Publicaciones recientes',placeholder:'Nuevo valor para reemplazar',error:'Revisa el canal, modelo y claves.',privacy:'Las claves se guardan en data. Los proveedores locales analizan textos e imágenes en este equipo; solo OpenAI los envía a un servicio con coste de API.'}
}[lang]);
export async function renderAssistant(container,mutate){
 const result=await api('/api/admin/assistant'),c=result.config,l=labels();
 container.innerHTML=`<form id="assistant-form" class="panel settings-panel"><h2>${esc(assistantLabel())}</h2><p class="notice">${esc(l.help)}</p><p class="small muted">${esc(l.privacy)}</p><label class="field">${esc(l.channel)}<input name="channel" dir="ltr" value="${esc(c.channel)}" maxlength="40" placeholder="@your_channel"></label><label class="field">${esc(l.bot)} · ${c.bot_token_set?'✓':'—'}<input name="bot_token" type="password" dir="ltr" autocomplete="new-password" maxlength="500" placeholder="${esc(l.placeholder)}"></label><label class="field">${esc(l.key)} · ${c.api_key_set?'✓':'—'}<input name="api_key" type="password" dir="ltr" autocomplete="new-password" maxlength="500" placeholder="${esc(l.placeholder)}"></label><label class="field">${esc(l.model)}<input name="model" dir="ltr" value="${esc(c.model)}" maxlength="100"></label><label class="check-field"><input type="checkbox" name="enabled" ${c.enabled?'checked':''}>${esc(l.enable)}</label><p class="form-error" id="assistant-error" role="alert" hidden></p><p id="assistant-saved" role="status"></p><button class="button primary" type="submit">${esc(l.save)}</button><h3>${esc(l.status)}</h3><p dir="ltr">${esc(result.runtime.state)} ${esc(result.runtime.code||'')}</p><pre dir="ltr">${esc(JSON.stringify(result.counts,null,2))}</pre><h3>${esc(l.recent)}</h3><div id="assistant-recent"></div></form>`;
 const names=assistantStates();
 container.querySelector('h3 + p').textContent=(names[result.runtime.state]||result.runtime.state)+(result.runtime.code?' · '+result.runtime.code:'');
 container.querySelector('pre').textContent=Object.entries(result.counts).map(([key,count])=>(names[key]||key)+': '+count).join('\n')||'—';
 const form=container.querySelector('form');
 const recovery={
  fa:{button:'تلاش دوباره موارد ناموفق',help:'پست‌های ناموفق دوباره صف می‌شوند. دستیار باید فعال باشد؛ برای موارد در انتظار رسانه، فرمان watch دریافت‌کنندهٔ تلگرام هم باید در حال اجرا باشد.',queued:'تعداد پست‌های آمادهٔ تلاش دوباره',attempts:'تلاش ناموفق',next:'تلاش بعدی'},
  en:{button:'Retry failed posts',help:'Requeue failed posts and scheduled retries. Enable the assistant; keep the Telegram watch receiver running for posts waiting for media.',queued:'Posts queued for another attempt',attempts:'Failed attempts',next:'Next retry'},
  ar:{button:'إعادة محاولة المنشورات الفاشلة',help:'تُعاد المنشورات الفاشلة والمحاولات المجدولة. فعّل المساعد وأبقِ مستقبل Telegram watch قيد التشغيل لتنزيل الوسائط.',queued:'المنشورات الجاهزة لإعادة المحاولة',attempts:'المحاولات الفاشلة',next:'المحاولة التالية'},
  es:{button:'Reintentar publicaciones fallidas',help:'Reintenta los fallos y reintentos programados. Activa el asistente y mantén el receptor Telegram watch en ejecución para descargar archivos.',queued:'Publicaciones listas para reintentar',attempts:'Intentos fallidos',next:'Próximo intento'}
 }[lang];
 const receiverText=receiver=>{
  const r=receiver||{state:'not_started'};
  return (names[r.state]||r.state)+(r.message?' · #'+r.message:'')+(r.code?' · '+assistantError(r.code)+' ('+r.code+')':'')+(r.retry_at?' · '+recovery.next+': '+new Date(r.retry_at*1000).toLocaleTimeString(lang):'');
 };
 const renderRecent=state=>{
  const receiver=form.querySelector('#assistant-receiver-status');
  if(receiver&&state.receiver)receiver.textContent=receiverText(state.receiver);
  if(state.runtime){
   const r=state.runtime;
   form.querySelector('h3 + p').textContent=(names[r.state]||r.state)+(r.message?' · #'+r.message:'')+(r.code?' · '+assistantError(r.code)+' ('+r.code+')':'')+(r.retry_at?' · '+recovery.next+': '+new Date(r.retry_at*1000).toLocaleTimeString(lang):'');
  }
  form.querySelector('pre').textContent=Object.entries(state.counts).map(([key,count])=>(names[key]||key)+': '+count).join('\n')||'—';
  form.querySelector('#assistant-recent').innerHTML=state.recent.map(r=>`<p dir="auto">#${r.message} · ${esc(names[r.status]||r.status)}${r.error?' · '+esc(assistantError(r.error)):''}${r.attempts?' · '+esc(recovery.attempts)+': '+r.attempts:''}${['retry','waiting_media'].includes(r.status)&&r.retry_at?' · '+esc(recovery.next)+': '+esc(new Date(r.retry_at*1000).toLocaleTimeString(lang)):''}</p>`).join('');
 };
 renderRecent(result);
 form.insertAdjacentHTML('beforeend',`<div class="assistant-rewrite"><p class="small muted">${esc(recovery.help)}</p><button type="button" class="button secondary" id="assistant-retry">${esc(recovery.button)}</button><p id="assistant-retry-result" role="status"></p></div>`);
 form.querySelector('#assistant-retry').addEventListener('click',async e=>{
  const button=e.currentTarget,feedback=form.querySelector('#assistant-retry-result');
  button.disabled=true;
  try{
   const response=await mutate('/api/admin/assistant/retry','POST',{});
   feedback.textContent=recovery.queued+': '+response.queued;
   renderRecent(await api('/api/admin/assistant'));
  }catch(err){feedback.textContent=err.message||l.error;}
  finally{button.disabled=false;}
 });
 const rewrite={
  fa:{button:'بازنویسی پست‌های منتشرشده',help:'عنوان و توضیحات پست‌های قبلی با تنظیمات فعلی هوش مصنوعی بازنویسی می‌شود. دستیار باید فعال باشد؛ متن فعلی تا آماده‌شدن جایگزین نمایش داده می‌شود.',queued:'تعداد پست‌های اضافه‌شده به صف بازنویسی'},
  en:{button:'Rewrite published posts',help:'Rewrite previous titles and descriptions using the current AI settings. Enable the assistant to process them; current posts stay visible until their replacements are ready.',queued:'Posts queued for rewriting'},
  ar:{button:'إعادة كتابة المنشورات المنشورة',help:'تُعاد كتابة العناوين والتفاصيل بإعدادات الذكاء الاصطناعي الحالية. فعّل المساعد للمعالجة؛ يبقى النص الحالي ظاهرًا حتى يجهز البديل.',queued:'المنشورات المضافة إلى قائمة إعادة الكتابة'},
  es:{button:'Reescribir publicaciones',help:'Reescribe los títulos y las descripciones con la configuración de IA actual. Activa el asistente; las publicaciones actuales siguen visibles hasta que estén listas sus sustitutas.',queued:'Publicaciones en cola para reescribir'}
 }[lang];
 form.insertAdjacentHTML('beforeend',`<div class="assistant-rewrite"><p class="small muted">${esc(rewrite.help)}</p><button type="button" class="button secondary" id="assistant-reprocess">${esc(rewrite.button)}</button><p id="assistant-reprocess-result" role="status"></p></div>`);
 form.querySelector('#assistant-reprocess').addEventListener('click',async e=>{
  const button=e.currentTarget,feedback=form.querySelector('#assistant-reprocess-result');
  button.disabled=true;
  try{
   const response=await mutate('/api/admin/assistant/reprocess','POST',{});
   feedback.textContent=rewrite.queued+': '+response.queued;
   const state=await api('/api/admin/assistant');
   renderRecent(state);
  }catch(err){feedback.textContent=err.message||l.error;}
  finally{button.disabled=false;}
 });
 form.elements.channel.maxLength=200;
 const accountLabels={fa:{source:'روش دریافت تلگرام',bot:'ربات (پست‌های جدید)',account:'حساب کاربری (تاریخچه، کانال خصوصی و رسانه)',provider:'روش تحلیل هوش مصنوعی',openai:'OpenAI آنلاین (نیازمند اعتبار API)',ollama:'Ollama محلی رایگان',help:'App API ID و API hash را ذخیره کنید. حساب باید از قبل عضو و مدیر کانال خصوصی باشد. سپس روی همین دستگاه، python telegram_account.py login و بعد python telegram_account.py watch را اجرا کنید. کپشن، نوع رسانه و تصویر پیش‌نمایش عکس/ویدیو تحلیل می‌شود. شماره تلفن، کد ورود و رمز دومرحله‌ای فقط در ترمینال محلی وارد می‌شوند.',receiver:'دریافت‌کننده حساب'},en:{source:'Telegram intake',bot:'Bot (new posts)',account:'User account (history, private channels and media)',provider:'AI analysis provider',openai:'Online OpenAI (API billing required)',ollama:'Free local Ollama',help:'Save the App API ID and API hash here. The account must already be a member and admin of a private channel. Run python telegram_account.py login, then python telegram_account.py watch on this device. Captions, media type and photo/video previews are analyzed. Enter your phone, login code and two-step password only in your local terminal.',receiver:'Account receiver'}};
 const a=accountLabels[lang]||accountLabels.en;
 form.querySelector('h2').insertAdjacentHTML('afterend',`<label class="field">${esc(a.source)}<select name="source"><option value="bot">${esc(a.bot)}</option><option value="account">${esc(a.account)}</option></select></label><div id="account-fields"><p class="notice">${esc(a.help)}</p><label class="field">Telegram App API ID<input name="telegram_api_id" dir="ltr" inputmode="numeric" maxlength="16" value="${esc(c.telegram_api_id||'')}"></label><label class="field">Telegram API hash · ${c.telegram_api_hash_set?'✓':'—'}<input name="telegram_api_hash" type="password" dir="ltr" autocomplete="new-password" maxlength="32" placeholder="${esc(l.placeholder)}"></label><p>${esc(a.receiver)}: <span id="assistant-receiver-status">${esc(receiverText(result.receiver))}</span></p></div>`);
 form.querySelector('#account-fields').insertAdjacentHTML('afterend',`<label class="field">${esc(a.provider)}<select name="provider"><option value="llamacpp">llama.cpp · Gemma 3 (local)</option><option value="openai">${esc(a.openai)}</option><option value="ollama">${esc(a.ollama)}</option></select></label>`);
 form.elements.source.value=c.source||'bot';
 form.elements.provider.value=c.provider||'llamacpp';
 const diagnostics={
  fa:{button:'بررسی سرویس محلی',help:'تنظیمات را اول ذخیره کنید. این بررسی آماده‌بودن سرویس را می‌سنجد. برای آزمون واقعی Gemma، در همان پوشه فرمان python local_ai.py test را اجرا کنید؛ پس از موفقیت، انتشار را فعال کنید.',checking:'در حال بررسی…'},
  en:{button:'Check local service',help:'Save settings first. This checks service readiness. For a real Gemma generation and vision test, run python local_ai.py test in the shop folder; enable publishing after it passes.',checking:'Checking…'},
  ar:{button:'فحص الخدمة المحلية',help:'احفظ الإعدادات أولًا. يفحص هذا جاهزية الخدمة. لاختبار Gemma بالنص والصورة شغّل python local_ai.py test في مجلد الموقع ثم فعّل النشر بعد النجاح.',checking:'جارٍ الفحص…'},
  es:{button:'Comprobar servicio local',help:'Guarda la configuración primero. Comprueba si el servicio está listo. Ejecuta python local_ai.py test en la carpeta del sitio para probar Gemma con texto e imagen; activa la publicación cuando pase.',checking:'Comprobando…'}
 }[lang];
 form.elements.provider.closest('label').insertAdjacentHTML('afterend',`<div id="assistant-diagnostics"><p class="small muted">${esc(diagnostics.help)}</p><button type="button" class="button secondary" id="assistant-check">${esc(diagnostics.button)}</button><p id="assistant-check-result" role="status"></p></div>`);
 form.querySelector('#assistant-check').addEventListener('click',async e=>{
  const button=e.currentTarget,feedback=form.querySelector('#assistant-check-result');
  button.disabled=true;feedback.textContent=diagnostics.checking;
  try{
   const report=await mutate('/api/admin/assistant/diagnostics','POST',{});
   feedback.textContent=(report.model?report.model+' · ':'')+assistantError(report.code)+' ('+report.code+')';
  }catch(err){feedback.textContent=err.message||l.error;}
  finally{button.disabled=false;}
 });
 const updateSource=()=>{const account=form.elements.source.value==='account';form.querySelector('#account-fields').hidden=!account;form.elements.bot_token.closest('label').hidden=account;form.querySelector(':scope > .notice').hidden=account;};
 const defaults={llamacpp:'lionxsec-gemma-3-4b',openai:'gpt-4.1-mini',ollama:''};
 const models={[c.provider]:c.model};let previousProvider=form.elements.provider.value;
 const updateProvider=()=>{
  const provider=form.elements.provider.value,local=provider!=='openai';
  if(provider!==previousProvider){models[previousProvider]=form.elements.model.value;form.elements.model.value=models[provider]??defaults[provider];previousProvider=provider;}
  form.elements.api_key.closest('label').hidden=local;
  form.querySelector('#assistant-diagnostics').hidden=!local;
  form.elements.model.readOnly=provider==='llamacpp';
  if(provider==='llamacpp')form.elements.model.value=defaults.llamacpp;
 };
 form.elements.source.addEventListener('change',updateSource);updateSource();
 form.elements.provider.addEventListener('change',updateProvider);updateProvider();
 form.addEventListener('submit',async e=>{
  e.preventDefault();const f=new FormData(form),b=form.querySelector('button[type=submit]'),error=form.querySelector('#assistant-error');b.disabled=true;error.hidden=true;
  try{await mutate('/api/admin/assistant','PUT',{source:f.get('source'),provider:f.get('provider'),telegram_api_id:f.get('telegram_api_id'),telegram_api_hash:f.get('telegram_api_hash'),channel:f.get('channel'),model:f.get('model'),bot_token:f.get('bot_token'),api_key:f.get('api_key'),enabled:f.get('enabled')==='on'});form.elements.bot_token.value='';form.elements.api_key.value='';form.elements.telegram_api_hash.value='';form.querySelector('#assistant-saved').textContent=l.saved;}
  catch(err){const details={invalid_assistant_channel:'لینک یا شناسه کانال معتبر نیست؛ برای لینک خصوصی روش حساب کاربری را انتخاب کنید.',invalid_assistant_model:'نام مدل هوش مصنوعی معتبر نیست.',invalid_telegram_api_id:'Telegram App API ID فقط باید عدد باشد.',invalid_telegram_api_hash:'Telegram API hash باید دقیقاً ۳۲ نویسه هگز باشد.',invalid_api_key:'کلید OpenAI دارای فاصله یا نویسه نامعتبر است.',invalid_bot_token:'توکن ربات معتبر نیست.',missing_channel:'کانال وارد نشده است.',missing_api_key:'کلید OpenAI ذخیره نشده است.',missing_bot_token:'توکن ربات ذخیره نشده است.',missing_telegram_api_id:'Telegram App API ID ذخیره نشده است.',missing_telegram_api_hash:'Telegram API hash ذخیره نشده است.'};error.textContent=details[err.code]||err.message||l.error;error.hidden=false;}finally{b.disabled=false;}
 });
 // Refresh status without re-rendering the form or discarding unsaved settings.
 const refresh=async()=>{
  if(!form.isConnected)return;
  try{if(!document.hidden){const state=await api('/api/admin/assistant');if(form.isConnected)renderRecent(state);}}
  catch(err){if(err.code==='unauthorized')return;}
  if(form.isConnected)setTimeout(refresh,5000);
 };
 setTimeout(refresh,5000);
}
