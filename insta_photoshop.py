"""کنترل فتوشاپ ادمین (ویندوز) برای کاور اینستاگرام.

قالب = فایل PSD خود ادمین. یه بار «آماده‌سازی» میشه:
  - لایه‌های متن پیدا و اسم‌گذاری میشن: TITLE (بزرگ‌ترین متن)، TAG (متن بالای تیتر)، SUB (متن پایین تیتر)
  - کادر دور تگ (اگه هست) → TAG_BOX ، لایه‌ی عکس (بزرگ‌ترین لایه‌ی عکس زیر متن‌ها) → IMAGE
  - گرادیان تأییدشده‌ی بات به‌صورت لایه‌ی ARIKO_GRADIENT اضافه میشه (گرادیان‌های قبلی فایل فقط خاموش میشن)
  - نتیجه کنار فایل اصلی با پسوند _ARIKO.psd ذخیره و توی فتوشاپ باز میشه تا ادمین چک/ویرایش کنه.
بعد از تأیید، برای هر پست فقط عکس لایه‌ی IMAGE و نوشته/رنگ TITLE/TAG/SUB عوض میشه؛ جای لایه‌ها، فونت، اندازه و
بقیه‌ی فایل دست نمی‌خوره. پست توی یه تب جدید فتوشاپ باز می‌مونه؛ ادمین چک می‌کنه و با دکمه‌ی ربات خروجی JPG
توی پوشه‌ی خودش ذخیره میشه. قالب هیچ‌وقت ذخیره نمیشه.

نیاز: فتوشاپ نصب روی همین کامپیوتر + pip install pywin32
"""
import json
import os
import threading

_lock = threading.Lock()      # فتوشاپ هم‌زمان فقط یه کار


class PhotoshopError(Exception):
    pass


def available():
    try:
        import win32com.client  # noqa: F401
        return True, ""
    except ImportError:
        return False, "کتابخونه‌ی pywin32 نصب نیست: pip install pywin32"


def _js_path(p):
    return os.path.abspath(p).replace("\\", "/")


