import {lang} from './shared.js';

export const assistantStates=()=>({
 fa:{disabled:'غیرفعال',running:'در حال دریافت',account_mode:'پردازش پیام‌های حساب تلگرام',error:'خطای اتصال یا پردازش',not_started:'هنوز شروع نشده',pending:'در انتظار تحلیل',retry:'در انتظار تلاش مجدد',failed:'ناموفق',published:'منتشرشده',ignored:'نامرتبط'},
 en:{disabled:'Disabled',running:'Receiving',account_mode:'Processing account messages',error:'Connection or processing error',not_started:'Not started',pending:'Pending',retry:'Retry scheduled',failed:'Failed',published:'Published',ignored:'Ignored'},
 ar:{disabled:'معطل',running:'جارٍ الاستلام',account_mode:'معالجة رسائل الحساب',error:'خطأ اتصال أو معالجة',not_started:'لم يبدأ بعد',pending:'بانتظار التحليل',retry:'إعادة المحاولة مجدولة',failed:'فشل',published:'منشور',ignored:'غير مرتبط'},
 es:{disabled:'Desactivado',running:'Recibiendo',account_mode:'Procesando mensajes de la cuenta',error:'Error de conexión o procesamiento',not_started:'No iniciado',pending:'Pendiente',retry:'Reintento programado',failed:'Fallido',published:'Publicado',ignored:'Ignorado'}
}[lang]);

export function assistantError(code){
 if(!code)return '';
 const labels={
  fa:{title:'عنوان',summary:'خلاصه',body:'توضیحات',fa:'فارسی',en:'انگلیسی',ar:'عربی',es:'اسپانیایی',object:'ساختار چهارزبانه ندارد',missing:'وجود ندارد',empty:'خالی است',not_text:'متن نیست',too_long:'بیش از حد طولانی است',generic:'بیش از حد عمومی یا نام خام فایل است'},
  en:{title:'Title',summary:'Summary',body:'Body',fa:'Persian',en:'English',ar:'Arabic',es:'Spanish',object:'must be a four-language object',missing:'is missing',empty:'is empty',not_text:'must be text',too_long:'is too long',generic:'is generic or a raw filename'},
  ar:{title:'العنوان',summary:'الملخص',body:'التفاصيل',fa:'الفارسية',en:'الإنجليزية',ar:'العربية',es:'الإسبانية',object:'يجب أن يحتوي على اللغات الأربع',missing:'غير موجود',empty:'فارغ',not_text:'يجب أن يكون نصًا',too_long:'طويل جدًا',generic:'عام جدًا أو اسم ملف'},
  es:{title:'Título',summary:'Resumen',body:'Descripción',fa:'Persa',en:'Inglés',ar:'Árabe',es:'Español',object:'debe contener los cuatro idiomas',missing:'falta',empty:'está vacío',not_text:'debe ser texto',too_long:'es demasiado largo',generic:'es genérico o un nombre de archivo'}
 }[lang];
 const field=/^model_(title|summary|body)(?:_(fa|en|ar|es))?_(object|missing|empty|not_text|too_long|generic)$/.exec(code);
 if(field)return labels[field[1]]+(field[2]?' ('+labels[field[2]]+')':'')+': '+labels[field[3]];
 const errors={
  model_output_truncated:{fa:'پاسخ مدل به سقف خروجی رسید و کامل نشد.',en:'The model reached its output limit before finishing.',ar:'وصل النموذج إلى حد الإخراج قبل الإكمال.',es:'El modelo alcanzó el límite de salida antes de terminar.'},
  model_output_empty:{fa:'مدل پاسخ قابل‌خواندن برنگرداند.',en:'The model returned no readable content.',ar:'لم يُرجع النموذج محتوى قابلًا للقراءة.',es:'El modelo no devolvió contenido legible.'},
  model_json_invalid:{fa:'ساختار JSON پاسخ مدل معتبر نیست.',en:'The model response is not valid JSON.',ar:'بنية JSON في رد النموذج غير صالحة.',es:'La respuesta del modelo no es JSON válido.'},
  model_object_required:{fa:'پاسخ مدل باید یک سند JSON باشد.',en:'The model must return one JSON object.',ar:'يجب أن يُرجع النموذج كائن JSON واحدًا.',es:'El modelo debe devolver un objeto JSON.'},
  model_classification_invalid:{fa:'نوع محتوا باید فروش، آموزش یا مقاله باشد.',en:'The content kind must be sale, tutorial or article.',ar:'يجب أن يكون النوع بيعًا أو درسًا أو مقالًا.',es:'El tipo debe ser venta, tutorial o artículo.'},
  model_response_invalid:{fa:'علت دقیق خطای قبلی ثبت نشده؛ دوباره پردازش کنید.',en:'The earlier validation failure has no detailed cause; retry to diagnose it.',ar:'لم يُسجل سبب تفصيلي للخطأ السابق؛ أعد المحاولة.',es:'El fallo anterior no tiene un motivo detallado; vuelve a intentarlo.'},
  connection_failed:{fa:'اتصال به سرویس برقرار نشد یا زمان پاسخ تمام شد.',en:'The service connection failed or timed out.',ar:'فشل الاتصال بالخدمة أو انتهت المهلة.',es:'La conexión falló o agotó el tiempo de espera.'}
 };
 return errors[code]?.[lang]||code;
}
