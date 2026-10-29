export const LANGS = ['fa', 'en', 'ar', 'es'];
export const LANGUAGE_NAMES = {fa:'فارسی', en:'English', ar:'العربية', es:'Español'};
export const BRANDS = {generic:'LionXsec',nordvpn:'NordVPN',crunchyroll:'Crunchyroll',dazn:'DAZN',netflix:'Netflix',spotify:'Spotify',youtube:'YouTube Premium',surfshark:'Surfshark'};
export const TEXT = {
fa: {
 shop:'فروشگاه', process:'روش سفارش', support:'پشتیبانی', admin:'مدیریت', wholesale:'فروش عمدهٔ اشتراک دیجیتال', productLogo:'لوگوی سرویس', serviceCollection:'سرویس‌های شناخته‌شده، یک فروشگاه.', brandNote:'فروشگاه مستقل؛ لوگوها برای معرفی سرویس‌ها نمایش داده می‌شوند.',
 heroA:'خرید عمده اکانت پرمیوم با گارانتی', heroB:'و خرید ابزارهای خصوصی کمیاب', heroText:'اشتراک‌های موردنیازتان را یک‌جا سفارش دهید. قیمت روشن به USDT، پرداخت رمزارزی و همراهی مستقیم در تلگرام.',
 browse:'مشاهدهٔ محصولات', talk:'گفت‌وگو در تلگرام', minLabel:'حداقل هر محصول', minValue:'۵ عدد', currencyLabel:'واحد قیمت', deliveryLabel:'روش تحویل', deliveryValue:'دستی · تلگرام',
 catalog:'اشتراک بعدی شما، اینجاست.', catalogSub:'محصول را انتخاب کنید؛ از هر محصول حداقل ۵ عدد.', all:'همهٔ محصولات', work:'کار و بهره‌وری', creative:'ابزارهای خلاقیت', learning:'آموزش', other:'سایر',
 search:'جست‌وجوی محصول…', each:'برای هر عدد', add:'افزودن به سفارش', demo:'نمونه', noResults:'محصولی با این مشخصات پیدا نشد.',
 preparing:'فروشگاه در حال آماده‌سازی است. برای موجودی و سفارش با پشتیبانی تماس بگیرید.',
 howTitle:'از انتخاب تا تحویل، سه قدم.', step1:'۱. انتخاب و ثبت سفارش', step1Text:'محصول و تعداد را انتخاب کنید؛ قیمت نهایی پیش از پرداخت نمایش داده می‌شود.',
 step2:'۲. پرداخت و ارسال رسید', step2Text:'با LTC یا USDT در شبکهٔ BEP-20 پرداخت کنید و شمارهٔ سفارش و رسید را در تلگرام بفرستید.',
 step3:'۳. بررسی و تحویل دستی', step3Text:'پس از تأیید دستی پرداخت، فایل یا اطلاعات سفارش را از پشتیبانی دریافت کنید.',
 contactTitle:'پیش از سفارش سوالی دارید؟', contactText:'برای موجودی، شرایط اشتراک یا پیگیری تحویل، مستقیم با ما صحبت کنید.',
 footer:'LionXsec Shop · فروش عمدهٔ اشتراک دیجیتال', manual:'بررسی پرداخت و تحویل به‌صورت دستی انجام می‌شود.',
 cart:'سفارش شما', empty:'سبد سفارش خالی است.', remove:'حذف', quantity:'تعداد', subtotal:'جمع', total:'مبلغ کل', checkout:'ادامه و ثبت سفارش',
 close:'بستن', minimum:'حداقل تعداد هر محصول ۵ عدد است.', added:'محصول به سفارش اضافه شد.', back:'بازگشت', payment:'روش پرداخت',
 network:'شبکه', ltcRate:'نرخ دستی: هر LTC برابر', quoteNotice:'مبلغ LTC با نرخ ثبت‌شدهٔ مدیر محاسبه می‌شود؛ پیش از پرداخت اعتبار زمانی مبلغ را بررسی کنید.',
 unavailable:'فعلاً قابل انتخاب نیست', telegram:'شناسهٔ تلگرام (اختیاری)', telegramHint:'مثلاً @your_username؛ شمارهٔ سفارش را هنگام تماس بفرستید.',
 place:'ثبت سفارش و دریافت آدرس پرداخت', ordering:'در حال ثبت…', notReady:'این محصول نمونه است یا روش پرداخت هنوز آماده نیست. با پشتیبانی تماس بگیرید.',
 order:'شمارهٔ سفارش', orderSaved:'سفارش ثبت شد.', awaiting_payment:'منتظر پرداخت', under_review:'در حال بررسی دستی', paid:'پرداخت تأیید شد', delivered:'تحویل داده شد', cancelled:'لغو شده',
 payAmount:'مبلغ قابل پرداخت', address:'آدرس دریافت', copy:'کپی', copied:'کپی شد.', copyFailed:'کپی خودکار ممکن نشد؛ متن را انتخاب و کپی کنید.',
 networkWarning:'فقط از شبکهٔ نمایش‌داده‌شده استفاده کنید. انتقال با شبکهٔ دیگر ممکن است باعث از دست رفتن دارایی شود.',
 expires:'اعتبار مبلغ تا', expired:'زمان مبلغ به پایان رسیده است. پیش از هر پرداخت با پشتیبانی هماهنگ کنید.',
 receiptInstructions:'شمارهٔ سفارش و شناسهٔ تراکنش یا تصویر رسید را برای @link_Lion بفرستید. ثبت سفارش به‌معنای تأیید پرداخت نیست.',
 copyMessage:'کپی متن سفارش', sendTelegram:'باز کردن گفت‌وگوی تلگرام', refresh:'بررسی وضعیت', previousOrder:'مشاهدهٔ آخرین سفارش',
 receiptDraft:'سلام، لطفاً پرداخت این سفارش را بررسی کنید.', txPlaceholder:'شناسهٔ تراکنش / رسید: [اینجا وارد کنید]',
 adminTitle:'پیشخوان فروشگاه', loginTitle:'ورود به مدیریت', password:'رمز مدیریت', login:'ورود', logout:'خروج',
 setupHint:'در اولین اجرا، رمز را با دستور python server.py init-admin در سرور تنظیم کنید.',
 products:'محصولات', wallets:'پرداخت و کیف پول', orders:'سفارش‌ها', newProduct:'محصول جدید', edit:'ویرایش', delete:'حذف',
 productName:'نام محصول', duration:'مدت اشتراک', delivery:'روش تحویل', price:'قیمت هر عدد (USDT)', category:'دسته‌بندی', active:'نمایش در فروشگاه',
 save:'ذخیره', cancel:'انصراف', translations:'اطلاعات محصول در هر چهار زبان الزامی است.', saved:'ذخیره شد.', deleteConfirm:'این محصول حذف شود؟ سفارش‌های قبلی حفظ می‌شوند.',
 usdtWallet:'آدرس عمومی دریافت USDT — BEP-20 (BSC)', ltcWallet:'آدرس عمومی دریافت LTC — Litecoin',
 publicOnly:'فقط آدرس عمومی دریافت را وارد کنید. عبارت بازیابی یا کلید خصوصی لازم نیست.', rate:'ارزش ۱ LTC به USDT',
 rateHelp:'نرخ را خودتان وارد و حداقل هر ۲۴ ساعت به‌روز کنید. نرخ قدیمی، پرداخت LTC را غیرفعال می‌کند. اعتبار مبلغ هر سفارش ۳۰ دقیقه است.',
 lastUpdated:'آخرین ثبت نرخ', noRate:'ثبت نشده', noOrders:'هنوز سفارشی ثبت نشده است.', status:'وضعیت', details:'جزئیات',
 notes:'یادداشت داخلی', txid:'شناسهٔ تراکنش (اختیاری)', manualConfirm:'تراکنش را شخصاً بررسی کرده‌ام؛ یا تحویل سفارش را انجام داده‌ام.',
 statusHint:'تغییر وضعیت فقط ثبت دستی است؛ سایت تراکنش را بررسی یا فایل را ارسال نمی‌کند.', units:'عدد', draftHelp:'اگر متن در تلگرام درج نشد، ابتدا «کپی متن سفارش» را بزنید.',
 errors:{generic:'درخواست انجام نشد. دوباره تلاش کنید.', minimum_quantity:'از هر محصول بین ۵ تا ۱۰۰۰۰ عدد انتخاب کنید.', invalid_credentials:'رمز مدیریت درست نیست.',
 unauthorized:'دوباره وارد پنل شوید.', csrf:'نشست معتبر نیست؛ صفحه را تازه کنید.', admin_not_configured:'ابتدا رمز مدیریت را با دستور راه‌اندازی تنظیم کنید.',
 translations_required:'هر چهار ترجمه را وارد کنید.', invalid_translation:'همهٔ ترجمه‌ها الزامی‌اند و حداکثر ۲۵۰ نویسه دارند.', invalid_price:'قیمت مثبت با حداکثر دو رقم اعشار وارد کنید.',
 invalid_usdt_wallet:'فرمت آدرس BEP-20 معتبر نیست.', invalid_ltc_wallet:'آدرس اصلی Litecoin یا checksum آن معتبر نیست.', invalid_rate:'نرخ مثبت و معتبر وارد کنید.',
 payment_unavailable:'این روش پرداخت آماده نیست.', rate_expired:'نرخ LTC قدیمی است؛ از پشتیبانی نرخ تازه بخواهید.', product_unavailable:'محصول نمونه، حذف‌شده یا غیرفعال قابل سفارش نیست.',
 invalid_telegram:'شناسهٔ معتبر تلگرام وارد کنید.', manual_confirmation_required:'تأیید بررسی دستی لازم است.', invalid_status_transition:'این تغییر وضعیت مجاز نیست.',
 invalid_txid:'شناسه باید ۶۴ رقم هگز، با یا بدون 0x باشد.', rate_limited:'تعداد درخواست‌ها زیاد است؛ کمی بعد تلاش کنید.', not_found:'مورد پیدا نشد.', origin:'نشانی سایت با تنظیم سرور سازگار نیست.'}
},
en: {
 shop:'Shop', process:'How it works', support:'Support', admin:'Admin', wholesale:'DIGITAL SUBSCRIPTIONS, IN BULK', productLogo:'Service logo', serviceCollection:'Familiar services. One destination.', brandNote:'Independent shop. Logos identify the respective services.',
 heroA:'Buy premium accounts in bulk with a guarantee', heroB:'and rare private tools.', heroText:'Your digital subscriptions, together in one order. Clear USDT pricing, crypto payments, and a real person on Telegram.',
 browse:'Explore products', talk:'Chat on Telegram', minLabel:'Minimum per product', minValue:'5 units', currencyLabel:'Prices in', deliveryLabel:'Delivery', deliveryValue:'Manual · Telegram',
 catalog:'Your next subscription starts here.', catalogSub:'Choose your products. Order at least 5 of each.', all:'All products', work:'Work & productivity', creative:'Creative tools', learning:'Learning', other:'Other',
 search:'Search products…', each:'per unit', add:'Add to order', demo:'Sample', noResults:'No products match your search.',
 preparing:'The shop is getting ready. Contact support for availability and orders.',
 howTitle:'Three steps. One simple order.', step1:'01. Choose your products', step1Text:'Select your products and quantities. Review the full total before making a payment.',
 step2:'02. Pay & share your receipt', step2Text:'Pay with LTC or USDT on BEP-20. Send your order number and receipt on Telegram.',
 step3:'03. Review & manual delivery', step3Text:'After manual payment verification, support sends your file or account details.',
 contactTitle:'A question before you order?', contactText:'Talk to us about availability, subscription details, or delivery updates.',
 footer:'LionXsec Shop · Digital subscriptions in bulk', manual:'Payments are checked and orders delivered manually.',
 cart:'Your order', empty:'Your order is empty.', remove:'Remove', quantity:'Quantity', subtotal:'Subtotal', total:'Order total', checkout:'Continue to checkout',
 close:'Close', minimum:'The minimum quantity is 5 per product.', added:'Added to your order.', back:'Back', payment:'Payment method',
 network:'Network', ltcRate:'Manual rate: 1 LTC =', quoteNotice:'LTC uses the rate entered by the administrator. Check the quote expiry before paying.',
 unavailable:'Currently unavailable', telegram:'Telegram username (optional)', telegramHint:'For example @your_username. Include your order number when contacting support.',
 place:'Create order & get payment address', ordering:'Creating order…', notReady:'This is a sample product or payment is not ready. Contact support.',
 order:'Order number', orderSaved:'Your order has been created.', awaiting_payment:'Awaiting payment', under_review:'Under manual review', paid:'Payment confirmed', delivered:'Delivered', cancelled:'Cancelled',
 payAmount:'Amount to send', address:'Receiving address', copy:'Copy', copied:'Copied.', copyFailed:'Automatic copy is unavailable. Select and copy the text.',
 networkWarning:'Use only the network shown here. Sending on a different network may result in lost funds.',
 expires:'Quote valid until', expired:'This quote has expired. Contact support before sending a payment.',
 receiptInstructions:'Send your order number and transaction ID or receipt image to @link_Lion. Creating an order does not confirm payment.',
 copyMessage:'Copy order message', sendTelegram:'Open Telegram chat', refresh:'Refresh status', previousOrder:'View latest order',
 receiptDraft:'Hello, please review the payment for this order.', txPlaceholder:'Transaction ID / receipt: [add here]',
 adminTitle:'Shop dashboard', loginTitle:'Admin sign in', password:'Admin password', login:'Sign in', logout:'Sign out',
 setupHint:'On first setup, set your password on the server with python server.py init-admin.',
 products:'Products', wallets:'Payments & wallets', orders:'Orders', newProduct:'New product', edit:'Edit', delete:'Delete',
 productName:'Product name', duration:'Subscription duration', delivery:'Delivery method', price:'Unit price (USDT)', category:'Category', active:'Visible in shop',
 save:'Save changes', cancel:'Cancel', translations:'Product details are required in all four languages.', saved:'Saved.', deleteConfirm:'Delete this product? Existing orders will be preserved.',
 usdtWallet:'Public USDT receiving address — BEP-20 (BSC)', ltcWallet:'Public LTC receiving address — Litecoin',
 publicOnly:'Enter public receiving addresses only. Never enter a private key or recovery phrase.', rate:'Value of 1 LTC in USDT',
 rateHelp:'Enter your own rate and refresh it at least every 24 hours. An outdated rate disables LTC checkout. Order quotes last 30 minutes.',
 lastUpdated:'Rate last set', noRate:'Not set', noOrders:'No orders yet.', status:'Status', details:'Details',
 notes:'Internal notes', txid:'Transaction ID (optional)', manualConfirm:'I have personally verified the payment, or completed delivery.',
 statusHint:'Status changes are manual records. The website does not verify transactions or send files.', units:'units', draftHelp:'If Telegram does not insert the message, use “Copy order message” first.',
 errors:{generic:'The request failed. Please try again.', minimum_quantity:'Choose 5–10,000 units of each product.', invalid_credentials:'Incorrect admin password.',
 unauthorized:'Please sign in again.', csrf:'Your session is invalid. Reload the page.', admin_not_configured:'Set an admin password using the setup command first.',
 translations_required:'Enter all four translations.', invalid_translation:'All translations are required, up to 250 characters each.', invalid_price:'Enter a positive price with at most two decimal places.',
 invalid_usdt_wallet:'Invalid BEP-20 address format.', invalid_ltc_wallet:'Invalid Litecoin mainnet address or checksum.', invalid_rate:'Enter a valid positive rate.',
 payment_unavailable:'This payment method is not configured.', rate_expired:'The LTC rate is outdated. Ask support for a new rate.', product_unavailable:'Sample, removed or inactive products cannot be ordered.',
 invalid_telegram:'Enter a valid Telegram username.', manual_confirmation_required:'Confirm your manual verification first.', invalid_status_transition:'This status change is not allowed.',
 invalid_txid:'The transaction ID must be 64 hexadecimal digits, optionally prefixed by 0x.', rate_limited:'Too many requests. Please try again later.', not_found:'Not found.', origin:'The site address does not match the server configuration.'}
},
ar: {
 shop:'المتجر', process:'طريقة الطلب', support:'الدعم', admin:'الإدارة', wholesale:'اشتراكات رقمية بالجملة', productLogo:'شعار الخدمة', serviceCollection:'خدمات معروفة في متجر واحد.', brandNote:'متجر مستقل؛ الشعارات للتعريف بالخدمات.',
 heroA:'شراء حسابات بريميوم بالجملة مع ضمان', heroB:'وشراء أدوات خاصة نادرة', heroText:'اطلب اشتراكاتك الرقمية في مكان واحد. أسعار واضحة بـ USDT ودفع بالعملات الرقمية ودعم مباشر عبر تيليجرام.',
 browse:'تصفح المنتجات', talk:'تحدث عبر تيليجرام', minLabel:'الحد الأدنى لكل منتج', minValue:'٥ وحدات', currencyLabel:'عملة الأسعار', deliveryLabel:'التسليم', deliveryValue:'يدوي · تيليجرام',
 catalog:'اشتراكك التالي يبدأ هنا.', catalogSub:'اختر المنتجات واطلب ٥ وحدات على الأقل من كل منتج.', all:'جميع المنتجات', work:'العمل والإنتاجية', creative:'أدوات إبداعية', learning:'التعلم', other:'أخرى',
 search:'ابحث عن منتج…', each:'للوحدة', add:'إضافة إلى الطلب', demo:'مثال', noResults:'لا توجد منتجات مطابقة.',
 preparing:'المتجر قيد التجهيز. تواصل مع الدعم لمعرفة التوفر والطلب.',
 howTitle:'ثلاث خطوات لطلب بسيط.', step1:'١. اختيار المنتجات', step1Text:'اختر المنتجات والكميات وراجع المبلغ الكامل قبل الدفع.',
 step2:'٢. الدفع وإرسال الإيصال', step2Text:'ادفع بـ LTC أو USDT على شبكة BEP-20 وأرسل رقم الطلب والإيصال عبر تيليجرام.',
 step3:'٣. المراجعة والتسليم اليدوي', step3Text:'بعد التحقق اليدوي من الدفع، يرسل الدعم الملف أو معلومات الحساب.',
 contactTitle:'لديك سؤال قبل الطلب؟', contactText:'تحدث معنا عن التوفر وتفاصيل الاشتراك ومتابعة التسليم.',
 footer:'LionXsec Shop · اشتراكات رقمية بالجملة', manual:'يتم التحقق من الدفع والتسليم يدويًا.',
 cart:'طلبك', empty:'سلة الطلب فارغة.', remove:'حذف', quantity:'الكمية', subtotal:'المجموع الفرعي', total:'الإجمالي', checkout:'المتابعة لتسجيل الطلب',
 close:'إغلاق', minimum:'الحد الأدنى ٥ وحدات لكل منتج.', added:'تمت الإضافة إلى طلبك.', back:'رجوع', payment:'طريقة الدفع',
 network:'الشبكة', ltcRate:'السعر اليدوي: 1 LTC =', quoteNotice:'يُحسب مبلغ LTC بالسعر الذي أدخله المدير. تحقق من صلاحية المبلغ قبل الدفع.',
 unavailable:'غير متاح حاليًا', telegram:'اسم تيليجرام (اختياري)', telegramHint:'مثال @your_username. أرسل رقم الطلب عند التواصل مع الدعم.',
 place:'تسجيل الطلب والحصول على عنوان الدفع', ordering:'جارٍ التسجيل…', notReady:'هذا منتج تجريبي أو الدفع غير جاهز. تواصل مع الدعم.',
 order:'رقم الطلب', orderSaved:'تم تسجيل الطلب.', awaiting_payment:'بانتظار الدفع', under_review:'قيد المراجعة اليدوية', paid:'تم تأكيد الدفع', delivered:'تم التسليم', cancelled:'ملغى',
 payAmount:'المبلغ المطلوب', address:'عنوان الاستلام', copy:'نسخ', copied:'تم النسخ.', copyFailed:'تعذر النسخ التلقائي. حدد النص وانسخه.',
 networkWarning:'استخدم الشبكة المعروضة فقط. الإرسال عبر شبكة أخرى قد يؤدي إلى فقدان الأموال.',
 expires:'المبلغ صالح حتى', expired:'انتهت صلاحية المبلغ. تواصل مع الدعم قبل الدفع.',
 receiptInstructions:'أرسل رقم الطلب ومعرف المعاملة أو صورة الإيصال إلى @link_Lion. تسجيل الطلب لا يؤكد الدفع.',
 copyMessage:'نسخ رسالة الطلب', sendTelegram:'فتح محادثة تيليجرام', refresh:'تحديث الحالة', previousOrder:'عرض آخر طلب',
 receiptDraft:'مرحبًا، يرجى التحقق من الدفع لهذا الطلب.', txPlaceholder:'معرف المعاملة / الإيصال: [أضف هنا]',
 adminTitle:'لوحة المتجر', loginTitle:'دخول الإدارة', password:'كلمة مرور الإدارة', login:'دخول', logout:'خروج',
 setupHint:'عند الإعداد الأول، أنشئ كلمة المرور على الخادم بالأمر python server.py init-admin.',
 products:'المنتجات', wallets:'الدفع والمحافظ', orders:'الطلبات', newProduct:'منتج جديد', edit:'تعديل', delete:'حذف',
 productName:'اسم المنتج', duration:'مدة الاشتراك', delivery:'طريقة التسليم', price:'سعر الوحدة (USDT)', category:'الفئة', active:'ظاهر في المتجر',
 save:'حفظ التغييرات', cancel:'إلغاء', translations:'تفاصيل المنتج مطلوبة باللغات الأربع.', saved:'تم الحفظ.', deleteConfirm:'حذف المنتج؟ ستُحفظ الطلبات السابقة.',
 usdtWallet:'عنوان استلام USDT العام — BEP-20 (BSC)', ltcWallet:'عنوان استلام LTC العام — Litecoin',
 publicOnly:'أدخل عناوين الاستلام العامة فقط. لا تدخل المفتاح الخاص أو عبارة الاسترداد.', rate:'قيمة 1 LTC بعملة USDT',
 rateHelp:'أدخل السعر وحدثه كل ٢٤ ساعة على الأقل. السعر القديم يعطل دفع LTC. صلاحية مبلغ الطلب ٣٠ دقيقة.',
 lastUpdated:'آخر تسجيل للسعر', noRate:'غير مسجل', noOrders:'لا توجد طلبات بعد.', status:'الحالة', details:'التفاصيل',
 notes:'ملاحظات داخلية', txid:'معرف المعاملة (اختياري)', manualConfirm:'تحققت شخصيًا من الدفع أو أكملت التسليم.',
 statusHint:'الحالات سجل يدوي؛ الموقع لا يتحقق من المعاملات ولا يرسل الملفات.', units:'وحدات', draftHelp:'إذا لم يُدرج النص في تيليجرام، انسخ رسالة الطلب أولًا.',
 errors:{generic:'تعذر تنفيذ الطلب. حاول مجددًا.', minimum_quantity:'اختر من ٥ إلى ١٠٠٠٠ وحدة لكل منتج.', invalid_credentials:'كلمة مرور غير صحيحة.', unauthorized:'سجل الدخول مجددًا.', csrf:'أعد تحميل الصفحة.',
 admin_not_configured:'أنشئ كلمة مرور الإدارة أولًا.', translations_required:'أدخل الترجمات الأربع.', invalid_translation:'كل ترجمة مطلوبة وبحد أقصى ٢٥٠ حرفًا.', invalid_price:'أدخل سعرًا موجبًا بمنزلتين عشريتين كحد أقصى.',
 invalid_usdt_wallet:'عنوان BEP-20 غير صالح.', invalid_ltc_wallet:'عنوان Litecoin أو المجموع الاختباري غير صالح.', invalid_rate:'أدخل سعر صرف موجبًا صالحًا.', payment_unavailable:'طريقة الدفع غير جاهزة.',
 rate_expired:'سعر LTC قديم. تواصل مع الدعم.', product_unavailable:'المنتج تجريبي أو غير متاح.', invalid_telegram:'أدخل اسم تيليجرام صالحًا.', manual_confirmation_required:'أكد التحقق اليدوي أولًا.',
 invalid_status_transition:'تغيير الحالة غير مسموح.', invalid_txid:'يجب أن يتكون المعرف من ٦٤ رقمًا سداسيًا مع 0x اختياري.', rate_limited:'طلبات كثيرة. حاول لاحقًا.', not_found:'غير موجود.', origin:'عنوان الموقع لا يطابق إعداد الخادم.'}
},
es: {
 shop:'Tienda', process:'Cómo funciona', support:'Soporte', admin:'Administración', wholesale:'SUSCRIPCIONES DIGITALES AL POR MAYOR', productLogo:'Logotipo del servicio', serviceCollection:'Servicios conocidos. Un solo destino.', brandNote:'Tienda independiente. Los logotipos identifican los servicios.',
 heroA:'Compra cuentas prémium al por mayor con garantía', heroB:'y herramientas privadas difíciles de encontrar.', heroText:'Tus suscripciones digitales en un solo pedido. Precios claros en USDT, pagos con criptomonedas y atención directa por Telegram.',
 browse:'Explorar productos', talk:'Hablar por Telegram', minLabel:'Mínimo por producto', minValue:'5 unidades', currencyLabel:'Precios en', deliveryLabel:'Entrega', deliveryValue:'Manual · Telegram',
 catalog:'Tu próxima suscripción empieza aquí.', catalogSub:'Elige tus productos. Pide al menos 5 unidades de cada uno.', all:'Todos', work:'Trabajo y productividad', creative:'Herramientas creativas', learning:'Aprendizaje', other:'Otros',
 search:'Buscar productos…', each:'por unidad', add:'Añadir al pedido', demo:'Ejemplo', noResults:'No hay productos que coincidan.', preparing:'Estamos preparando la tienda. Contacta con soporte para consultar disponibilidad y pedidos.',
 howTitle:'Tres pasos. Un pedido sencillo.', step1:'01. Elige tus productos', step1Text:'Selecciona los productos y cantidades. Consulta el total antes de pagar.',
 step2:'02. Paga y envía el comprobante', step2Text:'Paga con LTC o USDT en BEP-20. Envía el número de pedido y el comprobante por Telegram.',
 step3:'03. Revisión y entrega manual', step3Text:'Tras verificar manualmente el pago, soporte te enviará el archivo o los datos de la cuenta.',
 contactTitle:'¿Alguna pregunta antes de comprar?', contactText:'Habla con nosotros sobre disponibilidad, suscripciones o entregas.', footer:'LionXsec Shop · Suscripciones digitales al por mayor', manual:'Los pagos se revisan y los pedidos se entregan manualmente.',
 cart:'Tu pedido', empty:'Tu pedido está vacío.', remove:'Eliminar', quantity:'Cantidad', subtotal:'Subtotal', total:'Total del pedido', checkout:'Continuar con el pedido', close:'Cerrar', minimum:'El mínimo es de 5 unidades por producto.', added:'Añadido a tu pedido.', back:'Volver', payment:'Método de pago',
 network:'Red', ltcRate:'Tipo manual: 1 LTC =', quoteNotice:'LTC se calcula con el tipo fijado por el administrador. Comprueba la validez del importe antes de pagar.', unavailable:'No disponible', telegram:'Usuario de Telegram (opcional)', telegramHint:'Por ejemplo @your_username. Incluye tu número de pedido al contactar con soporte.',
 place:'Crear pedido y obtener dirección de pago', ordering:'Creando pedido…', notReady:'Es un producto de ejemplo o el pago no está listo. Contacta con soporte.',
 order:'Número de pedido', orderSaved:'Pedido creado.', awaiting_payment:'Pendiente de pago', under_review:'En revisión manual', paid:'Pago confirmado', delivered:'Entregado', cancelled:'Cancelado',
 payAmount:'Importe a enviar', address:'Dirección de recepción', copy:'Copiar', copied:'Copiado.', copyFailed:'No se pudo copiar automáticamente. Selecciona y copia el texto.', networkWarning:'Utiliza únicamente la red indicada. Enviar por otra red puede causar la pérdida de fondos.',
 expires:'Importe válido hasta', expired:'El importe ha caducado. Contacta con soporte antes de pagar.', receiptInstructions:'Envía el número de pedido y el ID de transacción o una imagen del comprobante a @link_Lion. Crear un pedido no confirma el pago.',
 copyMessage:'Copiar mensaje del pedido', sendTelegram:'Abrir chat de Telegram', refresh:'Actualizar estado', previousOrder:'Ver último pedido', receiptDraft:'Hola, revisa el pago de este pedido, por favor.', txPlaceholder:'ID de transacción / comprobante: [añadir aquí]',
 adminTitle:'Panel de la tienda', loginTitle:'Acceso de administración', password:'Contraseña', login:'Entrar', logout:'Salir', setupHint:'Primero, crea la contraseña en el servidor con python server.py init-admin.',
 products:'Productos', wallets:'Pagos y monederos', orders:'Pedidos', newProduct:'Nuevo producto', edit:'Editar', delete:'Eliminar', productName:'Nombre del producto', duration:'Duración', delivery:'Método de entrega', price:'Precio unitario (USDT)', category:'Categoría', active:'Visible en la tienda',
 save:'Guardar cambios', cancel:'Cancelar', translations:'Los datos del producto son obligatorios en los cuatro idiomas.', saved:'Guardado.', deleteConfirm:'¿Eliminar el producto? Los pedidos anteriores se conservarán.',
 usdtWallet:'Dirección pública USDT — BEP-20 (BSC)', ltcWallet:'Dirección pública LTC — Litecoin', publicOnly:'Introduce solo direcciones públicas de recepción. Nunca introduzcas claves privadas ni frases de recuperación.', rate:'Valor de 1 LTC en USDT',
 rateHelp:'Introduce tu tipo y actualízalo al menos cada 24 horas. Un tipo antiguo desactiva los pagos LTC. El importe de cada pedido es válido durante 30 minutos.', lastUpdated:'Última actualización', noRate:'Sin configurar', noOrders:'Aún no hay pedidos.', status:'Estado', details:'Detalles', notes:'Notas internas', txid:'ID de transacción (opcional)', manualConfirm:'He verificado personalmente el pago o completado la entrega.',
 statusHint:'El estado es un registro manual. La web no verifica transacciones ni envía archivos.', units:'unidades', draftHelp:'Si Telegram no incluye el texto, copia primero el mensaje del pedido.',
 errors:{generic:'La solicitud falló. Inténtalo de nuevo.', minimum_quantity:'Selecciona entre 5 y 10 000 unidades por producto.', invalid_credentials:'Contraseña incorrecta.', unauthorized:'Inicia sesión de nuevo.', csrf:'Recarga la página.', admin_not_configured:'Configura primero la contraseña de administración.',
 translations_required:'Introduce las cuatro traducciones.', invalid_translation:'Todas las traducciones son obligatorias, hasta 250 caracteres.', invalid_price:'Introduce un precio positivo con dos decimales como máximo.', invalid_usdt_wallet:'Dirección BEP-20 no válida.', invalid_ltc_wallet:'Dirección Litecoin o suma de comprobación no válida.', invalid_rate:'Introduce un tipo positivo válido.',
 payment_unavailable:'Este método de pago no está configurado.', rate_expired:'El tipo LTC ha caducado. Contacta con soporte.', product_unavailable:'Producto de ejemplo, eliminado o inactivo.', invalid_telegram:'Introduce un usuario de Telegram válido.', manual_confirmation_required:'Confirma primero la revisión manual.', invalid_status_transition:'Cambio de estado no permitido.', invalid_txid:'El ID debe tener 64 dígitos hexadecimales con 0x opcional.', rate_limited:'Demasiadas solicitudes. Inténtalo más tarde.', not_found:'No encontrado.', origin:'La dirección no coincide con la configuración del servidor.'}
}
};

