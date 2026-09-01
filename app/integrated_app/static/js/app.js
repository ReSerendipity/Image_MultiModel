/* ===== app.js — 完整前端逻辑（迁移自旧 static/index.html）===== */
// 主题/语言防闪烁已由 base.html 内联脚本处理
var I18N={
'zh-CN':{nav_home:'首页',nav_generate:'生图',nav_batch:'批量',nav_history:'历史',nav_status:'状态',nav_settings:'设置',preset:'预设',save_preset:'保存当前为预设',recent:'最近生成',neg_add:'＋ 负向提示词',neg_hide:'− 收起负向提示词',btn_generate:'▶ 生成',btn_advanced:'⚙ 高级参数',btn_gallery:'▦ 图片展示',btn_history:'◷ 历史记录',btn_batch:'▤ 批量模式',btn_presets:'▣ 预设管理',btn_share:'分享',btn_clear:'清空',btn_copy:'复制',btn_free_vram:'释放显存',btn_restore_default:'恢复默认',btn_done:'完成',btn_generate_batch:'▶ 生成批次',btn_cancel:'取消',batch_prompt_file:'Prompt 文件',batch_param_grid:'参数网格',search_placeholder:'搜索',phase_connecting:'连接中',phase_loading_workflow:'加载工作流',phase_engine_ready:'引擎就绪',phase_patching:'打补丁',phase_queuing:'排队中',phase_sampling:'采样中',phase_executing:'执行节点',phase_image_saved:'已保存',phase_completed:'完成',phase_cancelling:'取消中'},
'zh-TW':{nav_home:'首頁',nav_generate:'生圖',nav_batch:'批量',nav_history:'歷史',nav_status:'狀態',nav_settings:'設定',preset:'預設',save_preset:'儲存目前為預設',recent:'最近生成',neg_add:'＋ 負向提示詞',neg_hide:'− 收起負向提示詞',btn_generate:'▶ 生成',btn_advanced:'⚙ 進階參數',btn_gallery:'▦ 圖片展示',btn_history:'◷ 歷史記錄',btn_batch:'▤ 批量模式',btn_presets:'▣ 預設管理',btn_share:'分享',btn_clear:'清空',btn_copy:'複製',btn_free_vram:'釋放顯存',btn_restore_default:'恢復預設',btn_done:'完成',btn_generate_batch:'▶ 生成批次',btn_cancel:'取消',batch_prompt_file:'Prompt 檔案',batch_param_grid:'參數網格',search_placeholder:'搜尋',phase_connecting:'連接中',phase_loading_workflow:'載入工作流程',phase_engine_ready:'引擎就緒',phase_patching:'修補中',phase_queuing:'排隊中',phase_sampling:'採樣中',phase_executing:'執行節點',phase_image_saved:'已儲存',phase_completed:'完成',phase_cancelling:'取消中'},
'en-US':{nav_home:'Home',nav_generate:'Generate',nav_batch:'Batch',nav_history:'History',nav_status:'Status',nav_settings:'Settings',preset:'Preset',save_preset:'Save as preset',recent:'Recent',neg_add:'＋ Negative prompt',neg_hide:'− Hide negative prompt',btn_generate:'▶ Generate',btn_advanced:'⚙ Advanced',btn_gallery:'▦ Gallery',btn_history:'◷ History',btn_batch:'▤ Batch',btn_presets:'▣ Presets',btn_share:'Share',btn_clear:'Clear',btn_copy:'Copy',btn_free_vram:'Free VRAM',btn_restore_default:'Reset',btn_done:'Done',btn_generate_batch:'▶ Generate Batch',btn_cancel:'Cancel',batch_prompt_file:'Prompt File',batch_param_grid:'Param Grid',search_placeholder:'Search',phase_connecting:'Connecting',phase_loading_workflow:'Loading workflow',phase_engine_ready:'Engine ready',phase_patching:'Patching',phase_queuing:'Queuing',phase_sampling:'Sampling',phase_executing:'Executing',phase_image_saved:'Image saved',phase_completed:'Completed',phase_cancelling:'Cancelling'},
'ja-JP':{nav_home:'ホーム',nav_generate:'生成',nav_batch:'バッチ',nav_history:'履歴',nav_status:'ステータス',nav_settings:'設定',preset:'プリセット',save_preset:'プリセット保存',recent:'最近の生成',neg_add:'＋ ネガティブプロンプト',neg_hide:'− 閉じる',btn_generate:'▶ 生成',btn_advanced:'⚙ 詳細設定',btn_gallery:'▦ ギャラリー',btn_history:'◷ 履歴',btn_batch:'▤ バッチ',btn_presets:'▣ プリセット',btn_share:'共有',btn_clear:'クリア',btn_copy:'コピー',btn_free_vram:'VRAM解放',btn_restore_default:'デフォルトに戻す',btn_done:'完了',btn_generate_batch:'▶ バッチ生成',btn_cancel:'キャンセル',batch_prompt_file:'Promptファイル',batch_param_grid:'パラメータグリッド',search_placeholder:'検索',phase_connecting:'接続中',phase_loading_workflow:'ワークフロー読み込み中',phase_engine_ready:'エンジン準備完了',phase_patching:'パッチ適用中',phase_queuing:'キューに追加中',phase_sampling:'サンプリング中',phase_executing:'ノード実行中',phase_image_saved:'保存済み',phase_completed:'完了',phase_cancelling:'キャンセル中'},
'ko-KR':{nav_home:'홈',nav_generate:'생성',nav_batch:'배치',nav_history:'기록',nav_status:'상태',nav_settings:'설정',preset:'프리셋',save_preset:'현재를 프리셋으로 저장',recent:'최근 생성',neg_add:'＋ 네거티브 프롬프트',neg_hide:'− 접기',btn_generate:'▶ 생성',btn_advanced:'⚙ 고급 매개변수',btn_gallery:'▦ 갤러리',btn_history:'◷ 기록',btn_batch:'▤ 배치',btn_presets:'▣ 프리셋',btn_share:'공유',btn_clear:'지우기',btn_copy:'복사',btn_free_vram:'VRAM 해제',btn_restore_default:'기본값 복원',btn_done:'완료',btn_generate_batch:'▶ 배치 생성',btn_cancel:'취소',batch_prompt_file:'Prompt 파일',batch_param_grid:'매개변수 그리드',search_placeholder:'검색',phase_connecting:'연결 중',phase_loading_workflow:'워크플로 로드 중',phase_engine_ready:'엔진 준비 완료',phase_patching:'패치 적용 중',phase_queuing:'대기열 추가 중',phase_sampling:'샘플링 중',phase_executing:'노드 실행 중',phase_image_saved:'저장됨',phase_completed:'완료',phase_cancelling:'취소 중'}
};
var langSel=document.getElementById('langSelect');
function applyLang(l){document.documentElement.setAttribute('data-lang',l);var d=I18N[l]||I18N['zh-CN'];document.querySelectorAll('[data-i18n]').forEach(function(el){var k=el.getAttribute('data-i18n');if(d[k])el.textContent=d[k];});document.querySelectorAll('[data-i18n-ph]').forEach(function(el){var k=el.getAttribute('data-i18n-ph');if(d[k])el.placeholder=d[k];});/* 动态元素：negToggle 根据开关状态设置 */var nt=document.getElementById('negToggle');if(nt){var open=nt.classList.contains('open');nt.textContent=open?(d.neg_hide||'− '):(d.neg_add||'＋ ');}}
function trPhase(phase){var l=document.documentElement.getAttribute('data-lang')||'zh-CN';var d=I18N[l]||I18N['zh-CN'];return d[phase]||phase;}
function escHtml(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
langSel.addEventListener('change',function(e){applyLang(e.target.value);});
/* 顶栏图标菜单：引擎 / 语言 */
var engMenu=document.getElementById('engMenu'),langMenu=document.getElementById('langMenu');
function closeMenus(){engMenu.classList.remove('show');langMenu.classList.remove('show');}
document.getElementById('engIcon').addEventListener('click',function(e){e.stopPropagation();langMenu.classList.remove('show');engMenu.classList.toggle('show');});
document.getElementById('langIcon').addEventListener('click',function(e){e.stopPropagation();engMenu.classList.remove('show');langMenu.classList.toggle('show');});
document.querySelectorAll('#engMenu .ip-item').forEach(function(b){b.addEventListener('click',function(){document.querySelectorAll('#engMenu .ip-item').forEach(function(x){x.classList.remove('on');});b.classList.add('on');document.getElementById('engineSelect').value=b.dataset.v;document.getElementById('engineSelect').dispatchEvent(new Event('change'));closeMenus();});});
document.querySelectorAll('#langMenu .ip-item').forEach(function(b){b.addEventListener('click',function(){document.querySelectorAll('#langMenu .ip-item').forEach(function(x){x.classList.remove('on');});b.classList.add('on');langSel.value=b.dataset.l;localStorage.setItem('imm_lang',b.dataset.l);applyLang(b.dataset.l);closeMenus();});});
document.addEventListener('click',function(e){if(!e.target.closest('.ico-wrap'))closeMenus();});
/* ---------- 主题 ---------- */
var themeBtn=document.getElementById('themeToggle');
/* 主题切换持久化逻辑在 F10 节统一处理，此处不再绑定 */
/* ---------- 抽屉总控 ---------- */
var drawer=document.getElementById('drawer'),scrim=document.getElementById('scrim');
var mTitle=document.getElementById('mTitle'),mHint=document.getElementById('mHint'),drawerFoot=document.getElementById('drawerFoot');
var MODULES={adv:['高级参数','22 项 · 改动即时生效','sec-adv',false],presets:['预设管理','与生图页联动','sec-presets',true]};
function closeHist(){document.getElementById('histDrawer').classList.remove('open');}
function closeGalleryD(){document.getElementById('galleryDrawer').classList.remove('open');}
function openRight(key){
  closeBottom();closeTop();closeHist();closeGalleryD();
  var m=MODULES[key];
  mTitle.textContent=m[0];mHint.textContent=m[1];
  document.querySelectorAll('.drawer-sec').forEach(function(s){s.classList.remove('active');});
  document.getElementById(m[2]).classList.add('active');
  drawer.classList.toggle('wide',m[3]);
  drawerFoot.classList.toggle('hide',key!=='adv');
  if(key==='adv')loadLoras();
  drawer.classList.add('open');scrim.classList.add('show');
}
function closeRight(){drawer.classList.remove('open');scrim.classList.remove('show');}
document.getElementById('drawerToggle').addEventListener('click',function(){openRight('adv');});
document.getElementById('drawerClose').addEventListener('click',closeRight);
document.getElementById('drawerDone').addEventListener('click',closeRight);
scrim.addEventListener('click',function(){closeRight();closeBottom();});
function openHistD(){closeRight();closeBottom();closeTop();closeGalleryD();document.getElementById('histDrawer').classList.add('open');showHistList();}
function openGalleryD(){closeRight();closeBottom();closeTop();closeHist();document.getElementById('galleryDrawer').classList.add('open');renderGallery();}
document.getElementById('openGallery').addEventListener('click',openGalleryD);
document.getElementById('openHistory').addEventListener('click',openHistD);
document.getElementById('openPresets').addEventListener('click',function(){openRight('presets');showPList();});
document.getElementById('openBatch').addEventListener('click',function(){closeRight();closeTop();closeHist();closeGalleryD();document.getElementById('batchDrawer').classList.add('open');renderBatchQueue();});
document.getElementById('histClose').addEventListener('click',closeHist);
document.getElementById('galleryClose').addEventListener('click',closeGalleryD);
/* ---------- 底部/顶部抽屉 ---------- */
function closeBottom(){['setDrawer','aboutDrawer','batchDrawer'].forEach(function(id){document.getElementById(id).classList.remove('open');});['setScrim'].forEach(function(id){document.getElementById(id).classList.remove('show');});}
function closeTop(){document.getElementById('statDrawer').classList.remove('open');}
var setD=document.getElementById('setDrawer'),setSc=document.getElementById('setScrim');
function openSet(){closeRight();closeBottom();closeTop();closeHist();closeGalleryD();setD.classList.add('open');setSc.classList.add('show');}
document.getElementById('setOpen').addEventListener('click',function(){openSet();});
document.getElementById('setClose').addEventListener('click',function(){setD.classList.remove('open');setSc.classList.remove('show');});
setSc.addEventListener('click',function(){setD.classList.remove('open');setSc.classList.remove('show');});
var aboutDrawer=document.getElementById('aboutDrawer');
function openAbout(){closeRight();closeBottom();closeTop();closeHist();closeGalleryD();aboutDrawer.classList.add('open');}
document.getElementById('aboutBtn').addEventListener('click',openAbout);
document.getElementById('aboutClose').addEventListener('click',function(){aboutDrawer.classList.remove('open');});
document.getElementById('batchClose').addEventListener('click',function(){document.getElementById('batchDrawer').classList.remove('open');});
var statD=document.getElementById('statDrawer');
function openStat(){closeRight();closeBottom();closeHist();closeGalleryD();statD.classList.add('open');}
document.querySelectorAll('.sb-click').forEach(function(el){el.addEventListener('click',function(){openStat();});});
document.getElementById('statClose').addEventListener('click',closeTop);
/* ---------- Esc ---------- */
document.addEventListener('keydown',function(e){if(e.key==='Escape'){closeRight();closeBottom();closeTop();closeHist();closeGalleryD();viewer.classList.remove('show');qpop.classList.remove('show');}});
/* ---------- 负向提示词 / 示例 / Prompt ---------- */
var negBox=document.getElementById('negBox'),negToggle=document.getElementById('negToggle');
negToggle.addEventListener('click',function(){var open=negBox.classList.toggle('open');var d=I18N[langSel.value]||I18N['zh-CN'];negToggle.textContent=open?d.neg_hide:d.neg_add;});
var posPrompt=document.getElementById('posPrompt'),negPrompt=document.getElementById('negPrompt');
function updatePosMeta(){document.getElementById('posMeta').textContent=posPrompt.value.length+' 字符 · ≈'+Math.max(1,Math.round(posPrompt.value.length/0.7))+' token';}
function updateNegMeta(){document.getElementById('negMeta').textContent=negPrompt.value.length+' 字符';}
posPrompt.addEventListener('input',updatePosMeta);negPrompt.addEventListener('input',updateNegMeta);
document.getElementById('clearPos').addEventListener('click',function(){posPrompt.value='';updatePosMeta();});
document.getElementById('copyPos').addEventListener('click',function(){posPrompt.select();document.execCommand('copy');});
document.getElementById('clearNeg').addEventListener('click',function(){negPrompt.value='';updateNegMeta();});
document.getElementById('copyNeg').addEventListener('click',function(){negPrompt.select();document.execCommand('copy');});
document.querySelectorAll('.p-chip').forEach(function(c){c.addEventListener('click',function(){document.querySelectorAll('.p-chip').forEach(function(x){x.classList.remove('on');});c.classList.add('on');});});
/* ---------- 手风琴 / stepper / 滑块 / LoRA / dice / batch ---------- */
document.querySelectorAll('.acc-head').forEach(function(h){h.addEventListener('click',function(){h.parentElement.classList.toggle('open');});});
document.querySelectorAll('.stepper').forEach(function(s){var inp=s.querySelector('input'),step=+(s.dataset.step||1),min=+(s.dataset.min||-Infinity),max=+(s.dataset.max||Infinity);s.querySelector('.st-dec').addEventListener('click',function(){inp.value=Math.max(min,(+inp.value||0)-step);inp.dispatchEvent(new Event('input'));});s.querySelector('.st-inc').addEventListener('click',function(){inp.value=Math.min(max,(+inp.value||0)+step);inp.dispatchEvent(new Event('input'));});});
document.querySelectorAll('.quick-sz').forEach(function(q){q.querySelectorAll('button').forEach(function(b){b.addEventListener('click',function(){q.querySelectorAll('button').forEach(function(x){x.classList.remove('on');});b.classList.add('on');var tg=q.closest('.fgroup').querySelector('.stepper input');tg.value=b.textContent;tg.dispatchEvent(new Event('input'));});});});
document.querySelectorAll('.range-row input[type=range]').forEach(function(r){var v=r.nextElementSibling;function upd(){v.textContent=(+r.value).toFixed(2);v.style.color=Math.abs(+r.value)>1.5?'var(--red)':'var(--accent)';}r.addEventListener('input',upd);upd();});
document.querySelectorAll('.lora-name').forEach(function(sel){sel.addEventListener('change',function(){var row=sel.closest('.lora-row');row.classList.toggle('disabled',sel.value==='— 禁用 —');});});
document.querySelectorAll('.dice').forEach(function(b){b.addEventListener('click',function(){var inp=document.getElementById(b.dataset.target);inp.value=Math.floor(Math.random()*9007199254740991);inp.dispatchEvent(new Event('input'));if(b.dataset.target==='seed'){document.getElementById('seedHint').textContent='实际 seed：'+inp.value;document.getElementById('seedHint').style.color='var(--accent)';}});});
document.getElementById('reuseSeed').addEventListener('click',function(){API.get('/tasks?page=1&page_size=1').then(function(r){var t=r.tasks&&r.tasks[0];var s=t&&t.generation_config?t.generation_config.seed:null;if(s===undefined||s===null||s===-1){s=Math.floor(Math.random()*9007199254740991);}var e=document.getElementById('seed');e.value=s;e.dispatchEvent(new Event('input'));document.getElementById('seedHint').textContent='实际 seed：'+s;document.getElementById('seedHint').style.color='var(--accent)';}).catch(function(){var s=Math.floor(Math.random()*9007199254740991);var e=document.getElementById('seed');e.value=s;e.dispatchEvent(new Event('input'));document.getElementById('seedHint').textContent='实际 seed：'+s;});});
document.getElementById('b10').addEventListener('click',function(){var e=document.getElementById('batchSize');e.value=Math.min(9999,(+e.value||0)+10);e.dispatchEvent(new Event('input'));});
document.getElementById('b100').addEventListener('click',function(){var e=document.getElementById('batchSize');e.value=Math.min(9999,(+e.value||0)+100);e.dispatchEvent(new Event('input'));});
document.getElementById('restoreBtn').addEventListener('click',function(){resetToDefaults();});
/* ---------- 估算 + 快照 ---------- */
function estCount(){var n=+document.getElementById('batchSize').value||1;return {n:n,coef:1,total:n};}
function syncChips(){document.getElementById('snapRes').textContent=document.getElementById('width').value+' × '+document.getElementById('height').value;document.getElementById('snapSteps').textContent=document.getElementById('steps').value;document.getElementById('snapCfg').textContent=document.getElementById('cfg').value;document.getElementById('snapOut').textContent=estCount().total;var es=document.getElementById('engineSelect');document.getElementById('snapEngine').textContent=(window.ENGINES&&ENGINES[es.value])||(es.selectedOptions&&es.selectedOptions[0]&&es.selectedOptions[0].textContent)||'—';}
function updateEst(){var e=estCount(),line=document.getElementById('estLine');document.getElementById('bsWarn').style.display=e.n>500?'':'none';document.getElementById('bsWarn').style.color=e.n>5000?'var(--red)':'var(--amber)';line.innerHTML='预计生成 <b>'+e.total+'</b> 张 = 1 Prompt × '+e.n+' batch';line.className='est-line'+(e.total>=5000?' red':(e.total>=500?' yellow':''));document.getElementById('warn500').classList.toggle('show',e.total>=500&&e.total<5000);document.getElementById('warn5000').classList.toggle('show',e.total>=5000);syncChips();}
['batchSize','seedvr2Toggle','esesToggle','width','height','steps','cfg'].forEach(function(id){var el=document.getElementById(id);el.addEventListener('input',updateEst);el.addEventListener('change',updateEst);});
document.getElementById('engineSelect').addEventListener('change',function(){syncEngMenu();if(_CFG&&_CFG.models&&_CFG.models.engines){var ec=_CFG.models.engines[this.value];if(ec){var w=document.getElementById('width'),h=document.getElementById('height');if(!w.dataset.touched)w.value=ec.default_width||w.value;if(!h.dataset.touched)h.value=ec.default_height||h.value;}}syncChips();updateEst();});
updateEst();
/* ---------- 生成模拟 ---------- */
var genBtn=document.getElementById('genBtn');
var progFill=document.getElementById('progFill'),phaseText=document.getElementById('phaseText'),genProgress=document.getElementById('genProgress');
var outGrid=document.getElementById('outGrid');
var qpDot=document.getElementById('qpDot'),qpText=document.getElementById('qpText'),qpPct=document.getElementById('qpPct'),qpop=document.getElementById('queuePop');
var timer=null,progress=0;
/* 生成流程由下方 F1 真实层接管（startGenReal / cancelGenReal / renderOutReal） */
document.getElementById('queuePill').addEventListener('click',function(){qpop.classList.toggle('show');if(qpop.classList.contains('show'))renderQueue();});
document.getElementById('qpClose').addEventListener('click',function(e){e.stopPropagation();qpop.classList.remove('show');});
/* (队列取消已由 F1 真实层接管) */
/* ---------- 图片展示（抽屉内 + 悬浮查看器） ---------- */
/* 图库数据由 F7 从 /api/outputs 真实加载，不再使用原型示例 */
var gMasonry=document.getElementById('gMasonry');
function renderGallery(filter){filter=filter||'全部';gMasonry.innerHTML='<p style="padding:20px;text-align:center;color:var(--ink-faint)">加载中…</p>';}
document.querySelectorAll('#galleryDrawer .f-chip').forEach(function(b){b.addEventListener('click',function(){document.querySelectorAll('#galleryDrawer .f-chip').forEach(function(x){x.classList.remove('on');});b.classList.add('on');renderGallery(b.dataset.f);});});
var viewer=document.getElementById('viewer'),vImg=document.getElementById('vImg'),vTitle=document.getElementById('vTitle'),vSeed=document.getElementById('vSeed'),vMeta=document.getElementById('vMeta'),vZoomVal=document.getElementById('vZoomVal');
var zoom=100,compare=false,cur=0,_curViewer=null,_navList=null,_navIdx=-1;
function openViewer(i){/* 由 F7 openViewerReal 接管 */}
function renderImg(){/* 由 F7 覆盖为真实图片渲染 */}
document.getElementById('vCompare').addEventListener('click',function(){compare=!compare;renderImg();});
document.getElementById('vZoomIn').addEventListener('click',function(){zoom=Math.min(200,zoom+25);renderImg();});
document.getElementById('vZoomOut').addEventListener('click',function(){zoom=Math.max(50,zoom-25);renderImg();});
document.getElementById('vZoomReset').addEventListener('click',function(){zoom=100;renderImg();});
document.getElementById('vFav').addEventListener('click',function(){this.classList.toggle('on');this.textContent=this.classList.contains('on')?'★':'☆';});
document.getElementById('vClose').addEventListener('click',function(){viewer.classList.remove('show');});
document.getElementById('vDownload').addEventListener('click',function(){if(_curViewer)window.open('/api/outputs/'+_curViewer.path,'_blank');});
document.getElementById('vRedraw').addEventListener('click',function(){if(_curViewer&&_curViewer.task_id){var tid=_curViewer.task_id;viewer.classList.remove('show');redrawTask(tid);}});
document.getElementById('vPrev').addEventListener('click',function(){navViewer(-1);});
document.getElementById('vNext').addEventListener('click',function(){navViewer(1);});
document.getElementById('vFull').addEventListener('click',function(){if(document.fullscreenElement){document.exitFullscreen().catch(function(){});}else if(viewer.requestFullscreen){viewer.requestFullscreen().catch(function(){});}});
document.getElementById('vPromptToggle').addEventListener('click',function(){var info=document.getElementById('vInfo');var expanded=info.classList.toggle('expanded');this.textContent=expanded?'收起':'展开';});
/* 查看器打开时 ←/→ 切换上一张/下一张 */
document.addEventListener('keydown',function(e){
  if(!viewer.classList.contains('show'))return;
  if(e.key==='ArrowLeft')navViewer(-1);
  else if(e.key==='ArrowRight')navViewer(1);
});
/* ---------- 历史（抽屉内） ---------- */
var histList=document.getElementById('histList'),histDetail=document.getElementById('histDetail');
function showHistList(){histList.classList.remove('hide');histDetail.classList.remove('show');}
function showHistDetail(){histList.classList.add('hide');histDetail.classList.add('show');}
document.getElementById('histBack').addEventListener('click',showHistList);
/* ---------- 预设（抽屉内） ---------- */
var pList=document.getElementById('pList'),pEdit=document.getElementById('pEdit');
function showPList(){pList.style.display='';pEdit.classList.remove('show');}
function showPEdit(){pList.style.display='none';pEdit.classList.add('show');}
document.getElementById('pBack').addEventListener('click',showPList);
document.getElementById('pCancel').addEventListener('click',showPList);
document.getElementById('pNew').addEventListener('click',function(){_editPresetId=null;document.getElementById('pName').value='';document.getElementById('pDesc').value='';showPEdit();});
document.querySelectorAll('#pList .fav').forEach(function(b){b.addEventListener('click',function(){this.classList.toggle('on');this.textContent=this.classList.contains('on')?'★':'☆';});});
/* pSave 真实逻辑由 F5 节接管 */
/* ---------- 批量（底抽屉内） ---------- */
/* ---------- 批量底抽屉：真实文件上传 + 动态估算 ---------- */
var B_FILES=[];
function fmtSize(b){return b<1024?b+' B':(b/1024).toFixed(1)+' KB';}
function readBatchFiles(fileList){
  var files=Array.prototype.slice.call(fileList||[]);
  if(!files.length)return;
  var pending=files.length;
  files.forEach(function(file){
    var reader=new FileReader();
    reader.onload=function(){
      var text=String(reader.result||'');
      var raw=text.split(/\r?\n/).map(function(s){return s.trim();}).filter(Boolean);
      if(raw.length)B_FILES.push({name:file.name,size:file.size,lines:raw});
      pending--;
      if(pending===0){renderBFileList();calcBEst();}
    };
    reader.readAsText(file,'utf-8');
  });
}
function renderBFileList(){
  var box=document.getElementById('bFileList');
  if(!box)return;
  if(!B_FILES.length){box.innerHTML='<p style="text-align:center;color:var(--ink-faint);font-size:10px;padding:8px 0">未添加文件</p>';return;}
  box.innerHTML='';
  B_FILES.forEach(function(f,idx){
    var d=document.createElement('div');d.className='f-row';
    d.innerHTML='<span class="nm">'+escHtml(f.name)+'</span><span class="sz">'+fmtSize(f.size)+' · '+f.lines.length+' 行</span><span class="st ok">已解析</span><button class="btn btn-sm" type="button" style="height:22px;padding:2px 8px;font-size:10px">移除</button>';
    d.querySelector('button').addEventListener('click',function(){B_FILES.splice(idx,1);renderBFileList();calcBEst();});
    box.appendChild(d);
  });
}
function bPrompts(){
  var seen={},out=[];
  B_FILES.forEach(function(f){f.lines.forEach(function(l){if(!seen[l]){seen[l]=1;out.push(l);}});});
  return out;
}
function bGridCombos(){
  var n=1;
  document.querySelectorAll('#bpane-grid .dim>input[type=checkbox]:checked').forEach(function(c){
    var vals=c.parentElement.querySelectorAll('.vals label.checked');
    n*=Math.max(1,vals.length);
  });
  return n;
}
function bGridDims(){
  var grid={};
  document.querySelectorAll('#bpane-grid .dim').forEach(function(dim){
    var key=dim.querySelector('.dim-name').textContent.trim().split(/\s+/)[0];
    var checked=dim.querySelector('input[type=checkbox]').checked;
    if(checked){
      var vals=[];
      dim.querySelectorAll('.vals label.checked').forEach(function(l){
        var v=l.textContent.trim();
        if(key==='steps'||key==='width'||key==='height')vals.push(parseInt(v,10));
        else if(key==='cfg')vals.push(parseFloat(v));
        else vals.push(v);
      });
      if(vals.length)grid[key]=vals;
    }
  });
  return grid;
}
function calcBEst(){
  var lines=bPrompts().length;
  var groups=bGridCombos();
  var batch=+(document.getElementById('bBatchSize')||{value:1}).value||1;
  var total=lines*groups*batch;
  document.getElementById('bFileStat').textContent=B_FILES.length+' 个 · '+lines+' 行';
  document.getElementById('gridCombo').textContent=groups+' 组';
  document.getElementById('bBatchStat').textContent=batch;
  var e=document.getElementById('bEst');
  e.innerHTML='预计生成 <b>'+total+'</b> 张 = '+lines+' 行 × '+groups+' 组 × batch '+batch;
  e.className='big-est'+(total>=5000?' red':(total>=500?' yellow':''));
  document.getElementById('bWarn500').classList.toggle('show',total>=500&&total<5000);
  document.getElementById('bWarn5000').classList.toggle('show',total>=5000);
}
var bDrop=document.getElementById('bDropzone'),bInput=document.getElementById('bFileInput');
if(bDrop&&bInput){
  bDrop.addEventListener('click',function(){bInput.click();});
  bInput.addEventListener('change',function(){readBatchFiles(bInput.files);bInput.value='';});
  ['dragover','dragenter'].forEach(function(ev){bDrop.addEventListener(ev,function(e){e.preventDefault();e.stopPropagation();bDrop.style.borderColor='var(--accent)';});});
  ['dragleave','drop'].forEach(function(ev){bDrop.addEventListener(ev,function(e){e.preventDefault();e.stopPropagation();bDrop.style.borderColor='';});});
  bDrop.addEventListener('drop',function(e){readBatchFiles(e.dataTransfer.files);});
}
document.querySelectorAll('#bpane-grid .vals label').forEach(function(l){l.addEventListener('click',function(){l.classList.toggle('checked');calcBEst();});});
document.querySelectorAll('#bpane-grid .dim>input[type=checkbox]').forEach(function(c){c.addEventListener('change',function(){var vals=c.parentElement.querySelectorAll('.vals label');vals.forEach(function(l){l.classList.toggle('checked',c.checked);});calcBEst();});});
var bBatchSel=document.getElementById('bBatchSize');
if(bBatchSel)bBatchSel.addEventListener('change',calcBEst);
calcBEst();
document.querySelectorAll('.tabs .tab').forEach(function(t){t.addEventListener('click',function(){document.querySelectorAll('.tabs .tab').forEach(function(x){x.classList.remove('active');});document.querySelectorAll('.tabpane').forEach(function(x){x.classList.remove('active');});t.classList.add('active');document.getElementById(t.dataset.t).classList.add('active');});});

calcBEst();
/* ---------- 缩放控件 ---------- */
var zooms=[50,75,100,125,150,200],zi=2;var zVal=document.getElementById('zVal');
document.getElementById('zOut').addEventListener('click',function(){zi=Math.max(0,zi-1);zVal.textContent=zooms[zi]+'%';});
document.getElementById('zIn').addEventListener('click',function(){zi=Math.min(zooms.length-1,zi+1);zVal.textContent=zooms[zi]+'%';});

/* ================================================================
   F1-F10: 真实 API 接线（AUDIT_REPORT_2.0 R2 修复）
   原则：UI 结构不动，把模拟数据/模拟执行替换为真实 fetch / SSE
   ================================================================ */

/* ---------- F10: i18n/主题 localStorage 持久化 + 防闪烁 ---------- */
// 防闪烁：在 DOMContentLoaded 前恢复主题
(function(){
  var savedTheme=localStorage.getItem('imm_theme')||'light';
  var savedLang=localStorage.getItem('imm_lang')||'zh-CN';
  document.documentElement.setAttribute('data-theme',savedTheme);
  document.documentElement.setAttribute('data-lang',savedLang);
  if(themeBtn){var ic=themeBtn.querySelector('.ic');if(ic)ic.textContent=savedTheme==='dark'?'◑':'◐';}
  if(langSel){langSel.value=savedLang;}
  applyLang(savedLang);
})();
// 主题切换 → 持久化
themeBtn.onclick=function(){
  var dark=document.documentElement.getAttribute('data-theme')==='dark';
  var newTheme=dark?'light':'dark';
  document.documentElement.setAttribute('data-theme',newTheme);
  var ic=themeBtn.querySelector('.ic');if(ic)ic.textContent=dark?'◐':'◑';
  localStorage.setItem('imm_theme',newTheme);
};
// 语言切换 → 持久化
langSel.addEventListener('change',function(e){
  localStorage.setItem('imm_lang',e.target.value);
  applyLang(e.target.value);
});
// 从 localStorage 恢复语言菜单选中状态
document.querySelectorAll('#langMenu .ip-item').forEach(function(b){
  if(b.dataset.l===localStorage.getItem('imm_lang')){
    document.querySelectorAll('#langMenu .ip-item').forEach(function(x){x.classList.remove('on');});
    b.classList.add('on');
  }
});

/* ---------- API 辅助对象 + 全局 SSE ---------- */
/* CSRF (Double-Submit Cookie)：GET 响应头 X-CSRF-Token 与 httponly csrf_token cookie 同值；
   POST/PUT/DELETE 需带 X-CSRF-Token 头（后端校验 头==cookie，否则 403） */
var _csrfToken=null;
async function _ensureCsrf(){
  if(_csrfToken)return _csrfToken;
  var r=await fetch('/api/health');  // 任意 GET 领取 token
  var t=r.headers.get('X-CSRF-Token');if(t)_csrfToken=t;
  return _csrfToken;
}
var API={
  get:async function(p){
    var r=await fetch('/api'+p);
    var t=r.headers.get('X-CSRF-Token');if(t)_csrfToken=t;  // 每次 GET 刷新本地 token
    return r.json();
  },
  send:async function(p,body,method){
    method=method||'POST';
    var h={'Content-Type':'application/json'};
    var t=await _ensureCsrf();if(t)h['X-CSRF-Token']=t;
    var opts={method:method,headers:h};
    if(body)opts.body=JSON.stringify(body);
    var r=await fetch('/api'+p,opts);
    return r.json();
  },
  put:async function(p,body){return API.send(p,body,'PUT');},
  del:async function(p){return API.send(p,null,'DELETE');},
  post:async function(p,body){return API.send(p,body,'POST');}
};
var evt=new EventSource('/api/events'); // 全局唯一 SSE 连接
var currentTaskId=null;

// SSE 事件处理
evt.addEventListener('connected',function(e){
  console.log('[SSE] Connected');
});
evt.addEventListener('task_status',function(e){
  try{
    var d=JSON.parse(e.data);
    if(d.task_id===currentTaskId||!currentTaskId){
      if(d.progress!==undefined){progFill.style.width=d.progress+'%';phaseText.textContent=trPhase(d.phase||'')+' · '+d.progress+'%';qpPct.textContent=d.progress+'%';}
      if(d.status){
        if(d.status==='completed'){genBtn.disabled=false;timer=null;phaseText.textContent='完成 · '+(d.result?d.result.length:0)+' 张输出';progFill.style.width='100%';qpDot.className='qd';qpPct.style.display='none';qpText.textContent='队列 0·0 · 完成';if(d.result&&d.result.length)renderOutReal(d.result);loadRecent();}
        else if(d.status==='failed'){genBtn.disabled=false;timer=null;phaseText.textContent='失败: '+(d.error||'');progFill.style.width='0%';qpDot.className='qd';qpPct.style.display='none';qpText.textContent='失败';}
        else if(d.status==='cancelled'){genBtn.disabled=false;timer=null;phaseText.textContent='已取消';progFill.style.width='0%';qpDot.className='qd';qpPct.style.display='none';qpText.textContent='已取消';}
        else if(d.status==='processing'){qpDot.className='qd run';qpPct.style.display='';qpText.textContent='生成中';}
      }
    }
  }catch(err){console.warn('[SSE] parse error',err);}
});
evt.addEventListener('heartbeat',function(e){console.log('[SSE] heartbeat');});
evt.addEventListener('preview',function(e){
  try{
    var d=JSON.parse(e.data);
    if(d.b64){
      var img=document.createElement('img');
      img.src='data:image/'+(d.format||'jpg')+';base64,'+d.b64;
      img.style.cssText='max-width:100%;border-radius:6px;margin-top:6px';
      var prog=document.getElementById('genProgress');
      if(prog){var old=prog.querySelector('.preview-img');if(old)old.remove();img.className='preview-img';prog.appendChild(img);}
    }
  }catch(err){console.warn('[SSE] preview parse error',err);}
});
evt.addEventListener('gpu_status',function(e){
  try{
    var d=JSON.parse(e.data);
    var sb=document.querySelector('.sb-gpu');
    if(sb&&d.free_vram_gb!==undefined){sb.textContent='VRAM: '+d.free_vram_gb.toFixed(1)+'GB free';}if(d.total_vram_gb){setBar('statGpu',(d.used_vram_gb||0).toFixed(1)+' / '+d.total_vram_gb+' GB',d.total_vram_gb?Math.round((d.used_vram_gb||0)/d.total_vram_gb*100):0);}
  }catch(err){}
});

/* ---------- 系统状态：真实 health / GPU / 资源 ---------- */
function loadHealth(){
  fetch('/api/health').then(function(r){return r.json();}).then(function(h){
    if(!h||h.status!=='ok'){setConn(false);return;}
    setConn(true);
    var av=document.getElementById('aboutVersion');if(av)av.textContent=h.version||'—';
    // 状态栏：队列 + 引擎
    var q=h.queue||{};
    var sbq=document.getElementById('sbQueue');
    if(sbq)sbq.textContent='QUEUE '+(q.processing||0)+'·'+(q.pending||0);
    // 状态栏：GPU（SSE 也会更新）
    var g=h.gpu||{};
    var sbg=document.querySelector('.sb-gpu');
    if(sbg&&g.total_vram_gb)sbg.textContent='GPU '+(g.free_vram_gb!=null?(g.free_vram_gb.toFixed(1)+'/'+g.total_vram_gb+'GB free'):(g.total_vram_gb+'GB'));
    renderStatusBars(h);
    renderStatEngines(h.engines||[]);
    renderStatLoras();
  }).catch(function(){setConn(false);});
}
function setConn(ok){
  var dot=document.getElementById('sbConnDot'),txt=document.getElementById('sbConnText');
  if(!dot||!txt)return;
  dot.className='dot '+(ok?'green':'red');
  txt.textContent=ok?'CONN: OK':'CONN: 离线';
}
function renderStatusBars(h){
  // GPU
  var g=h.gpu||{};
  if(g.total_vram_gb){
    var used=((g.used_vram_gb!=null?g.used_vram_gb:(g.total_vram_gb-(g.free_vram_gb||0)))||0);
    var pct=g.total_vram_gb?Math.round(used/g.total_vram_gb*100):0;
    setBar('statGpu',used.toFixed(1)+' / '+g.total_vram_gb+' GB',pct);
  }else{setBar('statGpu','无 GPU 信息',0);}
  // 内存
  var m=h.memory||{};
  if(m.total_gb){setBar('statMem',m.used_gb+' / '+m.total_gb+' GB',Math.round(m.percent||0));}
  else{setBar('statMem','—',0);}
  // 磁盘
  var d=h.disk||{};
  if(d.total_gb){setBar('statDisk',d.used_gb+' / '+d.total_gb+' GB',d.total_gb?Math.round(d.used_gb/d.total_gb*100):0);}
  else{setBar('statDisk','—',0);}
}
function setBar(id,text,pct){
  var v=document.getElementById(id),b=document.getElementById(id+'Bar'),p=document.getElementById(id+'Pct');
  if(v)v.textContent=text;
  if(b)b.style.width=Math.max(0,Math.min(100,pct||0))+'%';
  if(p)p.textContent=(pct||0)+'%';
}
function renderStatEngines(engines){
  var box=document.getElementById('statEngines');
  if(!box)return;
  if(!engines||!engines.length){box.innerHTML='<div class="back-row"><b>无引擎配置</b></div>';return;}
  box.innerHTML='';
  engines.forEach(function(e){
    var d=document.createElement('div');d.className='back-row';
    var st=e.state||(e.ready?'loaded':'unknown');
    var chipTxt=st==='loaded'?'就绪':(st==='loading'?'加载中':(st==='error'?'错误':'未加载'));
    var chipCls=st==='loaded'?'chip ok':(st==='loading'?'chip':'chip red');
    d.innerHTML='<b>'+escHtml(e.display_name)+'</b><span style="color:var(--ink-faint)">'+escHtml(st)+'</span><span class="'+chipCls+'">'+chipTxt+'</span>';
    box.appendChild(d);
  });
}
function renderStatLoras(){
  var el=document.getElementById('statLoras'),chip=document.getElementById('statLorasChip');
  if(!el)return;
  fetch('/api/config/loras').then(function(r){return r.json();}).then(function(d){
    var n=(d.loras||[]).length;
    el.textContent='loras/ · '+n+' 个文件';
    if(chip){chip.textContent=n>0?'就绪':'空';chip.className='chip '+(n>0?'ok':'red');}
  }).catch(function(){el.textContent='加载失败';if(chip){chip.textContent='—';}});
}
var statRefreshBtn=document.getElementById('statRefresh');
if(statRefreshBtn)statRefreshBtn.addEventListener('click',function(){loadHealth();});

/* ---------- F1: 生成 + 进度 + 队列球 ---------- */
// 覆盖 startGen → POST /api/generate
function startGenReal(){
  if(timer)return;
  var loraSels=document.querySelectorAll('#loraStack .lora-name');
  var loraSliders=document.querySelectorAll('#loraStack .r2 input[type=range]');
  function loraName(i){var s=loraSels[i];if(!s)return '';var v=s.value;return(v==='— 禁用 —')?'':v;}
  function loraStrength(i){var s=loraSliders[i];return s?(+s.value||0):0;}
  var axisEl=document.querySelector('input[name="axis"]:checked');
  var outPrefix=document.getElementById('outputPrefix');
  var cfg={
    positive_prompt:posPrompt.value||'',
    negative_prompt:negPrompt.value||'',
    cfg:+document.getElementById('cfg').value||1.0,
    steps:+document.getElementById('steps').value||8,
    width:+document.getElementById('width').value||1024,
    height:+document.getElementById('height').value||1024,
    seed:+document.getElementById('seed').value||-1,
    batch_size:+document.getElementById('batchSize').value||1,
    lora_1_name:loraName(0),lora_1_strength:loraStrength(0),
    lora_2_name:loraName(1),lora_2_strength:loraStrength(1),
    lora_3_name:loraName(2),lora_3_strength:loraStrength(2),
    lora_4_name:loraName(3),lora_4_strength:loraStrength(3),
    lora_5_name:loraName(4),lora_5_strength:loraStrength(4),
    lora_6_name:loraName(5),lora_6_strength:loraStrength(5),
    seedvr2_enable:document.getElementById('seedvr2Toggle').checked,
    seedvr2_resolution:+document.getElementById('upscaleRes').value||2048,
    seedvr2_seed:+document.getElementById('upscaleSeed').value||-1,
    seedvr2_color_correction:document.getElementById('colorCorr').value||'lab',
    eses_enable:document.getElementById('esesToggle').checked,
    eses_compare_axis:axisEl?axisEl.value:'horizontal',
    vram_enable:document.getElementById('vramToggle').checked,
    vram_reserved_gb:+document.getElementById('vramGb').value||0.6,
    vram_mode:document.getElementById('vramMode').value||'auto',
    vram_seed:+document.getElementById('vramSeed').value||-1,
    output_format:'png',
    output_prefix:outPrefix?outPrefix.value:'{engine}',
    engine_name:document.getElementById('engineSelect').value
  };
  genBtn.disabled=true;
  genProgress.classList.add('show');
  progFill.style.width='0%';
  phaseText.textContent='提交中…';
  qpDot.className='qd run';qpPct.style.display='';qpText.textContent='提交中';
  API.post('/generate',cfg).then(function(r){
    if(r.task_id){
      currentTaskId=r.task_id;
      phaseText.textContent=r.estimated_time_s?('排队中…（预计 '+(r.estimated_time_s>=60?Math.ceil(r.estimated_time_s/60)+' 分钟':Math.ceil(r.estimated_time_s)+'s')+'）'):'排队中…';
      if(r.warning)console.warn('[Gen] Warning:',r.warning);
    }else{
      genBtn.disabled=false;
      genProgress.classList.remove('show');
      qpDot.className='qd';qpPct.style.display='none';qpText.textContent='错误';
      window.alert('生成失败: '+(r.detail||JSON.stringify(r)));
    }
  }).catch(function(e){
    genBtn.disabled=false;genProgress.classList.remove('show');
    qpDot.className='qd';qpPct.style.display='none';qpText.textContent='错误';
    window.alert('请求失败: '+e);
  });
}
// 覆盖 cancelGen → POST /api/tasks/{id}/cancel
function cancelGenReal(){
  if(!currentTaskId){if(timer){clearInterval(timer);timer=null;}genBtn.disabled=false;phaseText.textContent='已取消';return;}
  API.post('/tasks/'+currentTaskId+'/cancel').then(function(r){
    genBtn.disabled=false;timer=null;
    phaseText.textContent='已取消 (status=cancelled)';
    progFill.style.width='0%';genProgress.classList.remove('show');
    qpDot.className='qd';qpPct.style.display='none';qpText.textContent='已取消';
    currentTaskId=null;
  }).catch(function(e){console.error('[Cancel] error:',e);});
}
// 覆盖 renderOut → 真实输出
function renderOutReal(imgPaths){
  outGrid.innerHTML='';
  if(!imgPaths||!imgPaths.length){outGrid.innerHTML='<p style="padding:20px;text-align:center;color:var(--ink-faint)">无输出</p>';return;}
  imgPaths.forEach(function(path,i){
    var types=['原图'];
    var c=document.createElement('div');c.className='r-card';c.style.setProperty('--ar','1/1');
    c.innerHTML='<div class="ph-img"><img src="/api/outputs/'+path+'" style="max-width:100%;max-height:300px;object-fit:contain"><div class="r-actions"><button class="btn btn-sm" type="button" onclick="window.open(\'/api/outputs/'+path+'\',\'_blank\')">下载</button><button class="btn btn-sm" type="button">收藏</button><button class="btn btn-sm" type="button" onclick="redrawTask(\''+currentTaskId+'\')">重绘</button></div></div><div class="r-meta"><b>'+(types[i]||'输出 '+(i+1))+'</b><span>'+path.split('/').pop()+'</span></div>';
    outGrid.appendChild(c);
  });
}
// 重绘函数
function redrawTask(taskId){if(!taskId)return;API.post('/tasks/'+taskId+'/redraw').then(function(r){if(r.task_id){currentTaskId=r.task_id;genBtn.disabled=true;genProgress.classList.add('show');progFill.style.width='0%';phaseText.textContent='重绘中…';qpDot.className='qd run';qpPct.style.display='';qpText.textContent='重绘中';}}).catch(function(e){window.alert('重绘失败: '+e);});}
// 覆盖生成按钮事件
genBtn.removeEventListener('click',function(){}); // 移除旧监听
genBtn.onclick=function(){
  var e=estCount();
  if(e.total>=5000){if(!window.confirm('⚠ 将生成 '+e.total+' 张（batch='+e.n+'）。预计 '+Math.ceil(e.total/3000)+' 小时，确认？'))return;}
  else if(e.total>=500){if(!window.confirm('⚠ 将生成 '+e.total+' 张，预计 '+(e.total*1.5/60).toFixed(0)+' 分钟，确认？'))return;}
  startGenReal();
};
// 覆盖取消按钮
var qCancelBtn=document.getElementById('qCancelBtn');
if(qCancelBtn)qCancelBtn.onclick=function(){cancelGenReal();qpop.classList.remove('show');};

/* ---------- F3: LoRA 下拉 ← 后端资源扫描 ---------- */
var _lorasLoaded=false;
function loadLoras(){
  if(_lorasLoaded)return;
  fetch('/api/config/loras').then(function(r){return r.json();}).then(function(d){
    var sels=document.querySelectorAll('#loraStack .lora-name');
    if(!sels.length)return;
    var items=d.loras||[];
    sels.forEach(function(sel){
      var cur=sel.value;
      sel.innerHTML='<option>— 禁用 —</option>';
      var match=null;
      items.forEach(function(p){var o=document.createElement('option');o.value=p;o.textContent=p.split('/').pop();sel.appendChild(o);if(p.split('/').pop()===cur)match=p;});
      sel.value=match||'— 禁用 —';
    });
    _lorasLoaded=true;
    var h=document.getElementById('scanHint');if(h)h.textContent='loras/ '+d.count+' 个 · 模式 '+(d.mode==='portable'?'portable':'shared');
  }).catch(function(e){console.warn('[LoRA] load failed:',e);});
}
var scanBtn=document.getElementById('scanBtn');
if(scanBtn)scanBtn.addEventListener('click',function(){_lorasLoaded=false;loadLoras();});
/* ---------- F2: 设置顶抽屉（真实配置） ---------- */
function fillSettings(cfg){
  if(!cfg)return;
  var se=document.getElementById('setEngine');
  if(se){
    se.innerHTML='<option value="">—</option>';
    var engs=cfg.models&&cfg.models.engines||{};
    Object.keys(engs).forEach(function(k){var o=document.createElement('option');o.value=k;o.textContent=engs[k].display_name||k;se.appendChild(o);});
    se.value=(cfg.models&&cfg.models.default_engine)||'';
  }
  var ec=(cfg.models&&cfg.models.engines&&cfg.models.engines[cfg.models.default_engine])||{};
  var wd=document.getElementById('setWorkflowDir');if(wd)wd.value=ec.workflow_file||'';
  var mm=document.getElementById('setModelMode');if(mm){var ms=cfg.models||{};mm.value=(ms.model_source_mode||'')+' · '+((ms.model_source_mode==='portable'?(ms.portable&&ms.portable.internal_models_dir):(ms.shared&&ms.shared.comfy_models_dir))||'');}
  var sd=document.getElementById('setSeedvr2Dir');if(sd){var ms2=cfg.models||{};sd.value=(ms2.model_source_mode==='portable'?(ms2.portable&&ms2.portable.internal_models_dir):(ms2.shared&&ms2.shared.comfy_models_dir))||'';}
  var hb=document.getElementById('setHeartbeat');if(hb&&cfg.comfy&&cfg.comfy.backends&&cfg.comfy.backends.local)hb.value=String(cfg.comfy.backends.local.health_check_interval_s||30);
  var sp=document.getElementById('setSpawn');if(sp&&cfg.comfy&&cfg.comfy.backends&&cfg.comfy.backends.local)sp.value=String(cfg.comfy.backends.local.auto_spawn_if_dead===true?'true':'false');
  var lb=document.getElementById('setLb');if(lb&&cfg.comfy)lb.value=cfg.comfy.load_balance||'prefer_local';
  var rh=document.getElementById('retentionHint');if(rh&&cfg.history)rh.textContent='db: '+((cfg.history.db_path)||'');
}
var _origOpenSet=openSet;
openSet=function(){
  _origOpenSet();
  fetch('/api/config').then(function(r){return r.json();}).then(function(cfg){
    fillSettings(cfg);
  }).catch(function(e){console.warn('[Config] load failed:',e);});
};
// 设置抽屉：切换默认引擎 → 同步主界面
var setEngineEl=document.getElementById('setEngine');
if(setEngineEl)setEngineEl.addEventListener('change',function(){
  if(!this.value)return;
  var es=document.getElementById('engineSelect');
  if(es&&ENGINES[this.value]){es.value=this.value;es.dispatchEvent(new Event('change'));syncEngMenu();}
});
// 关闭设置抽屉时保存推理默认值 → PUT /api/config
document.getElementById('setClose').addEventListener('click',function(){
  var update={inference:{default_steps:+document.getElementById('steps').value||10,default_cfg:+document.getElementById('cfg').value||1.0}};
  API.put('/config',update).then(function(r){console.log('[Config] saved:',r);}).catch(function(e){console.warn('[Config] save failed:',e);});
  setD.classList.remove('open');setSc.classList.remove('show');
});

/* ---------- F6: 历史左抽屉（真实渲染 + 筛选/分页/详情） ---------- */
var _histPage=1,_histQ='',_histStatus='',_histEngine='',_curDetailTask=null;
function renderHist(){
  var tbody=document.getElementById('histRows');if(!tbody)return;
  var qs='/api/tasks?page='+_histPage+'&page_size=20';
  if(_histStatus)qs+='&status='+encodeURIComponent(_histStatus);
  if(_histEngine)qs+='&engine='+encodeURIComponent(_histEngine);
  if(_histQ)qs+='&q='+encodeURIComponent(_histQ);
  fetch(qs).then(function(r){return r.json();}).then(function(r){
    tbody.innerHTML='';
    var list=r.tasks||[];
    if(!list.length){tbody.innerHTML='<tr><td colspan="4" style="text-align:center;padding:20px;color:var(--ink-faint)">暂无历史记录</td></tr>';}
    var stTxt={completed:'完成',failed:'失败',cancelled:'已取消',processing:'进行中',pending:'排队中'};
    list.forEach(function(t){
      var tr=document.createElement('tr');
      var st=t.status||'';
      var chip=st==='completed'?'ok':(st==='failed'?'red':'warn');
      tr.innerHTML='<td><div class="th">'+(t.output_count>0?t.output_count+' 张':'—')+'</div></td>'+
        '<td class="pro">'+escHtml(t.prompt||'(无提示词)')+'<br><span style="font-size:9px;color:var(--ink-faint)">'+escHtml(engLabel(t.engine))+'</span></td>'+
        '<td><span class="chip '+chip+'">'+(stTxt[st]||st)+'</span></td>'+
        '<td><button class="btn btn-sm" type="button">详情</button></td>';
      tr.addEventListener('click',function(){showHistDetail(t);});
      tr.querySelector('button').addEventListener('click',function(e){e.stopPropagation();showHistDetail(t);});
      tbody.appendChild(tr);
    });
    var total=r.total||0,tp=r.total_pages||1;
    document.getElementById('histTotal').textContent='共 '+total+' 条';
    document.getElementById('histCount').textContent='第 '+_histPage+'/'+tp+' 页';
    var prev=document.getElementById('histPrev'),next=document.getElementById('histNext');
    if(prev)prev.disabled=_histPage<=1;
    if(next)next.disabled=_histPage>=tp;
  }).catch(function(e){console.warn('[History] load failed:',e);tbody.innerHTML='<tr><td colspan="4" style="text-align:center;padding:20px;color:var(--ink-faint)">加载失败</td></tr>';});
}
function showHistDetail(t){
  document.getElementById('histList').classList.add('hide');
  document.getElementById('histDetail').classList.add('show');
  var gc=t.generation_config||{};
  var st=t.status||'';
  var stTxt={completed:'完成',failed:'失败',cancelled:'已取消',processing:'进行中',pending:'排队中'};
  document.getElementById('ddEngine').textContent=engLabel(t.engine);
  document.getElementById('ddStatus').textContent=stTxt[st]||st;
  document.getElementById('ddMode').textContent=t.mode||'txt2img';
  document.getElementById('ddPrompt').textContent=t.prompt||'(无提示词)';
  document.getElementById('ddDim').textContent=(gc.width||'?')+'×'+(gc.height||'?')+' · seed '+(gc.seed===undefined||gc.seed===null?'—':gc.seed);
  document.getElementById('ddTime').textContent=(t.processing_time_s?t.processing_time_s+'s · ':'')+(t.created_at||'');
  document.getElementById('ddCfgSteps').textContent=(gc.cfg===undefined||gc.cfg===null?'?':gc.cfg)+' · '+(gc.steps===undefined||gc.steps===null?'?':gc.steps);
  var nLora=0;['lora_1_name','lora_2_name','lora_3_name','lora_4_name','lora_5_name','lora_6_name'].forEach(function(k){if(gc[k])nLora++;});
  document.getElementById('ddLora').textContent=(nLora?nLora+' 层':'—')+' · '+(gc.seedvr2_enable?('SeedVR2 '+(gc.seedvr2_resolution||'?')):'SeedVR2 off')+' · '+(gc.eses_enable?('Eses '+(gc.eses_compare_axis||'h')):'Eses off');
  var thumbs=document.getElementById('ddThumbs');
  thumbs.innerHTML=t.output_count>0
    ?'<div class="th" style="width:100%;height:56px">'+t.output_count+' 张输出</div>'
    :'<div class="th" style="width:100%;height:56px">无预览</div>';
  _curDetailTask=t;
}
document.getElementById('ddRedraw').addEventListener('click',function(){if(_curDetailTask)redrawTask(_curDetailTask.task_id);showHistList();});
document.getElementById('ddSavePreset').addEventListener('click',function(){
  if(!_curDetailTask)return;
  var gc=_curDetailTask.generation_config||{};
  var cfg={positive_prompt:_curDetailTask.prompt||'',cfg:gc.cfg,steps:gc.steps,width:gc.width,height:gc.height,seed:gc.seed===undefined?-1:gc.seed};
  API.post('/presets',{engine_name:_curDetailTask.engine||'z_image_turbo_native',name:'任务 '+String(_curDetailTask.task_id).substring(0,8),config:cfg}).then(function(){window.alert('已保存为预设');}).catch(function(e){window.alert('保存失败: '+e);});
});
document.getElementById('ddZip').addEventListener('click',function(){if(_curDetailTask)window.open('/api/tasks/export?ids='+_curDetailTask.task_id,'_blank');});
var _origShowHistList=showHistList;
showHistList=function(){_origShowHistList();renderHist();};
document.getElementById('histSearch').addEventListener('input',function(){
  var me=this;clearTimeout(window._histTimer);
  window._histTimer=setTimeout(function(){_histQ=me.value.trim();_histPage=1;renderHist();},300);
});
document.getElementById('histStatus').addEventListener('change',function(){_histStatus=this.value;_histPage=1;renderHist();});
document.getElementById('histEngine').addEventListener('change',function(){_histEngine=this.value;_histPage=1;renderHist();});
document.getElementById('histPrev').addEventListener('click',function(){if(_histPage>1){_histPage--;renderHist();}});
document.getElementById('histNext').addEventListener('click',function(){_histPage++;renderHist();});
// 批量删除：失败 / 排队中 / 进行中 / 已取消
function fetchAllTaskIds(status){
  var all=[],page=1;
  function one(){
    var q='/api/tasks?page='+page+'&page_size=200'+(status?'&status='+encodeURIComponent(status):'');
    return fetch(q).then(function(r){return r.json();}).then(function(d){
      (d.tasks||[]).forEach(function(t){if(t.task_id)all.push(t.task_id);});
      if(page*200<(d.total||0)){page++;return one();}
      return all;
    });
  }
  return one();
}
function deleteTaskIds(ids){
  if(!ids||!ids.length)return Promise.resolve({deleted:0});
  return API.del('/tasks?task_ids='+ids.map(encodeURIComponent).join('&task_ids='));
}
document.getElementById('histPurge').addEventListener('click',function(){
  var statuses=['failed','pending','processing','cancelled'],all=[];
  Promise.all(statuses.map(function(s){return fetchAllTaskIds(s).then(function(ids){all=all.concat(ids);});})).then(function(){
    var uniq=all.filter(function(v,i){return all.indexOf(v)===i;});
    if(!uniq.length){window.alert('没有可清理的记录（失败 / 排队中 / 进行中 / 已取消）');return;}
    if(!window.confirm('将批量删除 '+uniq.length+' 条记录（失败 / 排队中 / 进行中 / 已取消），不可恢复。确认？'))return;
    deleteTaskIds(uniq).then(function(r){
      window.alert('已删除 '+((r&&r.deleted)||uniq.length)+' 条记录');
      _histPage=1;renderHist();loadRecent();loadQueueSummary();
    }).catch(function(e){window.alert('删除失败: '+e);});
  });
});
// 清除全部历史
document.getElementById('histClear').addEventListener('click',function(){
  fetchAllTaskIds(null).then(function(ids){
    if(!ids.length){window.alert('当前没有历史记录');return;}
    if(!window.confirm('将清除全部 '+ids.length+' 条历史记录（含成功记录），不可恢复。确认？'))return;
    deleteTaskIds(ids).then(function(r){
      window.alert('已清除 '+((r&&r.deleted)||ids.length)+' 条记录');
      _histPage=1;renderHist();loadRecent();loadQueueSummary();
    }).catch(function(e){window.alert('清除失败: '+e);});
  });
});

/* ---------- F5: 预设右抽屉（真实渲染 + 应用/编辑/保存 + 多选批量删除） ---------- */
var _editPresetId=null;
var _selPresets={};
function updatePSelUI(){
  var ids=Object.keys(_selPresets).filter(function(k){return _selPresets[k];});
  var cnt=document.getElementById('pSelCount');if(cnt)cnt.textContent='已选 '+ids.length;
  var del=document.getElementById('pBatchDel');if(del)del.disabled=ids.length===0;
  var sa=document.getElementById('pSelectAll');
  if(sa){var all=document.querySelectorAll('#pList .p-check input');sa.textContent=(all.length&&ids.length===all.length)?'取消全选':'全选';}
}
function renderPresets(){
  var pl=document.getElementById('pList');if(!pl)return;
  fetch('/api/presets').then(function(r){return r.json();}).then(function(presets){
    pl.innerHTML='';
    // 清理已删除预设的残留选中
    var live={};presets.forEach(function(p){live[p.id]=1;});
    Object.keys(_selPresets).forEach(function(k){if(!live[k])delete _selPresets[k];});
    if(!presets||!presets.length){pl.innerHTML='<p style="grid-column:1/-1;text-align:center;color:var(--ink-faint);font-size:11px;padding:14px">暂无预设，点击「＋ 新建预设」创建</p>';updatePSelUI();return;}
    presets.forEach(function(p){
      var cfg=p.config||{};
      var chips='<span class="eng">'+engLabel(p.engine_name)+'</span>';
      if(cfg.steps!==undefined&&cfg.steps!==null)chips+='<span>'+cfg.steps+' steps</span>';
      if(cfg.cfg!==undefined&&cfg.cfg!==null)chips+='<span>cfg '+cfg.cfg+'</span>';
      if(cfg.width&&cfg.height)chips+='<span>'+cfg.width+'×'+cfg.height+'</span>';
      var c=document.createElement('div');c.className='p-card'+( _selPresets[p.id]?' sel':'');
      c.innerHTML='<label class="p-check"><input type="checkbox" data-id="'+p.id+'"'+( _selPresets[p.id]?' checked':'')+' aria-label="选择预设"><span></span></label>'+
        '<div class="nm">'+((p.name||'未命名').substring(0,20))+'</div>'+
        '<p class="ds">'+engLabel(p.engine_name)+'</p>'+
        '<div class="param-chips">'+chips+'</div>'+
        '<div class="acts"><button class="btn btn-sm ap" type="button">应用</button><button class="btn btn-sm ed" type="button">编辑</button><button class="btn btn-sm del" type="button" style="color:var(--red)">删除</button></div>';
      c.querySelector('.p-check input').addEventListener('change',function(){
        var chk=this;
        if(chk.checked){_selPresets[p.id]=true;c.classList.add('sel');}
        else{delete _selPresets[p.id];c.classList.remove('sel');}
        updatePSelUI();
      });
      c.querySelector('.ap').addEventListener('click',function(){applyPreset(p);});
      c.querySelector('.ed').addEventListener('click',function(){editPreset(p);});
      c.querySelector('.del').addEventListener('click',function(){
        if(!window.confirm('删除预设「'+(p.name||'')+'」？此操作不可恢复。'))return;
        API.del('/presets/'+p.id).then(function(){renderPresets();}).catch(function(e){window.alert('删除失败: '+e);});
      });
      pl.appendChild(c);
    });
    updatePSelUI();
  }).catch(function(e){console.warn('[Presets] load failed:',e);pl.innerHTML='<p style="grid-column:1/-1;text-align:center;color:var(--ink-faint);font-size:11px;padding:14px">加载失败</p>';});
}
var pSelectAllBtn=document.getElementById('pSelectAll');
if(pSelectAllBtn)pSelectAllBtn.addEventListener('click',function(){
  var all=document.querySelectorAll('#pList .p-check input');
  var selAll=all.length&&all.length===Object.keys(_selPresets).filter(function(k){return _selPresets[k];}).length;
  all.forEach(function(chk){
    chk.checked=!selAll;
    var card=chk.closest('.p-card');var id=+chk.dataset.id;
    if(!selAll){_selPresets[id]=true;card.classList.add('sel');}
    else{delete _selPresets[id];card.classList.remove('sel');}
  });
  updatePSelUI();
});
var pBatchDelBtn=document.getElementById('pBatchDel');
if(pBatchDelBtn)pBatchDelBtn.addEventListener('click',function(){
  var ids=Object.keys(_selPresets).filter(function(k){return _selPresets[k];}).map(Number);
  if(!ids.length)return;
  if(!window.confirm('将批量删除 '+ids.length+' 个预设，此操作不可恢复。确认？'))return;
  API.del('/presets?ids='+ids.join(',')).then(function(r){
    _selPresets={};
    window.alert('已删除 '+((r&&r.deleted)||ids.length)+' 个预设');
    renderPresets();
  }).catch(function(e){window.alert('删除失败: '+e);});
});
function applyPreset(p){
  if(!p)return;
  function doApply(cfg,eng){
    var es=document.getElementById('engineSelect');
    if(eng&&ENGINES[eng]&&es){es.value=eng;es.dispatchEvent(new Event('change'));syncEngMenu();}
    if(cfg.steps!==undefined&&cfg.steps!==null)document.getElementById('steps').value=cfg.steps;
    if(cfg.cfg!==undefined&&cfg.cfg!==null)document.getElementById('cfg').value=cfg.cfg;
    if(cfg.width!==undefined&&cfg.width!==null)document.getElementById('width').value=cfg.width;
    if(cfg.height!==undefined&&cfg.height!==null)document.getElementById('height').value=cfg.height;
    if(cfg.seed!==undefined&&cfg.seed!==null)document.getElementById('seed').value=cfg.seed;
    updateEst();
    window.alert('已应用预设：'+(p.name||''));
  }
  if(p.id){API.post('/presets/'+p.id+'/apply',{}).then(function(r){doApply(r.config||{},r.engine_name||p.engine_name);}).catch(function(e){window.alert('应用失败: '+e);});}
  else{doApply(p.config||{},p.engine_name||'');}
}
function editPreset(p){
  _editPresetId=p.id||null;
  document.getElementById('pName').value=p.name||'';
  var pEng=document.getElementById('pEngine');
  if(pEng){
    pEng.innerHTML='';
    Object.keys(ENGINES).forEach(function(k){var o=document.createElement('option');o.value=k;o.textContent=ENGINES[k];pEng.appendChild(o);});
    if(ENGINES[p.engine_name])pEng.value=p.engine_name;
  }
  document.getElementById('pDesc').value='参数 JSON：'+JSON.stringify(p.config||{});
  showPEdit();
}
var _origShowPList=showPList;
showPList=function(){_origShowPList();renderPresets();};
// 保存预设（新建 POST / 编辑 PUT）→ 真实接口
document.getElementById('pSave').addEventListener('click',function(){
  var name=document.getElementById('pName').value||'预设 '+(Date.now()%1000);
  var pEng=document.getElementById('pEngine');
  var eng=(pEng&&pEng.value)||document.getElementById('engineSelect').value;
  var cfg={positive_prompt:posPrompt.value,cfg:+document.getElementById('cfg').value||1.0,steps:+document.getElementById('steps').value||8,width:+document.getElementById('width').value||1024,height:+document.getElementById('height').value||1024,seed:+document.getElementById('seed').value||-1};
  if(_editPresetId){
    API.put('/presets/'+_editPresetId,{name:name,config:cfg}).then(function(){showPList();window.alert('预设已更新');}).catch(function(e){window.alert('保存失败: '+e);});
  }else{
    API.post('/presets',{engine_name:eng,name:name,config:cfg}).then(function(){showPList();window.alert('预设已保存');}).catch(function(e){window.alert('保存失败: '+e);});
  }
});

/* ---------- F7: 图库顶抽屉（真实渲染 + 标签映射） ---------- */
renderGallery=function(filter){
  filter=filter||'全部';
  gMasonry.innerHTML='';
  var f=FILTER_MAP[filter]||null;
  fetch('/api/outputs?page=1&page_size=50').then(function(r){return r.json();}).then(function(r){
    var list=(r.outputs||[]).filter(function(out){return !f||out.output_type===f;});
    if(!list.length){gMasonry.innerHTML='<p style="padding:20px;text-align:center;color:var(--ink-faint)">暂无图片</p>';return;}
    list.forEach(function(out,idx){
      var d=document.createElement('div');d.className='g-card';
      var ar=(out.width&&out.height)?out.width+'/'+out.height:'1/1';
      d.style.setProperty('--ar',ar);
      d.innerHTML='<span class="g-type">'+(TYPE_LABELS[out.output_type]||out.output_type||'输出')+'</span><div class="ph"><img src="/api/outputs/'+out.path+'" style="max-width:100%;max-height:200px;object-fit:contain" onerror="this.parentElement.textContent=\'加载失败\'"></div><div class="g-meta"><b>'+escHtml((out.prompt||'生成结果').substring(0,20))+'</b><span>'+escHtml(engLabel(out.engine))+' · '+(out.created_at?String(out.created_at).substring(5,16):'')+'</span></div>';
      d.addEventListener('click',function(){openViewerReal(out,list,idx);});
      gMasonry.appendChild(d);
    });
  }).catch(function(e){console.warn('[Gallery] load failed:',e);gMasonry.innerHTML='<p style="padding:20px;text-align:center;color:var(--ink-faint)">加载失败</p>';});
};
function openViewerReal(out,list,idx){
  _curViewer=out;
  if(list){_navList=list;_navIdx=(idx===undefined||idx===null)?-1:idx;}
  else{_navList=null;_navIdx=-1;}
  zoom=100;compare=false;
  vTitle.textContent=(out.prompt||'生成结果');
  vSeed.textContent=(out.seed===undefined||out.seed===null||out.seed===-1)?'seed 随机':'seed '+out.seed;
  // 底部信息栏：prompt（2 行截断，可展开）+ 参数 chips
  var pt=document.getElementById('vPromptText');
  if(pt){pt.textContent=out.prompt||'';pt.title=out.prompt||'';}
  var info=document.getElementById('vInfo');
  if(info)info.classList.remove('expanded');
  var toggle=document.getElementById('vPromptToggle');
  if(toggle)toggle.textContent=((out.prompt||'').length>70?'展开':'');
  var parts=[];
  parts.push(engLabel(out.engine));
  parts.push(TYPE_LABELS[out.output_type]||out.output_type||'');
  if(out.width&&out.height)parts.push(out.width+'×'+out.height);
  if(out.created_at)parts.push(String(out.created_at).substring(5,16));
  vMeta.innerHTML=parts.filter(Boolean).map(function(p){return '<span class="m-chip">'+escHtml(p)+'</span>';}).join('');
  updateNavUI();
  viewer.classList.add('show');
  renderImg();
}
function navViewer(d){
  if(!_navList||!_navList.length)return;
  var i=_navIdx+d;
  if(i<0||i>=_navList.length)return;
  openViewerReal(_navList[i],_navList,i);
}
function updateNavUI(){
  var p=document.getElementById('vPrev'),n=document.getElementById('vNext'),ix=document.getElementById('vIdx');
  if(ix)ix.textContent=(_navList&&_navList.length>1)?((_navIdx+1)+' / '+_navList.length):'';
  if(p)p.disabled=!_navList||_navIdx<=0;
  if(n)n.disabled=!_navList||_navIdx>=_navList.length-1;
}
function renderImgReal(out){_curViewer=out;renderImg();}
/* 覆盖原 mock renderImg：全屏大图 + 对比模式 */
renderImg=function(){
  vImg.style.transform='scale('+(zoom/100)+')';
  var out=_curViewer;
  if(compare&&out){
    vImg.className='v-img split-view';
    var basePath=out.path;
    var comparePath=basePath.replace(/\.png$/i,'_compare.png');
    vImg.innerHTML=
      '<div class="half"><span class="label">Original</span>'+
      '<img src="/api/outputs/'+basePath+'" alt="原图"></div>'+
      '<div class="divider"></div>'+
      '<div class="half"><span class="label">Compare</span>'+
      '<img src="/api/outputs/'+comparePath+'" alt="对比图" onerror="this.parentNode.style.display=\'none\'"></div>';
  }else if(compare){vImg.innerHTML='<div class="half"><span class="label">Compare</span><span style="color:rgba(245,240,234,.5)">无对比数据</span></div>';}
  else{
    vImg.className='v-img';
    vImg.innerHTML=out?'<img src="/api/outputs/'+out.path+'" alt="生成结果">':'<span style="color:rgba(245,240,234,.5);font-size:11px;letter-spacing:.1em">PREVIEW</span>';
  }
  vZoomVal.textContent=zoom+'%';
  document.getElementById('vCompare').classList.toggle('on',compare);
};

/* ---------- F9: 系统状态顶抽屉 ---------- */
var _origOpenStat=openStat;
openStat=function(){
  _origOpenStat();
  // 从后端加载系统状态
  fetch('/api/health').then(function(r){return r.json();}).then(function(h){
    var sd=document.getElementById('statDrawer');if(!sd)return;
    var gpu=h.gpu||{};
    // 查找或创建状态信息容器
    var infoBox=sd.querySelector('.stat-info');
    if(!infoBox){
      infoBox=document.createElement('div');infoBox.className='stat-info';infoBox.style.padding='16px';
      sd.querySelector('.ov-body').prepend(infoBox);
    }
    infoBox.innerHTML=
      '<p><b>状态:</b> '+h.status+'</p>'+
      '<p><b>版本:</b> '+(h.version||'')+'</p>'+
      '<p><b>GPU:</b> '+(gpu.name||'Unknown')+'</p>'+
      '<p><b>VRAM:</b> '+(gpu.total_vram_gb||0)+'GB total / '+(gpu.free_vram_gb||0)+'GB free</p>'+
      '<p><b>引擎:</b> '+(h.engines?h.engines.map(function(e){return e.display_name||e.name}).join(', '):'无')+'</p>'+
      '<p><b>时间:</b> '+new Date(h.timestamp*1000).toLocaleString()+'</p>';
  }).catch(function(e){console.warn('[Health] failed:',e);});
};

/* ---------- F8: 批量提交 + 进度轮询（真实 API） ---------- */
function collectBaseConfig(){
  return {
    positive_prompt:document.getElementById('posPrompt').value||'',
    negative_prompt:document.getElementById('negPrompt').value||'',
    cfg:+document.getElementById('cfg').value||1.0,
    steps:+document.getElementById('steps').value||8,
    width:+document.getElementById('width').value||1024,
    height:+document.getElementById('height').value||1024,
    seed:-1,
    batch_size:+(document.getElementById('bBatchSize')||{value:1}).value||1,
    seedvr2_enable:document.getElementById('seedvr2Toggle').checked,
    seedvr2_resolution:+(document.getElementById('upscaleRes')||{value:2048}).value||2048,
    eses_enable:document.getElementById('esesToggle').checked,
    vram_enable:document.getElementById('vramToggle').checked,
    vram_reserved_gb:+(document.getElementById('vramGb')||{value:0.6}).value||0.6,
    engine_name:document.getElementById('engineSelect').value
  };
}
var bSubmitBtn=document.getElementById('bSubmit');
if(bSubmitBtn){
  bSubmitBtn.addEventListener('click',function(){
    var prompts=bPrompts();
    if(!prompts.length){window.alert('请先添加 Prompt 文件');return;}
    var grid=bGridDims();
    bSubmitBtn.disabled=true;
    API.post('/generate/batch',{prompts:prompts,grid_dimensions:grid,base_config:collectBaseConfig()}).then(function(r){
      if(r.batch_id){
        try{localStorage.setItem('imm_last_batch',r.batch_id);}catch(e){}
        window.alert('批量任务已提交: '+r.total_tasks+' 个任务 (batch_id='+r.batch_id.substring(0,8)+')');
        renderBatchQueue(r.batch_id);
      }else{
        window.alert('批量提交失败: '+((r.error&&r.error.message)||r.detail||'未知错误'));
      }
    }).catch(function(e){window.alert('批量提交失败: '+e);}).then(function(){bSubmitBtn.disabled=false;});
  });
}
var bCancelBtn=document.getElementById('bCancel');
if(bCancelBtn)bCancelBtn.addEventListener('click',function(){document.getElementById('batchDrawer').classList.remove('open');});
var B_BATCH_POLL=null;
function renderBatchQueue(batchId){
  var box=document.getElementById('bQueueList');
  if(!box)return;
  var bid=batchId||null;
  if(!bid){try{bid=localStorage.getItem('imm_last_batch')||null;}catch(e){}}
  if(!bid){box.innerHTML='<p style="text-align:center;color:var(--ink-faint);font-size:10px;padding:10px 0">暂无批量任务</p>';return;}
  box.innerHTML='<p style="text-align:center;color:var(--ink-faint);font-size:10px;padding:10px 0">查询批次 '+bid.substring(0,8)+'…</p>';
  API.get('/tasks/batch/'+bid).then(function(r){
    if(r.batch_id){
      var pct=r.progress_pct||0;
      var done=(r.completed+r.failed+r.cancelled)>=r.total;
      box.innerHTML='<div class="qi-main"><div class="qi-title">batch '+bid.substring(0,8)+' · 共 '+r.total+' 任务</div><div class="qi-sub">'+r.completed+' 完成 · '+r.processing+' 进行中 · '+r.pending+' 排队 · '+r.failed+' 失败 · '+r.cancelled+' 取消</div><div class="progress"><i style="width:'+pct+'%"></i></div><div style="font-size:10px;color:var(--ink-faint);margin-top:2px">'+pct+'%</div></div>';
      if(!done){clearTimeout(B_BATCH_POLL);B_BATCH_POLL=setTimeout(function(){renderBatchQueue(bid);},2000);}
      else{loadRecent();}
    }else{
      box.innerHTML='<p style="text-align:center;color:var(--ink-faint);font-size:10px;padding:10px 0">'+escHtml(r.detail||'批次不存在或已过期')+'</p>';
      try{localStorage.removeItem('imm_last_batch');}catch(e){}
    }
  }).catch(function(){box.innerHTML='<p style="text-align:center;color:var(--ink-faint);font-size:10px;padding:10px 0">查询失败</p>';});
}


/* ---------- F3: LoRA 下拉从后端资源扫描填充 ---------- */
// 页面加载时从 /api/config 获取 LoRA 列表
fetch('/api/config').then(function(r){return r.json();}).then(function(cfg){
  // 尝试从配置中获取 LoRA 列表（如果后端提供了资源扫描接口）
  // 目前 LoRA 选项保持前端默认，后续可扩展
  console.log('[Init] Config loaded for LoRA dropdown');
}).catch(function(e){console.warn('[Init] Config load failed:',e);});

/* ================================================================
   F11-F13: 全局数据 + 初始化（真实数据源）
   原则：所有面板内容都来自后端接口，不再使用原型硬编码示例
   ================================================================ */
var ENGINES={};        // engine key → display_name（来自 /api/config）
var TYPE_LABELS={original:'原图',upscaled:'超分',compare:'对比图'};
var FILTER_MAP={'全部':null,'原图':'original','超分':'upscaled','对比图':'compare'};
var _CFG=null;         // 最近一次 /api/config 快照

function engLabel(k){return ENGINES[k]||k||'—';}

/* ---------- F14: 主题色切换（24 预设 + 自定义，localStorage 持久化） ---------- */
var ACCENTS=[
['蜜桃橙','#e8822a','#cf6e1a'],['橙焰','#f97316','#ea580c'],['琥珀','#f59e0b','#d97706'],['柠檬','#eab308','#ca8a04'],
['紫罗兰','#7c5fd6','#6b5bb8'],['靛蓝','#6366f1','#4f46e5'],['宝蓝','#3b82f6','#2563eb'],['天蓝','#0ea5e9','#0284c7'],
['青色','#06b6d4','#0891b2'],['青绿','#14b8a6','#0d9488'],['翡翠','#10b981','#059669'],['苔绿','#84cc16','#65a30d'],
['森林','#22c55e','#16a34a'],['朱红','#ef4444','#dc2626'],['玫红','#f43f5e','#e11d48'],['洋红','#ec4899','#db2777'],
['紫红','#d946ef','#c026d3'],['葡萄紫','#a855f7','#9333ea'],['藕荷','#c084fc','#a855f7'],['深紫','#8b5cf6','#7c3aed'],
['石板','#64748b','#475569'],['钢蓝','#475569','#334155'],['海蓝','#0f766e','#115e59'],['珊瑚','#fb7185','#f43f5e']
];
function renderPalette(){
  var grid=document.getElementById('palGrid');if(!grid)return;
  grid.innerHTML='';
  ACCENTS.forEach(function(a){
    var b=document.createElement('button');
    b.className='sw';b.type='button';b.title=a[0];b.dataset.p=a[1];b.dataset.a=a[2];
    b.style.background=a[1];
    b.addEventListener('click',function(){applyAccent(a[1],a[2]);});
    grid.appendChild(b);
  });
  syncPalette();
}
function applyAccent(primary,accent){
  var root=document.documentElement;
  root.style.setProperty('--seed-primary',primary);
  root.style.setProperty('--seed-accent',accent||primary);
  var dot=document.getElementById('palDot');if(dot)dot.style.background=primary;
  var pc=document.getElementById('palCustom');if(pc)pc.value=primary;
  try{localStorage.setItem('imm_accent',JSON.stringify([primary,accent||primary]));}catch(e){}
  syncPalette();
}
function syncPalette(){
  var cur=(document.documentElement.style.getPropertyValue('--seed-primary')||'#e8822a').trim().toLowerCase();
  document.querySelectorAll('#palGrid .sw').forEach(function(b){b.classList.toggle('on',b.dataset.p.toLowerCase()===cur);});
}
function initAccent(){
  var saved=null;try{saved=JSON.parse(localStorage.getItem('imm_accent')||'null');}catch(e){}
  if(saved&&saved[0]){
    var LEGACY={'#fdba74':'#e8822a','#fb923c':'#cf6e1a','#7c5fd6':'#e8822a','#6b5bb8':'#cf6e1a','#ef6d1c':'#cf6e1a','#f98a25':'#e8822a'};
    var s0=saved[0].toLowerCase(),s1=(saved[1]||'').toLowerCase();
    if(LEGACY[s0]){s0=LEGACY[s0];s1=LEGACY[s1]||s0;}
    applyAccent(s0,s1);
  }
  else{applyAccent('#e8822a','#cf6e1a');}
}
var palBtn=document.getElementById('palBtn'),palPop=document.getElementById('palPop');
if(palBtn)palBtn.addEventListener('click',function(e){
  e.stopPropagation();
  engMenu.classList.remove('show');langMenu.classList.remove('show');
  palPop.classList.toggle('show');
});
var palCustom=document.getElementById('palCustom');
if(palCustom)palCustom.addEventListener('input',function(){applyAccent(this.value,this.value);});
document.addEventListener('click',function(e){
  if(!e.target.closest('#palBtn')&&!e.target.closest('#palPop')){if(palPop)palPop.classList.remove('show');}
});
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&palPop)palPop.classList.remove('show');});

