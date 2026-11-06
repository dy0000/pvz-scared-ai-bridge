'use strict';
// Story mechanics call the same native callbacks as the player's UI. No save edits.
const STORY_OPERATIONS = ['game_info','shovel','move_plant','interact','set_slow','set_speed','set_paused',
  'set_difficulty','rewards','collect_reward','choose_event','next_level','almanac','almanac_select',
  'store','buy','purchase_receipt','ui_controls','set_ui_value','test_assist'];
const purchaseReceipts=new Map();
function excludedMode(name) { return /^(HappyMode|SurvivalMode|EntertainmentMode)$/i.test(name); }
function present(full) { return objects(full).filter(active); }
function fieldExists(full,name) { return !!PROFILE.classes[full]?.fields.some(f=>f.name===name); }
function staticStorage(full) { return klass(full).add(0xb8).readPointer(); }
function staticRead(full,name) { return read(staticStorage(full),full,name); }
function uiText(p) { return p.isNull()?'':managedString(call('TMPro.TMP_Text','get_text',p)); }
function settingsObject() { return staticRead('.GameAPP','$ZK'); }
function saveObject() { return staticRead('.SaveMgr','$JW'); }
function inspectClass(full) {
  const k=klass(full),it=Memory.alloc(8);it.writePointer(nil);
  const type=t=>classNameOfType(classOfType(t,1));
  const fields=[],methods=[];
  for(let i=0;i<2000;i++){
    const f=classFields(k,it);if(f.isNull())break;const t=f.add(32).readPointer();
    fields.push({name:f.add(16).readPointer().readCString(),offset:f.add(8).readS32(),type:type(t),flags:t.add(8).readU16()});
  }
  it.writePointer(nil);
  for(let i=0;i<2000;i++){
    const m=classMethods(k,it);if(m.isNull())break;const count=m.add(0x52).readU8();
    methods.push({name:m.add(0x18).readPointer().readCString(),rva:m.readPointer().sub(base).toString(),
      returns:type(m.add(32).readPointer()),parameters:Array.from({length:count},(_,j)=>type(m.add(48).readPointer().add(j*8).readPointer())),flags:m.add(0x4c).readU16()});
  }
  return {name:full.slice(full.lastIndexOf('.')+1),namespace:full.slice(0,full.lastIndexOf('.')),
    parent:classNameOfType(k.add(0xa8).readPointer()),fields,methods};
}
function classNameOfType(k){return k.isNull()?'Void':k.add(0x98).readPointer().readCString();}
function levelInfo(data) {
  if(data.isNull())return null;
  return {name:read(data,'.LevelDataJson','LevelName'),description:read(data,'.LevelDataJson','LevelDescription'),
    rows:read(data,'.LevelDataJson','totalRows'),waves:read(data,'.LevelDataJson','mTotalWaves'),
    start_sun:read(data,'.LevelDataJson','StartSun'),background:read(data,'.LevelDataJson','background'),
    components:list(read(data,'.LevelDataJson','components')).map(p=>read(p,'.LevelComponentJson','type'))};
}
function gameInfo(r={}) {
  const save=saveObject(), settings=settingsObject();
  const info={game:'PVZ-Scared',scope:'story',excluded_modes:['survival','entertainment']};
  if(!save.isNull()) info.progress={player_name:read(save,'.SaveData','playerName'),
    level:read(save,'.SaveData','adventureLevel'),highest_unlocked_level:read(save,'.SaveData','highestUnlockedAdventureLevel'),
    completed:read(save,'.SaveData','hasCompletedAdventure'),money:read(save,'.SaveData','money'),
    seed_slots:read(save,'.SaveData','seedSlotCount')};
  if(!settings.isNull()) info.settings={game_speed:read(settings,'.PlayerSettings','gameSpeed'),
    difficulty:read(settings,'.PlayerSettings','difficultyPreset'),nightmare_unlocked:read(settings,'.PlayerSettings','nightmareUnlocked')};
  const data=save.isNull()?nil:read(save,'.SaveData','currentLevelData');
  if(!data.isNull())info.level=levelInfo(data);
  if(r.level!==undefined){
    if(!Number.isInteger(r.level)||r.level<1)throw Error('level must be a positive integer');
    info.requested_level={number:r.level,...levelInfo(call('.SaveMgr','$MbA',nil,r.level))};
  }
  if(r.inspect_class)info.native_schema=inspectClass(r.inspect_class);
  return info;
}
function positionOf(p) { return call('UnityEngine.Transform','get_position',call('UnityEngine.Component','get_transform',p)); }
function checkCell(b,row,column) {
  if(!Number.isInteger(row)||!Number.isInteger(column)||row<1||column<1||row>read(b,'.Board','rowNum')||column>read(b,'.Board','columnNum')) throw Error('Cell outside native board');
}
function atPointer(b,row,column,body,worldPoint=null) {
  if(!worldPoint)checkCell(b,row,column);
  const m=singleton('.Mouse'); if(!alive(m))throw Error('Native mouse unavailable');
  const oldGrid=m.add(32).readByteArray(16),oldPosition=m.add(108).readByteArray(16);
  const local=worldPoint?boardPoint(b,worldPoint[0],worldPoint[1],false):[call('.Board','$DA',b,column-1),call('.Board','$eA',b,row-1)];
  const [x,y]=local,world=worldPoint||boardPoint(b,x,y);
  const project=pointerProjector(),point=project(world[0],world[1]);
  try {
    setPointer(point);
    m.add(32).writeS32(row-1);m.add(36).writeS32(column-1);m.add(40).writeFloat(x);m.add(44).writeFloat(y);
    m.add(108).writeFloat(point[0]);m.add(112).writeFloat(point[1]);m.add(116).writeFloat(x);m.add(120).writeFloat(y);
    return body(m,project);
  } finally {
    clearPointer();
    try {m.add(32).writeByteArray(oldGrid);m.add(108).writeByteArray(oldPosition);}
    finally {releaseSelection();}
  }
}
function requireEmptySelection() { if(selection()!==0) throw Error('Native selection is already in use'); }
function currentPlant(b,id) {
  const p=list(read(b,'.Board','plantArray')).find(p=>alive(p)&&p.toString()===id);
  if(!p)throw Error('Plant is no longer in the current battle');return p;
}
function plantAbility(p) {
  if(className(p)!=='PastorGarlic'||!PROFILE.classes['.PastorGarlic'])return null;
  return {kind:'pastor',crosses:read(p,'.PastorGarlic','$MB'),spent:read(p,'.PastorGarlic','$NB'),
    recharge:read(p,'.PastorGarlic','$nB'),restore:read(p,'.PastorGarlic','$pB')};
}
const plantUpdates=new Map();
function clickPlantUpdate(p) {
  const key=String(p.readPointer());
  let invoke=plantUpdates.get(key);
  if(!invoke){
    if(className(p)==='PastorGarlic'&&PROFILE.classes['.PastorGarlic'])invoke=target=>call('.PastorGarlic','$cC',target);
    let k=p.readPointer();
    while(!k.isNull()&&!invoke){
      const it=Memory.alloc(8);it.writePointer(nil);
      for(let i=0;i<2000;i++){
        const m=classMethods(k,it);if(m.isNull())break;
        if(m.add(0x18).readPointer().readCString()==='Update'&&m.add(0x52).readU8()===0){
          const fn=native(m.readPointer(),'void',['pointer','pointer']);invoke=target=>fn(target,m);break;
        }
      }
      k=k.add(0xa8).readPointer();
    }
    if(invoke)plantUpdates.set(key,invoke);
  }
  if(!invoke)return;
  if(pointerState)pointerState.add(24).writeU32(1);
  try{invoke(p);}finally{if(pointerState)pointerState.add(24).writeU32(0);}
}
function sourcePlantCell(p) { return {row:read(p,'.BoardEntity','theRow')+1,column:read(p,'.BoardEntity','theColumn')+1}; }
function chooseTool(kind) {
  const full=kind==='shovel'?'.Shovel':'.Glove',tools=present(full);
  if(tools.length!==1)throw Error('Native '+kind+' is locked or unavailable');
  ownsSelection=true;call(full,'$jJA',tools[0],true);
  if(selection()===0)throw Error('Native tool selection refused');return tools[0];
}
function plantPointer(p,m,project) {
  const origin=positionOf(p);
  // Plant transforms sit at their feet; click the first point that actually hits
  // this plant's native collider, including small mines and tall/stacked plants.
  for(const dy of [0,0.35,0.7,1.05,1.4]) {
    const screen=project(origin[0],origin[1]+dy);
    const hit=call('.Mouse','$dP',m,[screen[0],screen[1]]);
    if(hit.equals(p))return screen;
  }
  throw Error('Native pointer cannot resolve this plant');
}
function shovelPlant(r) {
  const b=requireBattle(r);requirePhase(b,'Playing');requireEmptySelection();
  const p=currentPlant(b,r.entity_id),cell=sourcePlantCell(p),point=positionOf(p);
  return atPointer(b,cell.row,cell.column,(m,project)=>{
    chooseTool('shovel');
    setPointer(plantPointer(p,m,project));
    call('.Mouse','$MP',m);
    const removed=!alive(p)||read(p,'.BoardEntity','dying')||!list(read(b,'.Board','plantArray')).some(q=>q.equals(p));
    return {status:removed?'Committed':'rejected_by_game',entity_id:r.entity_id};
  },point);
}
function movePlant(r) {
  const b=requireBattle(r);requirePhase(b,'Playing');checkCell(b,r.row,r.column);requireEmptySelection();
  const p=currentPlant(b,r.entity_id),cell=sourcePlantCell(p),point=positionOf(p),m=singleton('.Mouse');
  const project=pointerProjector();
  // Pickup and drop are one main-thread action; no selected plant survives the request.
  const oldGrid=m.add(32).readByteArray(16),oldPosition=m.add(108).readByteArray(16);
  function pointAt(row,column,x,y,worldPoint=null) {
    const world=worldPoint||boardPoint(b,x,y),screen=project(world[0],world[1]);
    setPointer(screen);
    m.add(32).writeS32(row-1);m.add(36).writeS32(column-1);m.add(40).writeFloat(x);m.add(44).writeFloat(y);
    m.add(108).writeFloat(screen[0]);m.add(112).writeFloat(screen[1]);m.add(116).writeFloat(x);m.add(120).writeFloat(y);
  }
  try {
    const local=boardPoint(b,point[0],point[1],false);
    pointAt(cell.row,cell.column,local[0],local[1],point);chooseTool('glove');setPointer(plantPointer(p,m,project));
    call('.Mouse','$NP',m);
    if(!read(m,'.Mouse','$EL').equals(p))throw Error('Native glove pickup refused');
    pointAt(r.row,r.column,call('.Board','$DA',b,r.column-1),call('.Board','$eA',b,r.row-1));
    call('.Mouse','$oP',m);
    const after=alive(p)?sourcePlantCell(p):null;
    return {status:after&&after.row===r.row&&after.column===r.column?'Committed':'rejected_by_game',
      entity_id:r.entity_id,from:cell,to:after};
  } finally {
    clearPointer();
    try {m.add(32).writeByteArray(oldGrid);m.add(108).writeByteArray(oldPosition);}
    finally {releaseSelection();}
  }
}
function specialCards() {
  const drops=present('.PlantCard').filter(p=>read(p,'.PlantCard','isPlantCardItem')&&!read(p,'.Item','dying')&&!read(p,'.Item','$ol')).map(p=>({
    card_id:'drop:'+p,source:'falling',plant_type:read(p,'.PlantCard','plantType'),
    plant_name:enumName('.$xB',read(p,'.PlantCard','plantType')),available:true,position:positionOf(p)}));
  const belts=present('.ConveyorBeltCardView').map(p=>({
    card_id:'belt:'+p,source:'conveyor',plant_type:read(p,'.ConveyorBeltCardView','$bJ'),
    plant_name:enumName('.$xB',read(p,'.ConveyorBeltCardView','$bJ')),available:true}));
  return [...belts,...drops];
}
function plantSpecial(r) {
  const b=requireBattle(r);requirePhase(b,'Playing');checkCell(b,r.row,r.column);requireEmptySelection();
  const type=r.card_id.startsWith('drop:')?'drop':'belt',full=type==='drop'?'.PlantCard':'.ConveyorBeltCardView';
  const p=present(full).find(p=>type+':'+p===r.card_id);
  if(!p)throw Error('Special card is no longer available');
  const plantType=type==='drop'?read(p,full,'plantType'):read(p,full,'$bJ');
  const before=new Set(list(read(b,'.Board','plantArray')).map(String)),sun=read(b,'.Board','theSun');
  return atPointer(b,r.row,r.column,m=>{
    ownsSelection=true;
    const selected=type==='drop'?call('.Mouse','$HP',m,p,false):call('.Mouse','$iP',m,p);
    if(!selected)return {status:'rejected',reason:'native_selection_refused'};
    call('.Mouse','$kP',m);
    const created=list(read(b,'.Board','plantArray')).filter(p=>alive(p)&&!before.has(String(p))).map(p=>entity(p,'.Plant')).filter(Boolean);
    return {status:created.some(p=>p.row===r.row&&p.column===r.column&&p.content_type===plantType)?'Committed':'rejected_by_game',
      plants:created,sun_before:sun,sun_after:read(b,'.Board','theSun')};
  });
}
function bossInfo(p) {
  const boss=read(p,'.BossBattleController','$Yh'),arena=read(p,'.BossBattleController','$zh');
  const bossAlive=alive(boss),arenaAlive=alive(arena);
  const parts=arenaAlive?['$ke','$Ke'].map(name=>read(arena,'.DaveLevel2ArenaController',name)).filter(alive).map(part=>({
    entity_id:String(part),kind:className(part),health:read(part,'.BoardEntity','theHealth'),
    max_health:read(part,'.BoardEntity','theMaxHealth'),dying:read(part,'.BoardEntity','dying'),position:positionOf(part),
    ...(PROFILE.classes['.BossPart']?{part_name:read(part,'.BossPart','$MC'),
      splash_rows:Array.from({length:read(read(p,'.BossBattleController','$Xh'),'.Board','rowNum')},(_,i)=>i+1)
        .filter(row=>call('.BossPart','$PE',part,row-1,1))}:{} )})):[];
  return {active:bossAlive||arenaAlive,entity_id:bossAlive?String(boss):arenaAlive?String(arena):null,
    kind:bossAlive?className(boss):arenaAlive?'DaveLevel2ArenaController':null,
    health:bossAlive?read(boss,'.BoardEntity','theHealth'):parts.length?parts.reduce((sum,part)=>sum+Math.max(0,part.health),0):null,
    arena:arenaAlive?{entity_id:String(arena),head_attack_countdown:read(arena,'.DaveLevel2ArenaController','headAttackCountdownRemaining')}:null,parts};
}
function storyObservation(state) {
  state.game_info=gameInfo();
  const b=getBoard();if(b.isNull())return state;
  state.cards=(state.cards||[]).map(c=>({...c,source:'bank'}));state.cards.push(...specialCards());
  state.tools=present('.ToolMgr').map(p=>({tool_id:String(p),kind:className(p),
    item_type:enumName('.$uB',read(p,'.ToolMgr','ItemType')),picked_up:read(p,'.ToolMgr','isPickUp'),
    cooldown:className(p)==='Glove'?Math.max(0,read(p,'.Glove','$Fm')):0}));
  state.time_scale=call('UnityEngine.Time','get_timeScale',nil);
  const ui=singleton('.InGameUIMgr',48);state.slow_enabled=!ui.isNull()&&read(ui,'.InGameUIMgr','$tP');
  state.mechanics={conveyor:!read(b,'.Board','conveyorBelt').isNull(),falling_cards:!read(b,'.Board','rainingSeeds').isNull(),
    selectable:read(b,'.Board','cardSelectable'),bank:read(b,'.Board','cardBank')};
  const waves=read(b,'.Board','zombieWavesMgr');
  if(!waves.isNull())state.wave_state={can_win:read(waves,'.ZombieWavesMgr','canWin'),initialized:read(waves,'.ZombieWavesMgr','mIsInitialized'),
    next_wave_timer:read(waves,'.ZombieWavesMgr','mNextWavesTimer'),total_health:read(waves,'.ZombieWavesMgr','mZombieTotalHealth'),
    native_zombie_count:read(b,'.Board','zombieArray').add(24).readS32()};
  const roads=read(b,'.Board','roadType');
  state.terrain={row_types:roads.isNull()?[]:Array.from({length:Math.min(roads.add(24).readU32(),state.rows)},(_,i)=>roads.add(32+i*4).readS32())};
  state.obstacles=list(read(b,'.Board','obstacleArray')).filter(alive).map(p=>({entity_id:String(p),kind:className(p),
    ...sourcePlantCell(p),position:positionOf(p),health:read(p,'.BoardEntity','theHealth'),dying:read(p,'.BoardEntity','dying'),type:enumName('.$VB',read(p,'.Obstacle','type'))}));
  state.grid_items=list(read(b,'.Board','gridItemArray')).filter(alive).map(p=>({entity_id:String(p),kind:className(p),
    ...sourcePlantCell(p),position:positionOf(p),type:enumName('.$E',read(p,'.GridItem','type'))}));
  state.bosses=present('.BossBattleController').map(bossInfo);
  return state;
}
function storeAncestor(p) {
  let transform=call('UnityEngine.Component','get_transform',p);
  for(let i=0;i<20&&!transform.isNull();i++) {
    if(/StoreProduct|Product|Buy|Purchase/i.test(objectName(transform)))return true;
    transform=call('UnityEngine.Transform','get_parent',transform);
  }
  return false;
}
function matchingButton(full,label) {
  const buttons=present(full).filter(p=>objectName(p)===label);
  if(buttons.length!==1)throw Error('Native button unavailable: '+label);return buttons[0];
}
function setPaused(r) {
  const b=requireBattle(r),phase=enumName('.$QB',read(b,'.Board','theBoardStatus'));
  if(typeof r.paused!=='boolean')throw Error('paused must be boolean');
  const paused=phase==='Pause'||phase==='PauseWhenSelecting';
  if(paused===r.paused)return {paused};
  if(!['Playing','Selecting','Pause','PauseWhenSelecting'].includes(phase))throw Error('Pause unavailable during transition');
  if(r.paused) {
    const p=matchingButton('.InGameBtn','Menu');call('.InGameBtn','OnMouseEnter',p);
    try {call('.InGameBtn','OnMouseDown',p);call('.InGameBtn','OnMouseUpAsButton',p);}
    finally {call('.InGameBtn','OnMouseExit',p);}
  } else clickNative('.UIButtonBase',matchingButton('.PauseMenuBtn','ReturnGame'));
  return {status:'pause_requested',paused:r.paused};
}
function setSlow(r) {
  const b=requireBattle(r);requirePhase(b,'Playing');
  if(typeof r.enabled!=='boolean')throw Error('enabled must be boolean');
  const ui=singleton('.InGameUIMgr',48);if(ui.isNull())throw Error('Native battle UI unavailable');
  if(read(ui,'.InGameUIMgr','$tP')!==r.enabled)call('.InGameUIMgr','$cW',ui);
  return {enabled:read(ui,'.InGameUIMgr','$tP'),time_scale:call('UnityEngine.Time','get_timeScale',nil)};
}
function setSpeed(r) {
  requireControl();if(typeof r.speed!=='number'||!Number.isFinite(r.speed))throw Error('speed must be finite');
  let dialogs=present('.Dialog').filter(p=>/速度/.test(uiText(read(p,'.Dialog','Header'))));
  if(!dialogs.length) {
    const buttons=present('.InGameBtn').filter(p=>/speed/i.test(objectName(p)));
    if(buttons.length===1) {
      call('.InGameBtn','OnMouseEnter',buttons[0]);
      try {call('.InGameBtn','OnMouseDown',buttons[0]);call('.InGameBtn','OnMouseUpAsButton',buttons[0]);}
      finally {call('.InGameBtn','OnMouseExit',buttons[0]);}
    }
    dialogs=present('.Dialog').filter(p=>/速度/.test(uiText(read(p,'.Dialog','Header'))));
  }
  const sliders=present('UnityEngine.UI.Slider').filter(p=>/\/SpeedDialog\//.test(controlPath(p)));
  if(dialogs.length!==1||sliders.length!==1)throw Error('Native speed slider is unavailable');
  const slider=sliders[0];
  // Native dialog slider positions are speed presets, not multiplier values.
  const speeds=[0.5,1,1.5,2,3];
  const index=speeds.reduce((best,value,i)=>Math.abs(value-r.speed)<Math.abs(speeds[best]-r.speed)?i:best,0);
  call('UnityEngine.UI.Slider','set_value',slider,index);
  const yes=matchingButton('.UIButtonBase','Yesbtn');clickNative('.UIButtonBase',yes);
  return {game_speed:gameInfo().settings.game_speed};
}
function setDifficulty(r) {
  requireControl();const menus=present('.DifficultyControlMenu');
  const action={easy:'$ow',normal:'$Ow',hard:'$pw',nightmare:'$ilA'}[r.preset];
  if(!action)throw Error('Unknown native difficulty preset');
  if(menus.length!==1)throw Error('Open the native difficulty menu first');
  call('.DifficultyControlMenu',action,menus[0]);
  const settings=gameInfo().settings;return {status:settings.difficulty===r.preset?'confirmed':'rejected_by_game',settings};
}
function rewards() {
  const b=getBoard();
  const items=present('.WinItem').filter(p=>!read(p,'.Item','$ol')).map(p=>({reward_id:String(p),kind:className(p),
    item_type:enumName('.$TB',read(p,'.Item','theItemType'))}));
  const events=present('.EventCard').map(p=>({event_id:String(p),kind:enumName('.$ab',read(p,'.EventCard','cardType')),
    name:uiText(read(p,'.EventCard','_name')),description:uiText(read(p,'.EventCard','_description')),
    native_state:p.add(80).readS32(),revealed:p.add(80).readS32()!==0,animating:read(p,'.EventCard','$WM')}));
  return {battle_id:b.isNull()?null:battleId(),items,events,game_info:gameInfo()};
}
function collectReward(r) {
  requireBattle(r);const listNow=rewards().items;
  if(!listNow.some(p=>p.reward_id===r.reward_id))throw Error('Reward is no longer present');
  const p=present('.WinItem').find(p=>String(p)===r.reward_id),kind=className(p);
  if(!['MoneyBag','WinItem'].includes(kind))throw Error('Unknown native reward type');
  call('.'+kind,'$cJA',p,false);return {status:'reward_requested',reward_id:r.reward_id};
}
function chooseEvent(r) {
  requireControl();const p=present('.EventCard').find(p=>String(p)===r.event_id);
  if(!p)throw Error('Native event is no longer present');
  // The native Button listener owns reveal/zoom/selection. $WM is an animation
  // lock, and $nR is a zoom-out callback, not the event commit callback.
  const button=call('UnityEngine.GameObject','GetComponent',componentGameObject(p),reflectionType('UnityEngine.UI.Button'));
  if(button.isNull())throw Error('Native event button unavailable');
  call('UnityEngine.UI.Button','Press',button);
  return {status:'event_requested',event_id:r.event_id};
}
function nextLevel(r) {
  requireControl();const actions=menu();
  const candidates=actions.actions.filter(a=>/^(NextLevel|Next|Continue)$/i.test(a.label));
  if(candidates.length===1)return dispatch({op:'menu_action',menu_id:actions.menu_id,action_id:candidates[0].action_id});
  if(!getBoard().isNull())throw Error('Collect the native victory reward and finish event selection first');
  const confirms=present('.LevelChooseConfirmButton');
  if(confirms.length===1) {
    try {clickNative('.UIButtonBase',confirms[0]);return {status:'navigation_requested'};}
    catch(e) {if(e.message!=='Native button gate refused')throw e;}
  }
  const buttons=present('.LevelChooseButton'),level=gameInfo().progress.level;
  const target=buttons.find(p=>read(p,'.LevelChooseButton','$sm')===level);
  if(target){clickNative('.UIButtonBase',target);return {status:'level_selected',level};}
  const maps=present('.MapChooseButton');
  if(maps.length===1){clickNative('.UIButtonBase',maps[0]);return {status:'chapter_selected'};}
  const story=actions.actions.find(a=>a.label==='StoryMode');
  if(story)return dispatch({op:'menu_action',menu_id:actions.menu_id,action_id:story.action_id});
  throw Error('Native continuation is not ready; inspect menu');
}
function almanac() {
  return {entries:[...present('.CardAlmanac').map(p=>({entry_id:String(p),kind:'plant',name:enumName('.$xB',read(p,'.CardAlmanac','id'))})),
    ...present('.BlockAlmanac').map(p=>({entry_id:String(p),kind:'zombie',name:enumName('.$Ac',read(p,'.BlockAlmanac','id'))}))],
    texts:objects('TMPro.TMP_Text').map(p=>({name:objectName(p),text:uiText(p)}))};
}
function almanacSelect(r) {
  requireControl();const full=r.kind==='plant'?'.CardAlmanac':r.kind==='zombie'?'.BlockAlmanac':null;
  if(!full)throw Error('Invalid almanac entry kind');
  const p=present(full).find(p=>String(p)===r.entry_id);if(!p)throw Error('Entry is not present on this native page');
  call(full,'OnMouseDown',p);return {status:'navigation_requested'};
}
function store() {
  const products=present('.StoreProduct').map(p=>{
    const priceText=uiText(read(p,'.StoreProduct','price')),match=priceText.replace(/,/g,'').match(/\d+/);
    const product={product_id:String(p),name:uiText(read(p,'.StoreProduct','name')),
      description:uiText(read(p,'.StoreProduct','description')),price:match?Number(match[0]):null,price_text:priceText,
      stars:uiText(read(p,'.StoreProduct','star'))};
    return product;
  });
  return {products,money:gameInfo().progress?.money};
}
function buyProduct(r) {
  requireControl();if(purchaseReceipts.has(r.id))return purchaseReceipts.get(r.id);
  const p=present('.StoreProduct').find(p=>String(p)===r.product_id);
  if(!p)throw Error('Product is no longer displayed');
  const managers=present('.StoreMgr');if(managers.length!==1)throw Error('Native store unavailable');
  const before=gameInfo().progress.money,name=uiText(read(p,'.StoreProduct','name'));
  purchaseReceipts.set(r.id,{status:'unknown',purchase_id:r.id,name});
  const ok=call('.StoreMgr','$vX',managers[0],p),after=gameInfo().progress.money;
  const result={status:ok?'Committed':'rejected_by_game',purchase_id:r.id,name,money_before:before,money_after:after,spent:before-after};
  purchaseReceipts.set(r.id,result);return result;
}
const UI_CONTROL_TYPES={slider:'UnityEngine.UI.Slider',toggle:'UnityEngine.UI.Toggle',input:'TMPro.TMP_InputField',dropdown:'TMPro.TMP_Dropdown'};
function controlPath(p) {
  let t=call('UnityEngine.Component','get_transform',p),names=[];
  for(let i=0;i<8&&!t.isNull();i++){names.unshift(objectName(t));t=call('UnityEngine.Transform','get_parent',t);}
  return names.join('/');
}
function uiControls() {
  const controls=[];
  for(const [kind,full] of Object.entries(UI_CONTROL_TYPES)) {
    if(!PROFILE.classes[full])continue;
    for(const p of present(full)) {
      const value=kind==='input'?managedString(call(full,'get_text',p)):kind==='toggle'?!!call(full,'get_isOn',p):call(full,'get_value',p);
      const info={control_id:String(p),kind,name:objectName(p),value,path:controlPath(p),interactable:!!call('UnityEngine.UI.Selectable','IsInteractable',p)};
      if(kind==='slider'){info.minimum=call(full,'get_minValue',p);info.maximum=call(full,'get_maxValue',p);}
      controls.push(info);
    }
  }
  return {controls};
}
function setUiValue(r) {
  requireControl();const full=UI_CONTROL_TYPES[r.kind];if(!full)throw Error('Unknown UI control kind');
  const p=present(full).find(p=>String(p)===r.control_id);if(!p)throw Error('UI control is no longer active');
  if(!call('UnityEngine.UI.Selectable','IsInteractable',p))throw Error('Native UI control is disabled');
  if(r.kind==='input') {
    if(typeof r.value!=='string')throw Error('Text value required');
    call(full,'set_text',p,newString(r.value));
    if(PROFILE.classes[full].methods.some(m=>m.name==='SendOnEndEdit'&&!m.parameters.length))call(full,'SendOnEndEdit',p);
  } else if(r.kind==='toggle') {
    if(typeof r.value!=='boolean')throw Error('Boolean value required');call(full,'set_isOn',p,r.value);
  } else {
    if(typeof r.value!=='number'||!Number.isFinite(r.value)||(r.kind==='dropdown'&&!Number.isInteger(r.value)))throw Error('Numeric UI value required');
    call(full,'set_value',p,r.value);
  }
  return {status:'ui_value_set',control_id:r.control_id};
}
const damageHandlers=new Map();
function nativeDamage(p,amount) {
  const key=String(p.readPointer());let invoke=damageHandlers.get(key);
  if(!invoke){
    let k=p.readPointer();
    while(!k.isNull()&&!invoke){
      const it=Memory.alloc(8);it.writePointer(nil);
      for(let i=0;i<2000;i++){
        const m=classMethods(k,it);if(m.isNull())break;
        if(m.add(0x18).readPointer().readCString()==='$OgA'&&m.add(0x52).readU8()===1){
          const fn=native(m.readPointer(),'bool',['pointer','float','pointer']);invoke=(target,value)=>fn(target,value,m);break;
        }
      }
      k=k.add(0xa8).readPointer();
    }
    if(!invoke)throw Error('Native damage callback not present');damageHandlers.set(key,invoke);
  }
  return invoke(p,amount);
}
function testAssist(r) {
  const b=requireBattle(r);requirePhase(b,'Playing');
  const damage=[];
  const targets=list(read(b,'.Board','zombieArray')).filter(alive).map(p=>className(p)==='GameObject'?
    call('UnityEngine.GameObject','GetComponent',p,reflectionType('.Zombie')):p).filter(alive);
  if(r.scope!=='mobs')targets.push(...present('.BossPart'));
  const seen=new Set();
  for(const p of targets){
    const id=String(p),kind=className(p);if(seen.has(id)||kind==='PaladinGargantuar')continue;seen.add(id);
    if(r.scope==='mobs'&&/^(Dave|Boss)/.test(kind))continue;
    const before=read(p,'.BoardEntity','theHealth');if(before<=0||read(p,'.BoardEntity','dying'))continue;
    const health=PROFILE.classes['.BoardEntity'].fields.find(f=>f.name==='theHealth');
    p.add(health.offset).writeFloat(Math.min(1,before));nativeDamage(p,1000000);
    damage.push({entity_id:id,kind,health_before:before,health_after:alive(p)?read(p,'.BoardEntity','theHealth'):0});
  }
  let accelerated=false;
  const waves=read(b,'.Board','zombieWavesMgr');
  if(r.advance_waves&&!waves.isNull()&&!present('.BossBattleController').some(p=>alive(read(p,'.BossBattleController','$Yh'))||alive(read(p,'.BossBattleController','$zh')))){
    const timer=PROFILE.classes['.ZombieWavesMgr'].fields.find(f=>f.name==='mNextWavesTimer');
    waves.add(timer.offset).writeFloat(0);accelerated=true;
  }
  return {status:'test_assist_applied',cheat:true,damage,wave_accelerated:accelerated};
}
function storyDispatch(r) {
  switch(r.op) {
    case 'game_info':return gameInfo(r);
    case 'shovel':return shovelPlant(r);
    case 'move_plant':return movePlant(r);
    case 'interact':{
      const b=requireBattle(r);requirePhase(b,'Playing');requireEmptySelection();
      let point=null,plantTarget=null,row=r.row,column=r.column;
      if(r.entity_id){
        let p=nil;
        for(const [field,full] of [['plantArray','.Plant'],['zombieArray','.Zombie'],['gridItemArray','.GridItem'],['obstacleArray','.Obstacle']]) {
          for(let q of list(read(b,'.Board',field)).filter(alive)) {
            if(className(q)==='GameObject')q=call('UnityEngine.GameObject','GetComponent',q,reflectionType(full));
            if(alive(q)&&String(q)===r.entity_id){p=q;if(full==='.Plant')plantTarget=q;break;}
          }
          if(!p.isNull())break;
        }
        if(p.isNull())throw Error('Entity is no longer in the current battle');
        const cell=sourcePlantCell(p);row=cell.row;column=cell.column;point=positionOf(p);
      }
      if(typeof r.x==='number'&&Number.isFinite(r.x)&&typeof r.y==='number'&&Number.isFinite(r.y)){
        point=[r.x,r.y,0];plantTarget=null;row=Number.isInteger(row)?row:1;column=Number.isInteger(column)?column:1;
      }
      return atPointer(b,row,column,(m,project)=>{
        if(plantTarget)setPointer(plantPointer(plantTarget,m,project));
        const before=plantTarget?plantAbility(plantTarget):null;
        ownsSelection=true;call('.Mouse','$AP',m);
        if(plantTarget)clickPlantUpdate(plantTarget);
        return {status:'interaction_requested',ability_before:before,ability_after:plantTarget?plantAbility(plantTarget):null};
      },point);
    }
    case 'set_slow':return setSlow(r);
    case 'set_speed':return setSpeed(r);
    case 'set_paused':return setPaused(r);
    case 'set_difficulty':return setDifficulty(r);
    case 'rewards':return rewards();
    case 'collect_reward':return collectReward(r);
    case 'choose_event':return chooseEvent(r);
    case 'next_level':return nextLevel(r);
    case 'almanac':return almanac();
    case 'almanac_select':return almanacSelect(r);
    case 'store':return store();
    case 'buy':return buyProduct(r);
    case 'purchase_receipt':return r.purchase_id?(purchaseReceipts.get(r.purchase_id)||{status:'not_found'}):[...purchaseReceipts.values()].slice(-20);
    case 'ui_controls':return uiControls();
    case 'set_ui_value':return setUiValue(r);
    case 'test_assist':return testAssist(r);
    default:throw Error('Unsupported operation: '+r.op);
  }
}