# کتابخونه‌ی مشترک JSX (ExtendScript = جاوااسکریپت قدیمی، JSON نداره)
_JSX_LIB = r"""
function sTID(s){return stringIDToTypeID(s);}
function q(s){return '"' + String(s).replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\n/g,'\\n') + '"';}
function ser(v){
  if (v === null || v === undefined) return 'null';
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (typeof v === 'string') return q(v);
  if (v instanceof Array){var a=[];for(var i=0;i<v.length;i++)a.push(ser(v[i]));return '['+a.join(',')+']';}
  var o=[];for(var k in v){if(v.hasOwnProperty(k))o.push(q(k)+':'+ser(v[k]));}return '{'+o.join(',')+'}';
}
function px(u){return u.as('px');}
function allLayers(container, out){
  for (var i=0;i<container.layers.length;i++){
    var l=container.layers[i];
    if (l.typename=='LayerSet'){allLayers(l,out);} else out.push(l);
  }
  return out;
}
function byName(doc,name){var ls=allLayers(doc,[]);for(var i=0;i<ls.length;i++)if(ls[i].name==name)return ls[i];return null;}
function openOrDup(path){
  // اگه فایل همین الان توی فتوشاپ باز باشه، روی کپیش کار می‌کنیم که تغییرات ادمین از دست نره
  var f=new File(path);
  for (var i=0;i<app.documents.length;i++){
    var d=app.documents[i];
    try{ if (d.fullName && d.fullName.fsName.toLowerCase()==f.fsName.toLowerCase()){ app.activeDocument=d; return {doc:d.duplicate('ariko_work'), opened:false, unsaved:!d.saved}; } }catch(e){}
  }
  var d2=app.open(f);
  var w=d2.duplicate('ariko_work');
  d2.close(SaveOptions.DONOTSAVECHANGES);
  return {doc:w, opened:true, unsaved:false};
}
function styleColor(style){
  try{var c=style.getObjectValue(sTID('color'));return [c.getDouble(sTID('red')),c.getDouble(sTID('grain')),c.getDouble(sTID('blue'))];}catch(e){return null;}
}
function textKeyOf(layer){
  app.activeDocument.activeLayer=layer;
  var ref=new ActionReference();ref.putEnumerated(sTID('layer'),sTID('ordinal'),sTID('targetEnum'));
  return executeActionGet(ref).getObjectValue(sTID('textKey'));
}
function cloneDesc(d){var n=new ActionDescriptor();n.fromStream(d.toStream());return n;}
function rgbDesc(c){var d=new ActionDescriptor();d.putDouble(sTID('red'),c[0]);d.putDouble(sTID('grain'),c[1]);d.putDouble(sTID('blue'),c[2]);return d;}
function diff(a,b){return !a||!b?999:Math.abs(a[0]-b[0])+Math.abs(a[1]-b[1])+Math.abs(a[2]-b[2]);}
function colorAt(layer,pos){
  var st=textKeyOf(layer).getList(sTID('textStyleRange'));
  for (var i=0;i<st.count;i++){var r=st.getObjectValue(i); if(r.getInteger(sTID('from'))<=pos && pos<r.getInteger(sTID('to'))) return styleColor(r.getObjectValue(sTID('textStyle')));}
  return null;
}
function colorRange(layer,a,b,rgb){
  // فقط رنگ همون تیکه عوض میشه؛ فونت/اندازه/کشیدگی/فاصله‌ها دست نمی‌خوره
  app.activeDocument.activeLayer=layer;
  var desc=new ActionDescriptor(), ref=new ActionReference();
  ref.putProperty(sTID('property'),sTID('textStyle'));
  ref.putEnumerated(sTID('textLayer'),sTID('ordinal'),sTID('targetEnum'));
  desc.putReference(sTID('null'),ref);
  var st=new ActionDescriptor();
  st.putInteger(sTID('from'),a); st.putInteger(sTID('to'),b);
  st.putInteger(sTID('textOverrideFeatureName'),808465458);
  st.putInteger(sTID('typeStyleOperationType'),3);
  st.putObject(sTID('color'),sTID('RGBColor'),rgbDesc(rgb));
  desc.putObject(sTID('to'),sTID('textStyle'),st);
  executeAction(sTID('set'),desc,DialogModes.NO);
}
function keepLook(layer){
  var t=layer.textItem, k={};
  try{k.size=t.size;}catch(e){} try{k.h=t.horizontalScale;}catch(e){} try{k.v=t.verticalScale;}catch(e){}
  try{k.track=t.tracking;}catch(e){} try{ if(!t.useAutoLeading) k.lead=t.leading; }catch(e){}
  return k;
}
function restoreLook(layer,k){
  var t=layer.textItem;
  try{ if(k.size!==undefined && Math.abs(t.size.as('pt')-k.size.as('pt'))>0.01) t.size=k.size; }catch(e){}
  try{ if(k.h!==undefined && t.horizontalScale!=k.h) t.horizontalScale=k.h; }catch(e){}
  try{ if(k.v!==undefined && t.verticalScale!=k.v) t.verticalScale=k.v; }catch(e){}
  try{ if(k.track!==undefined && t.tracking!=k.track) t.tracking=k.track; }catch(e){}
  try{ if(k.lead!==undefined && Math.abs(t.leading.as('pt')-k.lead.as('pt'))>0.01) t.leading=k.lead; }catch(e){}
}
function findRanges(layer, names){
  // جای اسم‌ها رو توی متنی که فتوشاپ واقعاً نگه داشته پیدا می‌کنیم (بعضی کاراکترها مثل نیم‌فاصله رو حذف می‌کنه)
  var t=String(layer.textItem.contents), out=[];
  for (var i=0;i<names.length;i++){
    var cands=[names[i], names[i].replace(/\u00a0/g,' '), names[i].replace(/ /g,'\u00a0')];
    for (var j=0;j<cands.length;j++){ var k=t.indexOf(cands[j]); if(k>=0){ out.push([k,k+cands[j].length]); break; } }
  }
  out.sort(function(a,b){return a[0]-b[0];});
  return out;
}
function setText(layer, text, names, hcOverride){
  // names: اسم‌هایی که رنگ «هایلایت» قالب (زرد اسم انیمه) رو می‌گیرن؛ hcOverride: رنگی که ادمین از ربات انتخاب کرده
  var look=keepLook(layer);
  var tk=textKeyOf(layer), styles=tk.getList(sTID('textStyleRange'));
  var baseStyle=cloneDesc(styles.getObjectValue(0).getObjectValue(sTID('textStyle')));
  var bc=styleColor(baseStyle), hc=null;
  for (var i=1;i<styles.count;i++){
    var c=styleColor(styles.getObjectValue(i).getObjectValue(sTID('textStyle')));
    if (diff(c,bc)>30){hc=c;break;}
  }
  if (!hc) hc=[251,221,27];
  if (hcOverride) hc=hcOverride;
  layer.textItem.contents=text;
  restoreLook(layer,look);
  if (!names || !names.length) return;
  var ranges=findRanges(layer,names);
  if (!ranges.length) return;
  text=String(layer.textItem.contents);
  var ok=true;
  try{
    for (var j=0;j<ranges.length;j++) colorRange(layer,ranges[j][0],ranges[j][1],hc);
    for (var j2=0;j2<ranges.length;j2++){ if (diff(colorAt(layer,ranges[j2][0]),hc)>30) ok=false; }
    if (ranges[0][0]>0 && diff(colorAt(layer,0),bc)>30) ok=false;
    if (ranges[ranges.length-1][1]<text.length && diff(colorAt(layer,text.length-1),bc)>30) ok=false;
  }catch(e){ ok=false; }
  if (ok) return;
  // روش دوم (اگه نسخه‌ی فتوشاپ روش اول رو قبول نکرد): بازنویسی بازه‌های استایل + برگردوندن اندازه/کشیدگی
  layer.textItem.contents=text;
  tk=textKeyOf(layer);
  var hi=cloneDesc(baseStyle); hi.putObject(sTID('color'),sTID('RGBColor'),rgbDesc(hc));
  var list=new ActionList(), pos=0;
  function add(a,b,st){ if(b<=a)return; var r=new ActionDescriptor(); r.putInteger(sTID('from'),a); r.putInteger(sTID('to'),b); r.putObject(sTID('textStyle'),sTID('textStyle'),st); list.putObject(sTID('textStyleRange'),r); }
  for (var k=0;k<ranges.length;k++){ add(pos,ranges[k][0],baseStyle); add(ranges[k][0],ranges[k][1],hi); pos=ranges[k][1]; }
  add(pos,text.length,baseStyle);
  tk.putList(sTID('textStyleRange'),list);
  var d=new ActionDescriptor(), ref=new ActionReference();
  ref.putEnumerated(sTID('layer'),sTID('ordinal'),sTID('targetEnum'));
  d.putReference(sTID('null'),ref); d.putObject(sTID('to'),sTID('textLayer'),tk);
  executeAction(sTID('set'),d,DialogModes.NO);
  restoreLook(layer,look);
}
function scaleText(layer, k){
  // اندازه‌ی متن ×k (و فاصله‌ی خط‌ها اگه دستی بود)؛ جای لایه بعدش تنظیم میشه
  if (!k || Math.abs(k-1)<0.001) return;
  var t=layer.textItem;
  try{ t.size=new UnitValue(t.size.as('pt')*k,'pt'); }catch(e){}
  try{ if(!t.useAutoLeading) t.leading=new UnitValue(t.leading.as('pt')*k,'pt'); }catch(e){}
}
function findLogo(doc){
  // لایه‌ای به اسم LOGO، وگرنه یه لایه‌ی کوچیک (غیرمتنی) گوشه‌ی بالای کادر
  var l=byName(doc,'LOGO'); if (l) return l;
  var W=px(doc.width), H=px(doc.height), ls=allLayers(doc,[]), best=null;
  for (var i=0;i<ls.length;i++){
    var x=ls[i]; if (!x.visible || x.kind==LayerKind.TEXT) continue;
    var b=x.bounds, w=px(b[2])-px(b[0]), h=px(b[3])-px(b[1]);
    if (w<=0||h<=0||w>W*0.25||h>H*0.15||px(b[1])>H*0.15) continue;
    if (!best || w*h>best.a) best={l:x,a:w*h};
  }
  return best?best.l:null;
}
function setLogoColor(doc, rgb){
  var logo=findLogo(doc); if (!logo) return false;
  app.activeDocument=doc; doc.activeLayer=logo;
  var ref=new ActionReference(); ref.putEnumerated(sTID('layer'),sTID('ordinal'),sTID('targetEnum'));
  var desc=executeActionGet(ref);
  if (!desc.hasKey(sTID('layerEffects'))) return false;
  var fx=desc.getObjectValue(sTID('layerEffects')), done=false;
  if (fx.hasKey(sTID('solidFill'))){
    var sf=fx.getObjectValue(sTID('solidFill')); sf.putObject(sTID('color'),sTID('RGBColor'),rgbDesc(rgb));
    fx.putObject(sTID('solidFill'),sTID('solidFill'),sf); done=true;
  }
  if (fx.hasKey(sTID('solidFillMulti'))){
    var list=fx.getList(sTID('solidFillMulti')), nl=new ActionList();
    for (var i=0;i<list.count;i++){ var it=list.getObjectValue(i); it.putObject(sTID('color'),sTID('RGBColor'),rgbDesc(rgb)); nl.putObject(sTID('solidFill'),it); }
    fx.putList(sTID('solidFillMulti'),nl); done=true;
  }
  if (!done) return false;
  var d=new ActionDescriptor(), r=new ActionReference();
  r.putProperty(sTID('property'),sTID('layerEffects')); r.putEnumerated(sTID('layer'),sTID('ordinal'),sTID('targetEnum'));
  d.putReference(sTID('null'),r); d.putObject(sTID('to'),sTID('layerEffects'),fx);
  executeAction(sTID('set'),d,DialogModes.NO);
  return true;
}
function placeFull(doc, pngPath, below, name){
  // PNG هم‌اندازه‌ی کادر → لایه‌ی جدید دقیقاً زیر/جای لایه‌ی below
  var src=app.open(new File(pngPath));
  // PNG با 72ppi باز میشه؛ بدون این، فتوشاپ موقع انتقال به سند 300ppi لایه رو بزرگ/تار می‌کنه
  try{ src.resizeImage(undefined, undefined, doc.resolution, ResampleMethod.NONE); }catch(e){}
  var l=src.layers[0]; if (l.isBackgroundLayer) l.isBackgroundLayer=false;
  var dup=l.duplicate(doc, ElementPlacement.PLACEATBEGINNING);
  src.close(SaveOptions.DONOTSAVECHANGES);
  app.activeDocument=doc;
  var b=dup.bounds; dup.translate(-px(b[0]),-px(b[1]));
  dup.name=name;
  return dup;
}
"""