const FEATURES = {
fa:{tutorials:'آموزش‌های ویدیویی',tools:'ابزارهای رایگان',uploads:'فایل‌های آپلودشده',learningSub:'ویدیوهای راهنما را همین‌جا تماشا کنید.',toolsSub:'ابزارهای رایگان و لینک دانلود آن‌ها.',newTutorial:'آموزش جدید',newTool:'ابزار جدید',title:'عنوان',description:'توضیحات',published:'نمایش عمومی',uploadLogo:'انتخاب و آپلود لوگو از سیستم',logoHint:'PNG، JPG یا WebP؛ حداکثر ۳ مگابایت.',removeLogo:'حذف لوگوی اختصاصی',uploadVideo:'انتخاب و آپلود ویدیو از سیستم',videoHint:'MP4 یا WebM؛ حداکثر ۲۵۰ مگابایت.',downloadLink:'لینک دانلود HTTPS',download:'دانلود رایگان',watch:'تماشای ویدیو',noTutorials:'هنوز آموزشی منتشر نشده است.',noTools:'هنوز ابزاری منتشر نشده است.',noUploads:'هنوز فایلی آپلود نشده است.',copyTranslations:'کپی این متن به زبان‌های خالی',translationsCopied:'متن‌ها در زبان‌های خالی کپی شدند؛ می‌توانید ترجمه‌ها را ویرایش کنید.',uploading:'در حال آپلود',uploadComplete:'آپلود شد',deleteContentConfirm:'این محتوا حذف شود؟ فایل آپلودشده در کتابخانه باقی می‌ماند.',deleteUploadConfirm:'این فایلِ بدون استفاده برای همیشه حذف شود؟',size:'اندازه',fileName:'نام فایل',currentVideo:'ویدیوی فعلی',productHelp:'برای افزودن محصول، نام، مدت و روش تحویل را وارد کنید. برای زبان‌های خالی از دکمهٔ کپی متن استفاده کنید.',contentHelp:'عنوان و توضیحات را وارد کنید؛ زبان‌های خالی را با دکمهٔ کپی پر کنید.',errors:{unsupported_upload:'فرمت فایل پشتیبانی نمی‌شود. برای لوگو PNG/JPG/WebP و برای ویدیو MP4/WebM انتخاب کنید.',upload_too_large:'حجم فایل بیشتر از حد مجاز است.',media_not_found:'فایل پیدا نشد یا نوع آن درست نیست.',media_in_use:'این فایل در محصول یا محتوا استفاده شده است؛ ابتدا ارتباط آن را حذف کنید.',video_required:'ابتدا ویدیو را آپلود کنید.',invalid_download_url:'یک لینک کامل HTTPS بدون نام کاربری یا رمز وارد کنید.',upload_timeout:'مهلت آپلود تمام شد. دوباره تلاش کنید.',upload_cancelled:'آپلود لغو شد.',incomplete_upload:'فایل کامل دریافت نشد. دوباره آپلود کنید.',invalid_resource:'اطلاعات محتوا معتبر نیست.'}},
en:{tutorials:'Video tutorials',tools:'Free tools',uploads:'Uploaded files',learningSub:'Watch helpful guides right here.',toolsSub:'Free tools and their download links.',newTutorial:'New tutorial',newTool:'New tool',title:'Title',description:'Description',published:'Publicly visible',uploadLogo:'Choose & upload logo from your computer',logoHint:'PNG, JPG or WebP; maximum 3 MB.',removeLogo:'Remove custom logo',uploadVideo:'Choose & upload video from your computer',videoHint:'MP4 or WebM; maximum 250 MB.',downloadLink:'HTTPS download link',download:'Free download',watch:'Watch video',noTutorials:'No tutorials published yet.',noTools:'No tools published yet.',noUploads:'No uploaded files yet.',copyTranslations:'Copy this text into empty languages',translationsCopied:'Copied into empty languages. You can edit each translation.',uploading:'Uploading',uploadComplete:'Uploaded',deleteContentConfirm:'Delete this content? The uploaded file stays in the library.',deleteUploadConfirm:'Permanently delete this unused file?',size:'Size',fileName:'Filename',currentVideo:'Current video',productHelp:'Enter the name, duration and delivery method. Use the copy button to fill empty languages.',contentHelp:'Enter the title and description. Use the copy button to fill empty languages.',errors:{unsupported_upload:'Unsupported file. Use PNG/JPG/WebP for logos or MP4/WebM for videos.',upload_too_large:'The file exceeds the upload limit.',media_not_found:'File not found or wrong media type.',media_in_use:'This file is used by a product or content. Remove that reference first.',video_required:'Upload a video first.',invalid_download_url:'Enter a complete HTTPS URL without a username or password.',upload_timeout:'The upload timed out. Try again.',upload_cancelled:'Upload cancelled.',incomplete_upload:'The file was not fully received. Upload it again.',invalid_resource:'Invalid content details.'}},
ar:{tutorials:'دروس الفيديو',tools:'أدوات مجانية',uploads:'الملفات المرفوعة',learningSub:'شاهد الأدلة التعليمية هنا.',toolsSub:'أدوات مجانية وروابط تنزيلها.',newTutorial:'درس جديد',newTool:'أداة جديدة',title:'العنوان',description:'الوصف',published:'ظاهر للعموم',uploadLogo:'اختيار ورفع شعار من جهازك',logoHint:'PNG أو JPG أو WebP؛ بحد أقصى ٣ ميغابايت.',removeLogo:'إزالة الشعار الخاص',uploadVideo:'اختيار ورفع فيديو من جهازك',videoHint:'MP4 أو WebM؛ بحد أقصى ٢٥٠ ميغابايت.',downloadLink:'رابط تنزيل HTTPS',download:'تنزيل مجاني',watch:'مشاهدة الفيديو',noTutorials:'لا توجد دروس منشورة بعد.',noTools:'لا توجد أدوات منشورة بعد.',noUploads:'لا توجد ملفات مرفوعة بعد.',copyTranslations:'نسخ هذا النص إلى اللغات الفارغة',translationsCopied:'تم النسخ؛ يمكنك تعديل كل ترجمة.',uploading:'جارٍ الرفع',uploadComplete:'تم الرفع',deleteContentConfirm:'حذف المحتوى؟ يبقى الملف في المكتبة.',deleteUploadConfirm:'حذف هذا الملف غير المستخدم نهائيًا؟',size:'الحجم',fileName:'اسم الملف',currentVideo:'الفيديو الحالي',productHelp:'أدخل الاسم والمدة وطريقة التسليم. انسخ النص إلى اللغات الفارغة بالزر.',contentHelp:'أدخل العنوان والوصف ثم انسخهما إلى اللغات الفارغة.',errors:{unsupported_upload:'نوع الملف غير مدعوم. استخدم PNG/JPG/WebP للشعار أو MP4/WebM للفيديو.',upload_too_large:'الملف يتجاوز الحد المسموح.',media_not_found:'الملف غير موجود أو نوعه غير صحيح.',media_in_use:'الملف مستخدم. أزل ارتباطه بالمنتج أو المحتوى أولًا.',video_required:'ارفع فيديو أولًا.',invalid_download_url:'أدخل رابط HTTPS كاملًا بدون اسم مستخدم أو كلمة مرور.',upload_timeout:'انتهت مهلة الرفع.',upload_cancelled:'تم إلغاء الرفع.',incomplete_upload:'لم يصل الملف كاملًا. أعد الرفع.',invalid_resource:'بيانات المحتوى غير صالحة.'}},
es:{tutorials:'Videotutoriales',tools:'Herramientas gratuitas',uploads:'Archivos subidos',learningSub:'Mira las guías directamente aquí.',toolsSub:'Herramientas gratuitas y enlaces de descarga.',newTutorial:'Nuevo tutorial',newTool:'Nueva herramienta',title:'Título',description:'Descripción',published:'Visible públicamente',uploadLogo:'Elegir y subir logotipo desde tu equipo',logoHint:'PNG, JPG o WebP; máximo 3 MB.',removeLogo:'Quitar logotipo personalizado',uploadVideo:'Elegir y subir vídeo desde tu equipo',videoHint:'MP4 o WebM; máximo 250 MB.',downloadLink:'Enlace de descarga HTTPS',download:'Descarga gratuita',watch:'Ver vídeo',noTutorials:'Todavía no hay tutoriales publicados.',noTools:'Todavía no hay herramientas publicadas.',noUploads:'Todavía no hay archivos subidos.',copyTranslations:'Copiar este texto a los idiomas vacíos',translationsCopied:'Copiado a los idiomas vacíos. Puedes editar cada traducción.',uploading:'Subiendo',uploadComplete:'Subido',deleteContentConfirm:'¿Eliminar este contenido? El archivo seguirá en la biblioteca.',deleteUploadConfirm:'¿Eliminar permanentemente este archivo sin usar?',size:'Tamaño',fileName:'Nombre del archivo',currentVideo:'Vídeo actual',productHelp:'Introduce nombre, duración y entrega. Usa el botón para rellenar los idiomas vacíos.',contentHelp:'Introduce título y descripción y cópialos a los idiomas vacíos.',errors:{unsupported_upload:'Formato no compatible. Usa PNG/JPG/WebP para logos o MP4/WebM para vídeos.',upload_too_large:'El archivo supera el límite.',media_not_found:'Archivo no encontrado o tipo incorrecto.',media_in_use:'El archivo está en uso. Quita primero su referencia.',video_required:'Sube primero un vídeo.',invalid_download_url:'Introduce una URL HTTPS completa sin usuario ni contraseña.',upload_timeout:'La subida ha caducado.',upload_cancelled:'Subida cancelada.',incomplete_upload:'No se recibió el archivo completo. Inténtalo de nuevo.',invalid_resource:'Datos del contenido no válidos.'}}
};
for(const [language,{errors,...words}] of Object.entries(FEATURES)){Object.assign(TEXT[language],words);Object.assign(TEXT[language].errors,errors);}