/* ---------- F15: 标题艺术字体切换（localStorage 持久化） ---------- */
var FONTS=[
  {name:'现代无衬线',desc:'Inter · 系统默认',fam:'var(--sans)'},
  {name:'思源宋体',desc:'优雅衬线 · Noto Serif SC',fam:'"Noto Serif SC",serif'},
  {name:'站酷小薇',desc:'文艺手写 · ZCOOL XiaoWei',fam:'"ZCOOL XiaoWei","Noto Serif SC",serif'},
  {name:'马善政楷书',desc:'毛笔书法 · Ma Shan Zheng',fam:'"Ma Shan Zheng",cursive'}
];
function renderFontList(){
  var box=document.getElementById('fontList');if(!box)return;
  box.innerHTML='';
  FONTS.forEach(function(f,i){
    var b=document.createElement('button');
    b.className='font-item';b.type='button';b.style.fontFamily=f.fam;
    b.innerHTML=f.name+'<span class="fd">'+f.desc+'</span>';
    b.addEventListener('click',function(){applyFont(i);});
    box.appendChild(b);
  });
  syncFontList();
}
function applyFont(i){
  var f=FONTS[i];if(!f)return;
  document.documentElement.style.setProperty('--title-font',f.fam);
  try{localStorage.setItem('imm_font',String(i));}catch(e){}
  syncFontList();
}
function syncFontList(){
  var saved=localStorage.getItem('imm_font');
  var idx=(saved!==null&&FONTS[+saved])?+saved:0;
  document.querySelectorAll('#fontList .font-item').forEach(function(b,i){b.classList.toggle('on',i===idx);});
}
function initFont(){
  var saved=localStorage.getItem('imm_font');
  applyFont((saved!==null&&FONTS[+saved])?+saved:0);
}
var fontBtn=document.getElementById('fontBtn'),fontPop=document.getElementById('fontPop');
if(fontBtn)fontBtn.addEventListener('click',function(e){
  e.stopPropagation();
  engMenu.classList.remove('show');langMenu.classList.remove('show');if(palPop)palPop.classList.remove('show');
  fontPop.classList.toggle('show');
});
document.addEventListener('click',function(e){
  if(!e.target.closest('#fontBtn')&&!e.target.closest('#fontPop')){if(fontPop)fontPop.classList.remove('show');}
});
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&fontPop)fontPop.classList.remove('show');});