_JSX_INSPECT = r"""
(function(){
  app.displayDialogs=DialogModes.NO;
  var o=openOrDup(ARGS.path), doc=o.doc, out={w:px(doc.width),h:px(doc.height),texts:[],pixels:[],unsaved:o.unsaved};
  var ls=allLayers(doc,[]);
  for (var i=0;i<ls.length;i++){
    var l=ls[i], b=l.bounds, info={name:l.name,top:px(b[1]),bottom:px(b[3]),left:px(b[0]),right:px(b[2]),visible:l.visible,kind:String(l.kind)};
    if (l.kind==LayerKind.TEXT){ try{info.size=l.textItem.size.as('pt');}catch(e){info.size=0;} out.texts.push(info);} else out.pixels.push(info);
  }
  doc.close(SaveOptions.DONOTSAVECHANGES);
  return ser(out);
})();
"""

_JSX_SETUP = r"""
(function(){
  app.displayDialogs=DialogModes.NO;
  var o=openOrDup(ARGS.path), doc=o.doc, m=ARGS.map;
  var ls=allLayers(doc,[]);
  function rename(oldName,newName){ if(!oldName)return; var l=byName(doc,oldName); if(l) l.name=newName; }
  rename(m.TITLE,'TITLE'); rename(m.TAG,'TAG'); rename(m.SUB,'SUB'); rename(m.TAG_BOX,'TAG_BOX'); rename(m.IMAGE,'IMAGE');
  for (var i=0;i<ls.length;i++){ try{ if (ls[i].kind==LayerKind.GRADIENTFILL) ls[i].visible=false; }catch(e){} }
  var old=byName(doc,'ARIKO_GRADIENT'); if(old) old.remove();
  var img=byName(doc,'IMAGE');
  var g=placeFull(doc, ARGS.gradient, img, 'ARIKO_GRADIENT');
  if (img) g.move(img, ElementPlacement.PLACEBEFORE);
  var opts=new PhotoshopSaveOptions(); opts.layers=true;
  doc.saveAs(new File(ARGS.out), opts, true);
  doc.close(SaveOptions.DONOTSAVECHANGES);
  app.open(new File(ARGS.out));       // برای بازبینی ادمین باز می‌مونه
  return ser({ok:true});
})();
"""

