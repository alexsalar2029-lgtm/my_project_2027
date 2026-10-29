import {LANGS,LANGUAGE_NAMES,api,t,esc,name,date,lang,toast,icon,copyTranslations,uploadFile} from './shared.js';

export class ContentAdmin {
 constructor(context){this.context=context;this.resources=[];this.uploads=[];this.language=lang;}
 mutation(path,method,data){return api(path,{method,headers:{'X-CSRF-Token':this.context.csrf()},body:JSON.stringify(data)});}
 async render(tab){
  const [{resources},{uploads}]=await Promise.all([api('/api/admin/resources'),api('/api/admin/uploads')]);
  if(this.context.active()!==tab)return;
  this.resources=resources;this.uploads=uploads;
  const container=document.getElementById('admin-content');
  if(tab==='uploads'){
   container.innerHTML=`<h2>${esc(t('uploads'))}</h2><div class="upload-library">${uploads.map(m=>`<article class="uploaded-file">${m.kind==='logo'?`<img src="${m.url}" alt="" class="library-image">`:`<span class="library-video">${m.mime.startsWith('image/')?'🖼':m.mime.startsWith('audio/')?'♪':'📄'}</span>`}<div class="grow"><strong>${esc(m.name)}</strong><p class="small muted">${(m.size/1024**2).toFixed(2)} MB · ${esc(m.mime)} · ${date(m.created)}</p></div><button class="remove-button" data-delete-upload="${m.id}">${esc(t('delete'))}</button></article>`).join('')||`<p class="empty-state">${esc(t('noUploads'))}</p>`}</div>`;
   container.querySelectorAll('[data-delete-upload]').forEach(button=>button.addEventListener('click',async()=>{
    if(!confirm(t('deleteUploadConfirm')))return;
    try{await this.mutation('/api/admin/uploads/'+button.dataset.deleteUpload,'DELETE',{});await this.render(tab);toast(t('saved'));}catch(err){toast(err.message,true);}
   }));return;
  }
  const kind=tab==='tutorials'?'tutorial':'tool';
  container.innerHTML=`<div class="admin-toolbar"><p class="muted">${esc(t('contentHelp'))}</p><button id="new-resource" class="button primary">${icon('plus')}${esc(t(kind==='tutorial'?'newTutorial':'newTool'))}</button></div><div class="resource-admin-list">${resources.filter(r=>r.kind===kind).map(r=>`<article class="admin-product"><div class="grow"><h3>${esc(name(r.title))}</h3><p>${esc(name(r.description))}</p></div><span class="status-badge" data-status="${r.published?'paid':'cancelled'}">${esc(t(r.published?'published':'unavailable'))}</span><button class="button secondary" data-edit-resource="${r.id}">${esc(t('edit'))}</button><button class="remove-button" data-delete-resource="${r.id}">${esc(t('delete'))}</button></article>`).join('')||`<p class="empty-state">${esc(t(kind==='tutorial'?'noTutorials':'noTools'))}</p>`}</div>`;
  document.getElementById('new-resource').addEventListener('click',()=>this.edit(kind));
  container.querySelectorAll('[data-edit-resource]').forEach(button=>button.addEventListener('click',()=>this.edit(kind,button.dataset.editResource)));
  container.querySelectorAll('[data-delete-resource]').forEach(button=>button.addEventListener('click',async()=>{
   if(!confirm(t('deleteContentConfirm')))return;
   try{await this.mutation('/api/admin/resources/'+button.dataset.deleteResource,'DELETE',{});await this.render(tab);toast(t('saved'));}catch(err){toast(err.message,true);}
  }));
 }
 edit(kind,id){
  const item=this.resources.find(r=>r.id===id),dialog=document.getElementById('edit-dialog'),box=document.getElementById('edit-content');this.language=lang;
  box.innerHTML=`<div class="dialog-heading"><h2>${esc(t(item?'edit':kind==='tutorial'?'newTutorial':'newTool'))}</h2><button class="icon-button" data-close aria-label="${esc(t('close'))}">${icon('close')}</button></div><form id="resource-form"><p class="small muted">${esc(t('contentHelp'))}</p><button type="button" id="resource-copy-translations" class="button secondary copy-translations">${esc(t('copyTranslations'))}</button><div class="translation-tabs">${LANGS.map(l=>`<button class="filter ${l===lang?'selected':''}" type="button" data-resource-language="${l}">${LANGUAGE_NAMES[l]}</button>`).join('')}</div>${LANGS.map(l=>`<section data-resource-fields="${l}" ${l===lang?'':'hidden'}><label class="field">${esc(t('title'))} · ${LANGUAGE_NAMES[l]}<input name="title_${l}" value="${esc(item?.title[l]||'')}" maxlength="250" dir="${['fa','ar'].includes(l)?'rtl':'ltr'}"></label><label class="field">${esc(t('description'))} · ${LANGUAGE_NAMES[l]}<textarea name="description_${l}" rows="3" maxlength="1000" dir="${['fa','ar'].includes(l)?'rtl':'ltr'}">${esc(item?.description[l]||'')}</textarea></label></section>`).join('')}
  ${kind==='tutorial'?`<label class="field">${esc(t('uploadVideo'))}<input type="file" id="resource-video-file"><small>${esc(t('videoHint'))}</small></label><label class="field">${esc(t('currentVideo'))}<select name="video_id"><option value="">—</option>${this.uploads.filter(m=>m.kind==='video').map(m=>`<option value="${m.id}" ${item?.video_id===m.id?'selected':''}>${esc(m.name)}</option>`).join('')}</select></label><progress id="resource-upload-progress" value="0" max="100" hidden></progress><p class="small muted" id="resource-upload-status"></p>`:`<label class="field">${esc(t('downloadLink'))}<input name="download_url" type="url" dir="ltr" maxlength="2000" placeholder="https://…" value="${esc(item?.download_url||'')}" required></label>`}
  <label class="check-field"><input type="checkbox" name="published" ${item?.published!==false?'checked':''}>${esc(t('published'))}</label><p id="resource-error" class="form-error" role="alert" hidden></p><div class="form-actions"><button type="submit" class="button primary">${esc(t('save'))}</button><button type="button" class="button secondary" data-close>${esc(t('cancel'))}</button></div></form>`;
  const form=document.getElementById('resource-form');let pending=null;
  box.querySelectorAll('[data-resource-language]').forEach(button=>button.addEventListener('click',()=>{
   this.language=button.dataset.resourceLanguage;box.querySelectorAll('[data-resource-fields]').forEach(el=>el.hidden=el.dataset.resourceFields!==this.language);box.querySelectorAll('[data-resource-language]').forEach(el=>el.classList.toggle('selected',el===button));
  }));
  document.getElementById('resource-copy-translations').addEventListener('click',()=>copyTranslations(form,['title','description'],this.language));
  if(kind==='tutorial')document.getElementById('resource-video-file').addEventListener('change',async e=>{
   const file=e.target.files[0];if(!file)return;
   if(file.size>250*1024**2){toast(t('errors').upload_too_large,true);return;}
   const button=form.querySelector('[type=submit]'),progress=document.getElementById('resource-upload-progress'),status=document.getElementById('resource-upload-status');button.disabled=true;e.target.disabled=true;progress.hidden=false;
   pending=uploadFile(file,'video',this.context.csrf(),n=>{progress.value=n;status.textContent=t('uploading')+' '+n+'%';});
   try{const media=await pending;const option=new Option(media.name,media.id,true,true);form.elements.video_id.add(option);this.uploads.unshift(media);status.textContent=t('uploadComplete');}
   catch(err){if(dialog.open){status.textContent=err.message;toast(err.message,true);}}
   finally{pending=null;button.disabled=false;e.target.disabled=false;progress.hidden=true;}
  });
  dialog.addEventListener('close',()=>pending?.abort(),{once:true});
  form.addEventListener('submit',async e=>{
   e.preventDefault();if(pending)return;
   const f=new FormData(form),button=form.querySelector('[type=submit]');button.disabled=true;
   const data={kind,published:f.get('published')==='on',video_id:f.get('video_id'),download_url:f.get('download_url')};
   for(const field of ['title','description'])data[field]=Object.fromEntries(LANGS.map(l=>[l,f.get(field+'_'+l)]));
   try{await this.mutation('/api/admin/resources'+(id?'/'+id:''),id?'PUT':'POST',data);dialog.close();await this.render(kind==='tutorial'?'tutorials':'tools');toast(t('saved'));}
   catch(err){document.getElementById('resource-error').textContent=err.message;document.getElementById('resource-error').hidden=false;}
   finally{button.disabled=false;}
  });
  dialog.showModal();
 }
}