function loadConfig(){
  return fetch('/api/config').then(function(r){return r.json();}).then(function(cfg){
    _CFG=cfg;
    var engs=cfg.models&&cfg.models.engines||{};
    ENGINES={};
    Object.keys(engs).forEach(function(k){ENGINES[k]=engs[k].display_name||k;});
    return cfg;
  }).catch(function(e){console.warn('[Init] config load failed:',e);return null;});
}

/* ---------- F11: 引擎菜单 + 参数默认值（来自后端配置） ---------- */
function initEngines(){
  var sel=document.getElementById('engineSelect');
  var menu=document.getElementById('engMenu');
  var keys=Object.keys(ENGINES);
  if(!keys.length||!sel)return;
  var cur=sel.value;
  sel.innerHTML='';
  if(menu)menu.innerHTML='';
  keys.forEach(function(k){
    var label=ENGINES[k];
    var o=document.createElement('option');o.value=k;o.textContent=label;sel.appendChild(o);
    if(menu){var b=document.createElement('button');b.className='ip-item';b.type='button';b.dataset.v=k;b.textContent=label;menu.appendChild(b);}
  });
  var def=_CFG&&_CFG.models&&_CFG.models.default_engine;
  if(ENGINES[cur])sel.value=cur;
  else if(def&&ENGINES[def])sel.value=def;
  else sel.value=keys[0];
  if(menu)menu.querySelectorAll('.ip-item').forEach(function(b){
    b.addEventListener('click',function(){
      menu.querySelectorAll('.ip-item').forEach(function(x){x.classList.remove('on');});
      b.classList.add('on');
      var es=document.getElementById('engineSelect');es.value=b.dataset.v;es.dispatchEvent(new Event('change'));
      closeMenus();
    });
  });
  syncEngMenu();
}
function syncEngMenu(){
  var cur=document.getElementById('engineSelect').value;
  document.querySelectorAll('#engMenu .ip-item').forEach(function(b){b.classList.toggle('on',b.dataset.v===cur);});
  syncChips();
}
function initDefaults(){
  if(!_CFG)return;
  var inf=_CFG.inference||{};
  function setv(id,v,def){var el=document.getElementById(id);if(el)el.value=(v!==undefined&&v!==null)?v:def;}
  setv('steps',inf.default_steps,8);
  setv('cfg',inf.default_cfg,1.0);
  setv('seed',inf.default_seed,-1);
  setv('batchSize',inf.default_batch_size,1);
  var ec=(_CFG.models&&_CFG.models.engines&&_CFG.models.engines[document.getElementById('engineSelect').value])||{};
  setv('width',ec.default_width||1024,1024);
  setv('height',ec.default_height||1024,1024);
}
function resetToDefaults(){
  if(!_CFG){window.alert('配置尚未加载，请稍后重试');return;}
  initDefaults();
  document.getElementById('seedvr2Toggle').checked=false;
  document.getElementById('esesToggle').checked=false;
  document.getElementById('vramToggle').checked=true;
  document.getElementById('vramGb').value=0.6;
  document.getElementById('upscaleSeed').value=-1;
  document.getElementById('vramSeed').value=-1;
  updateEst();
  window.alert('已恢复为后端默认参数');
}