_JSX_PREPARE = r"""
(function(){
  app.displayDialogs=DialogModes.NO;
  var o=openOrDup(ARGS.template), doc=o.doc;
  function need(n){var l=byName(doc,n); if(!l) throw new Error('لایه‌ی '+n+' توی قالب نیست'); return l;}
  // عکس
  var img=need('IMAGE');
  var ni=placeFull(doc, ARGS.image, img, 'IMAGE_NEW');
  ni.move(img, ElementPlacement.PLACEAFTER);
  img.remove(); ni.name='IMAGE';
  // پس‌زمینه‌ی سفید قالب (فقط توی این کپی) مشکی میشه که اگه عکس کادر رو پر نکرد، دورش سفید نمونه
  try{ var bgl=null; for (var bi=0;bi<doc.artLayers.length;bi++) if (doc.artLayers[bi].isBackgroundLayer) bgl=doc.artLayers[bi];
       if (bgl){ doc.activeLayer=bgl; var fc=new SolidColor(); fc.rgb.red=7; fc.rgb.green=7; fc.rgb.blue=7;
                 doc.selection.selectAll(); doc.selection.fill(fc); doc.selection.deselect(); } }catch(e){}
  if (ARGS.native_xy){
    // اندازه‌ی اصلی عکس: فقط جابه‌جا میشه (وسط/بالا)، هیچ تغییر اندازه‌ای نداره؛ Smart Object که ادمین بی‌افت کیفیت بزرگ/کوچیکش کنه
    ni.translate(ARGS.native_xy[0], ARGS.native_xy[1]);
    try{ app.activeDocument.activeLayer=ni; executeAction(sTID('newPlacedLayer'), undefined, DialogModes.NO); ni=app.activeDocument.activeLayer; ni.name='IMAGE'; }catch(e){}
  }
  // متن‌ها: فقط نوشته و رنگ عوض میشه، جا و اندازه‌ی لایه‌ها همونیه که توی قالبه
  var title=need('TITLE');
  setText(title, ARGS.title, ARGS.names, ARGS.hi_rgb);
  scaleText(title, ARGS.title_scale);
  // تیتر کوتاه‌تر/بلندتر از نمونه‌ی قالب: پایین تیتر (و تگ بالاش) همون‌جای قالب می‌مونه؛ فونت و اندازه دست نمی‌خوره
  var delta=ARGS.title_bottom ? ARGS.title_bottom - px(title.bounds[3]) : 0;
  var ky=px(doc.height)/1440;                              // جابه‌جایی‌های ربات روی کادر ۱۴۴۰ پیکسلیه
  delta+= (ARGS.title_dy||0)*ky;
  if (Math.abs(delta)>0.5) title.translate(0, delta);
  var tag=byName(doc,'TAG'), box=byName(doc,'TAG_BOX');
  if (tag){ if (ARGS.tag){ setText(tag, ARGS.tag, []); tag.visible=true; if(Math.abs(delta)>0.5) tag.translate(0,delta); } else tag.visible=false; }
  if (box){ box.visible=!!ARGS.tag; if (ARGS.tag && Math.abs(delta)>0.5) box.translate(0,delta); }
  var sub=byName(doc,'SUB');
  if (sub){ if (ARGS.sub){ setText(sub, ARGS.sub, []); sub.visible=true;
              var sb=px(sub.bounds[1]); scaleText(sub, ARGS.sub_scale);
              var sd=sb-px(sub.bounds[1])+(ARGS.sub_dy||0)*ky; if(Math.abs(sd)>0.5) sub.translate(0, sd); }
            else sub.visible=false; }
  // رنگ لوگو نسبت به پس‌زمینه (Color Overlay لایه‌ی لوگو): روشن → مشکی، تیره → سفید
  if (ARGS.logo_rgb) setLogoColor(doc, ARGS.logo_rgb);
  // همین سند باز می‌مونه تا ادمین چک کنه؛ خروجی با دکمه‌ی ربات (یا دستی)
  var d2=doc.duplicate(ARGS.docname); doc.close(SaveOptions.DONOTSAVECHANGES);
  app.activeDocument=d2;
  return ser({ok:true, doc:d2.name});
})();
"""