export let lang = LANGS.includes(localStorage.getItem('lx-language')) ? localStorage.getItem('lx-language') : 'fa';
export const t = key => TEXT[lang][key] ?? TEXT.en[key] ?? key;
export const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const amount = cents => new Intl.NumberFormat(lang, {minimumFractionDigits:2,maximumFractionDigits:2}).format(cents/100);
export const date = ts => new Intl.DateTimeFormat(lang, {dateStyle:'medium',timeStyle:'short'}).format(new Date(ts*1000));
export const name = value => value?.[lang] || value?.en || '';
export function brandFor(product) {
 if (product?.brand && product.brand in BRANDS) return product.brand;
 const title=(product?.name?.en || '').toLowerCase().replace(/[^a-z0-9]/g,'');
 return Object.keys(BRANDS).find(key=>key!=='generic' && title.includes(key)) || 'generic';
}
export function brandLogo(brand, css='service-logo') {
 const key=brand in BRANDS ? brand : 'generic';
 const source=key==='generic'?'lion-logo.png':key+'.svg';
 return `<img class="${css}${key==='generic'?' lion-logo':''}" src="/assets/${source}" alt="${BRANDS[key]}" width="64" height="64">`;
}
export function productLogo(product,css='service-logo') {
 if(typeof product?.logo_id==='string' && /^[0-9a-f]{32}$/.test(product.logo_id))return `<img class="${css} uploaded-logo" src="/media/${product.logo_id}" alt="${esc(name(product.name))}" width="64" height="64">`;
 return brandLogo(brandFor(product),css);
}
export function copyTranslations(form,fields,currentLanguage) {
 for(const field of fields){
  const source=form.elements[field+'_'+currentLanguage]?.value.trim() || LANGS.map(l=>form.elements[field+'_'+l]?.value.trim()).find(Boolean) || '';
  for(const language of LANGS){const input=form.elements[field+'_'+language];if(input && !input.value.trim())input.value=source;}
 }
 toast(t('translationsCopied'));
}
export function uploadFile(file,kind,csrf,onProgress=()=>{}) {
 let xhr;
 const promise=new Promise((resolve,reject)=>{
  xhr=new XMLHttpRequest();xhr.open('POST','/api/admin/uploads?kind='+kind);xhr.withCredentials=true;
  xhr.setRequestHeader('X-CSRF-Token',csrf);xhr.setRequestHeader('X-Upload-Name',encodeURIComponent(file.name));xhr.setRequestHeader('Content-Type','application/octet-stream');
  xhr.upload.onprogress=e=>{if(e.lengthComputable)onProgress(Math.round(e.loaded/e.total*100));};
  xhr.onload=()=>{let result;try{result=JSON.parse(xhr.responseText);}catch{result={error:'generic'};}
   if(xhr.status>=200 && xhr.status<300)resolve(result);else reject(new Error(TEXT[lang].errors[result.error] || t('errors').generic));};
  xhr.onerror=()=>reject(new Error(t('errors').generic));xhr.onabort=()=>reject(new Error(t('errors').upload_cancelled));xhr.send(file);
 });
 promise.abort=()=>xhr?.abort();return promise;
}
export function setLanguage(value) {
 if (!LANGS.includes(value)) return;
 lang = value; localStorage.setItem('lx-language', lang);
 document.documentElement.lang = lang;
 document.documentElement.dir = ['fa','ar'].includes(lang) ? 'rtl' : 'ltr';
 document.querySelectorAll('[data-i18n]').forEach(el => el.textContent = t(el.dataset.i18n));
 document.querySelectorAll('[data-placeholder]').forEach(el => el.placeholder = t(el.dataset.placeholder));
 document.querySelectorAll('.language').forEach(el => el.value = lang);
 window.dispatchEvent(new Event('languagechange'));
}
export function setupLanguage() {
 document.querySelectorAll('.language').forEach(el => {
  el.innerHTML = LANGS.map(l => `<option value="${l}">${LANGUAGE_NAMES[l]}</option>`).join('');
  el.addEventListener('change', () => setLanguage(el.value));
 });
 setLanguage(lang);
}
let timer;
export function toast(text, error=false) {
 const el = document.getElementById('toast');
 el.textContent = text; el.classList.toggle('is-error', error); el.hidden=false;
 clearTimeout(timer); timer=setTimeout(() => el.hidden=true, 4500);
}
export async function api(path, options={}) {
 const res = await fetch(path, {credentials:'same-origin', ...options,
  headers:{'Content-Type':'application/json',...options.headers}});
 const data = await res.json();
 if (!res.ok) { const e = new Error(TEXT[lang].errors[data.error] || TEXT.en.errors[data.error] || t('errors').generic); e.code=data.error; e.status=res.status; throw e; }
 return data;
}
export async function copy(text) {
 try { await navigator.clipboard.writeText(text); toast(t('copied')); }
 catch { toast(t('copyFailed'),true); }
}
export const icon = (type='arrow') => {
 const paths = {arrow:'M5 12h14m-6-6 6 6-6 6', bag:'M5 7h14l1 14H4L5 7Zm4 0V5a3 3 0 0 1 6 0v2',
  plus:'M12 5v14M5 12h14', close:'m6 6 12 12M6 18 18 6', check:'m5 12 4 4L19 6', search:'m21 21-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  work:'M4 8h16v12H4V8Zm4 0V4h8v4M4 13h16m-9-2v4h2v-4', creative:'m4 20 4-1L20 7l-3-3L5 16l-1 4Zm10-13 3 3',
  learning:'M3 4h7l2 2 2-2h7v15h-7l-2 2-2-2H3V4Zm9 2v15', other:'M5 5h5v5H5V5Zm9 0h5v5h-5V5ZM5 14h5v5H5v-5Zm9 0h5v5h-5v-5'};
 return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[type] || paths.arrow}"/></svg>`;
};