/* ---------- F12: 最近生成（真实输出） ---------- */
function loadRecent(){
  var grid=document.getElementById('outGrid');
  if(!grid)return;
  grid.innerHTML='<p style="grid-column:1/-1;text-align:center;color:var(--ink-faint);font-size:11px;padding:16px 0">加载最近生成…</p>';
  fetch('/api/outputs?page=1&page_size=9').then(function(r){return r.json();}).then(function(r){
    var list=r.outputs||[];
    if(!list.length){grid.innerHTML='<p style="grid-column:1/-1;text-align:center;color:var(--ink-faint);font-size:11px;padding:16px 0">暂无生成记录</p>';return;}
    grid.innerHTML='';
    list.forEach(function(out,idx){
      var c=document.createElement('div');c.className='r-card';c.style.setProperty('--ar','1/1');
      var label=TYPE_LABELS[out.output_type]||out.output_type||'输出';
      var meta=engLabel(out.engine)+(out.created_at?' · '+String(out.created_at).substring(5,16):'');
      c.innerHTML='<div class="ph-img"><img src="/api/outputs/'+out.path+'" style="max-width:100%;max-height:220px;object-fit:contain;display:block;margin:0 auto" onerror="this.parentElement.textContent=\'加载失败\'"><div class="r-actions"><button class="btn btn-sm" type="button" onclick="event.stopPropagation();window.open(\'/api/outputs/'+out.path+'\',\'_blank\')">下载</button><button class="btn btn-sm" type="button" onclick="event.stopPropagation();window.open(\'/api/tasks/export?ids='+out.task_id+'\',\'_blank\')">ZIP</button><button class="btn btn-sm" type="button" onclick="event.stopPropagation();redrawTask(\''+out.task_id+'\')">重绘</button></div></div><div class="r-meta"><b>'+escHtml((out.prompt||'生成结果').substring(0,18))+'</b><span>'+escHtml(label)+' · '+escHtml(meta)+'</span></div>';
      c.addEventListener('click',function(){openViewerReal(out,list,idx);});
      grid.appendChild(c);
    });
  }).catch(function(){grid.innerHTML='<p style="grid-column:1/-1;text-align:center;color:var(--ink-faint);font-size:11px;padding:16px 0">加载失败</p>';});
}