_JSX_FINISH = r"""
(function(){
  app.displayDialogs=DialogModes.NO;
  var doc=null;
  for (var i=0;i<app.documents.length;i++) if (app.documents[i].name==ARGS.docname) doc=app.documents[i];
  if (!doc) throw new Error('سند «'+ARGS.docname+'» توی فتوشاپ باز نیست (بسته شده؟)');
  if (ARGS.drop){ doc.close(SaveOptions.DONOTSAVECHANGES); return ser({ok:true}); }
  app.activeDocument=doc;
  if (ARGS.psd){ var po0=new PhotoshopSaveOptions(); po0.layers=true; doc.saveAs(new File(ARGS.psd), po0, true); ARGS.psd=''; }
  // مثل «Save for Web» خود ادمین: تبدیل به sRGB (تلگرام/اینستا پروفایل‌های دیگه رو نمی‌فهمن و رنگ کدر میشه) + JPEG کیفیت ۸۰ Optimized
  try{ doc.convertProfile('sRGB IEC61966-2.1', Intent.RELATIVECOLORIMETRIC, true, true); }catch(e){}
  var wo=new ExportOptionsSaveForWeb();
  wo.format=SaveDocumentType.JPEG; wo.quality=ARGS.quality; wo.optimized=true; wo.includeProfile=false; wo.blur=0;
  doc.exportDocument(new File(ARGS.jpg), ExportType.SAVEFORWEB, wo);
  if (ARGS.psd){ var po=new PhotoshopSaveOptions(); po.layers=true; doc.saveAs(new File(ARGS.psd), po, true); }
  doc.close(SaveOptions.DONOTSAVECHANGES);
  return ser({ok:true});
})();
"""


def _run(script, args):
    ok, why = available()
    if not ok:
        raise PhotoshopError(why)
    import pythoncom
    import win32com.client
    code = "var ARGS = " + json.dumps(args, ensure_ascii=False) + ";\n" + _JSX_LIB + "\n" + \
           "try { " + script + " } catch (e) { '{\"error\":' + q(e.message + ' (line ' + e.line + ')') + '}'; }"
    with _lock:
        pythoncom.CoInitialize()
        try:
            try:
                app = win32com.client.Dispatch("Photoshop.Application")    # اگه بسته باشه خودش باز میشه
            except Exception as exc:
                raise PhotoshopError(f"فتوشاپ باز نشد (نصبه؟): {exc}")
            res = app.DoJavaScript(code)
        finally:
            pythoncom.CoUninitialize()
    try:
        data = json.loads(res or "{}")
    except Exception:
        raise PhotoshopError(f"جواب نامفهوم از فتوشاپ: {str(res)[:200]}")
    if isinstance(data, dict) and data.get("error"):
        raise PhotoshopError(data["error"])
    return data


def inspect(path):
    return _run(_JSX_INSPECT, {"path": _js_path(path)})


def guess_map(info):
    """حدس لایه‌ها: بزرگ‌ترین متن = تیتر؛ متن بالای تیتر = تگ؛ متن پایین تیتر = زیرنویس."""
    texts = [t for t in info.get("texts", []) if t.get("visible", True)] or info.get("texts", [])
    if not texts:
        raise PhotoshopError("توی فایل هیچ لایه‌ی متنی نیست؛ تیتر/تگ/زیرنویس رو به‌صورت لایه‌ی متن بذار.")
    named = {t["name"]: t for t in texts}
    if "TITLE" in named:                                    # قبلاً آماده‌سازی شده
        title = named["TITLE"]
    else:
        title = max(texts, key=lambda t: (t.get("size") or 0, t["bottom"] - t["top"]))
    rest = [t for t in texts if t is not title]
    above = [t for t in rest if t["bottom"] <= title["top"] + 5]
    below = [t for t in rest if t["top"] >= title["bottom"] - 5]
    tag = named.get("TAG") or (max(above, key=lambda t: t["bottom"]) if above else None)
    sub = named.get("SUB") or (min(below, key=lambda t: t["top"]) if below else None)
    box = None
    if tag:
        cx, cy = (tag["left"] + tag["right"]) / 2, (tag["top"] + tag["bottom"]) / 2
        boxes = [p for p in info.get("pixels", []) if p["left"] <= cx <= p["right"] and p["top"] <= cy <= p["bottom"]
                 and (p["right"] - p["left"]) < info["w"] * 0.6 and p.get("visible", True)]
        if boxes:
            box = min(boxes, key=lambda p: (p["right"] - p["left"]) * (p["bottom"] - p["top"]))
    imgs = [p for p in info.get("pixels", []) if p.get("visible", True)
            and any(k in p.get("kind", "").upper() for k in ("NORMAL", "SMARTOBJECT"))
            and (p["right"] - p["left"]) >= info["w"] * 0.6 and (p["bottom"] - p["top"]) >= info["h"] * 0.4]
    named_px = {p["name"]: p for p in info.get("pixels", [])}
    image = named_px.get("IMAGE") or (max(imgs, key=lambda p: (p["right"] - p["left"]) * (p["bottom"] - p["top"]))
                                      if imgs else None)
    if not image:
        raise PhotoshopError("لایه‌ی عکس پیدا نشد؛ اسم لایه‌ی عکس رو IMAGE بذار و دوباره امتحان کن.")
    return {"TITLE": title["name"], "TAG": tag["name"] if tag else "", "SUB": sub["name"] if sub else "",
            "TAG_BOX": box["name"] if box else "", "IMAGE": image["name"]}