/* ---------- F13: 队列悬浮球（真实任务） ---------- */
function renderQueue(){
  var box=document.getElementById('queueItems');if(!box)return;
  box.innerHTML='<p style="text-align:center;color:var(--ink-faint);font-size:10px;padding:10px">加载中…</p>';
  fetch('/api/tasks?page=1&page_size=30').then(function(r){return r.json();}).then(function(r){
    var list=(r.tasks||[]).filter(function(t){return t.status==='pending'||t.status==='processing'||t.status==='queued';});
    if(!list.length){box.innerHTML='<p style="text-align:center;color:var(--ink-faint);font-size:10px;padding:10px">队列空闲</p>';return;}
    box.innerHTML='';
    list.forEach(function(t){
      var d=document.createElement('div');d.className='q-item';
      var st=t.status==='processing'?'进行中':'排队中';
      d.innerHTML='<div class="t"><b>'+escHtml((t.task_id||'').substring(0,12))+' · '+escHtml((t.prompt||'未命名').substring(0,16))+'</b><span>'+st+' · '+(t.output_count||0)+' 输出</span></div><span class="p">'+(t.status==='processing'?'…':'—')+'</span>';
      box.appendChild(d);
    });
  }).catch(function(){box.innerHTML='<p style="text-align:center;color:var(--ink-faint);font-size:10px;padding:10px">加载失败</p>';});
}
function loadQueueSummary(){
  fetch('/api/tasks?page=1&page_size=30').then(function(r){return r.json();}).then(function(r){
    var n=(r.tasks||[]).filter(function(t){return t.status==='pending'||t.status==='processing';}).length;
    if(qpText)qpText.textContent='队列 '+(n||0);
  }).catch(function(){});
}

/* ---------- 页面加载完成后的初始化（真实数据） ---------- */
renderPalette();
initAccent();
renderFontList();
initFont();
loadConfig().then(function(cfg){
  if(cfg)initEngines();
  if(cfg)initDefaults();
  updateEst();
  loadRecent();
  loadQueueSummary();
  loadHealth();
  setInterval(loadHealth,15000);
  setInterval(loadQueueSummary,5000);
  var he=document.getElementById('histEngine');
  if(he){he.innerHTML='<option value="">引擎</option>';Object.keys(ENGINES).forEach(function(k){var o=document.createElement('option');o.value=k;o.textContent=ENGINES[k];he.appendChild(o);});}
});
// 标记用户手动改过的参数（引擎切换时不再覆盖分辨率）
['width','height','steps','cfg','seed','batchSize'].forEach(function(id){var el=document.getElementById(id);if(el)el.addEventListener('input',function(){el.dataset.touched='1';});});