def setup(path, gradient_png, out_path, layer_map):
    return _run(_JSX_SETUP, {"path": _js_path(path), "gradient": _js_path(gradient_png),
                             "out": _js_path(out_path), "map": layer_map})


def prepare(template, image_png, title, names, tag, sub, docname, title_bottom=0, logo_rgb=None, native_xy=None, adj=None):
    """پست رو توی فتوشاپ می‌سازه و باز میذاره (ذخیره نمی‌کنه) تا ادمین چک کنه.
    adj: تنظیم دستی متن از ربات — ts/ss اندازه‌ی تیتر/زیرنویس، ty/sy جابه‌جایی (پیکسل کادر ۱۴۴۰)، hc رنگ بخش رنگی."""
    adj = adj or {}
    return _run(_JSX_PREPARE, {
        "title_scale": float(adj.get("ts") or 1.0), "title_dy": float(adj.get("ty") or 0),
        "sub_scale": float(adj.get("ss") or 1.0), "sub_dy": float(adj.get("sy") or 0),
        "hi_rgb": list(adj["hc"]) if adj.get("hc") else None,
        "template": _js_path(template), "image": _js_path(image_png), "title": title, "names": names,
        "tag": _ps_text(tag), "sub": _ps_text(sub), "docname": docname, "title_bottom": float(title_bottom or 0),
        "logo_rgb": list(logo_rgb) if logo_rgb else None,
        "native_xy": list(native_xy) if native_xy else None,
    })


def _ps_text(text):
    """فتوشاپ ادمین نیم‌فاصله رو نشون نمیده (انیمه‌ی → انیمهی)؛ مثل تایپ خود ادمین با فاصله."""
    return (text or "").replace("\u200c", " ")


def finish(docname, jpg_path, psd_path="", quality=80, tmp_dir=""):
    """خروجی JPG (Save for Web) از سندی که ادمین چک کرده و بستنش.
    اول توی یه مسیر انگلیسی موقت ذخیره میشه (Save for Web با اسم‌های فارسی/طولانی مشکل داره) بعد جابه‌جا میشه."""
    import shutil
    import time
    tmp = os.path.join(tmp_dir or os.path.dirname(jpg_path), f"ariko_export_{int(time.time())}.jpg")
    res = _run(_JSX_FINISH, {"docname": docname, "jpg": _js_path(tmp), "quality": int(quality),
                             "psd": _js_path(psd_path) if psd_path else "", "drop": False})
    if not os.path.exists(tmp):
        raise PhotoshopError("فتوشاپ فایل خروجی رو نساخت")
    shutil.move(tmp, jpg_path)
    return res


def drop(docname):
    return _run(_JSX_FINISH, {"docname": docname, "jpg": "", "psd": "", "drop": True})


def gradient_png(path, size):
    """گرادیان تأییدشده (نسخه‌ی ۷) به‌صورت PNG مشکیِ نیمه‌شفاف هم‌اندازه‌ی قالب."""
    import numpy as np
    from PIL import Image
    import insta_cover
    w, h = size
    alpha = insta_cover.gradient_alpha(h)
    alpha = np.maximum(alpha, 1.0 / 255)            # حداقل ۱ تا لایه تمام‌کادر باشه (برای جاگذاری دقیق)
    a = np.repeat((alpha * 255).round().astype(np.uint8)[:, None], w, axis=1)
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = insta_cover.DARK.astype(np.uint8)
    rgba[..., 3] = a
    Image.fromarray(rgba, "RGBA").save(path)
    return path


def title_and_names(title):
    """«... [Name] ...» → (متن بدون براکت، اسم‌هایی که باید زرد بشن). اسم کوتاه با فاصله‌ی نشکن که وسطش خط نشکنه."""
    import re
    text, names = "", []
    for i, part in enumerate(re.split(r"\[([^\]]+)\]", title or "")):
        if i % 2:
            name = " ".join(part.split())
            if len(name) <= 22:
                name = name.replace(" ", "\u00a0")
            names.append(name)
            text += name
        else:
            text += _ps_text(part)
    return re.sub(r" {2,}", " ", text).strip(), names
