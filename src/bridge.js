'use strict';
// Injected into the pinned local game. All Unity calls run on GameAPP.Update.
const base = Process.getModuleByName('GameAssembly.dll').base;
let nativeExceptionReports=0;
if(typeof Process.setExceptionHandler==='function')Process.setExceptionHandler(details=>{
  if(nativeExceptionReports++<5)send({type:'native_exception',kind:details.type,address:String(details.address),memory:details.memory,
    trace:Thread.backtrace(details.context,Backtracer.ACCURATE).map(DebugSymbol.fromAddress).map(String)});
  return false;
});
// Preserve the engine's exception handling; filter destroyed scene objects
// before invoking Unity methods on the native lists that retain them.
function native(address, result, args) { return new NativeFunction(address, result, args, {exceptions:'propagate',traps:'all'}); }
const pinObject=native(base.add(0x2b2a90),'uint',['pointer','bool']);
const freeHandle=native(base.add(0x2b1fa0),'void',['uint']);
const typeHandles=[];
const nil = ptr(0), queue = [], bindings = new Map(), types = new Map(), classCache = new Map();
const assemblies = native(base.add(0x279200), 'pointer', []);
const classFromName = native(base.add(0x337600), 'pointer', ['pointer', 'pointer', 'pointer']);
const classMethods = native(base.add(0x2bb410), 'pointer', ['pointer', 'pointer']);
const classFields = native(base.add(0x2ba5a0), 'pointer', ['pointer', 'pointer']);
const classOfType = native(base.add(0x2b9550), 'pointer', ['pointer', 'bool']);
const allocateString = native(base.add(0x1043b00), 'pointer', ['int', 'pointer']);
const screenToWorld=native(base.add(0x498e40),['float','float','float'],[['float','float','float'],'pointer']);
let controlled = false, playerLocked = false, epoch = 1, boardKey = '', menuGeneration = 0;
let menuTargets = new Map(), lastMenu = '', autoCollect = false, stopping = false;
let pointerOverride = null, pointerThread = 0, collectAt = 0;
let pointerReads=0;
let pointerState=null;
function setPointer(point) {
  pointerOverride=point;pointerThread=Process.getCurrentThreadId();
  if(pointerState){
    pointerState.writeU32(0);pointerState.add(4).writeU32(pointerThread);
    for(let i=0;i<3;i++)pointerState.add(8+i*4).writeFloat(point[i]);
    pointerState.writeU32(1);
  }
}
function clearPointer() {
  if(pointerState){pointerState.writeU32(0);pointerState.add(24).writeU32(0);}
  pointerOverride=null;pointerThread=0;
}
let ownsSelection = false;
const enums = new Map();
function managedString(p) {
  if (p.isNull()) return null;
  const n = p.add(16).readS32();
  if (n < 0 || n > 200000) throw Error('Invalid managed string');
  return p.add(20).readUtf16String(n);
}
function newString(s) { const p = allocateString(s.length, nil); p.add(20).writeUtf16String(s); return p; }
function klass(full) {
  if (classCache.has(full)) return classCache.get(full);
  const split = full.lastIndexOf('.'), ns = full.slice(0, split), name = full.slice(split + 1);
  const v = assemblies(), a = v.readPointer(), count = v.add(8).readPointer().sub(a).toInt32() / 8;
  for (let i = 0; i < count; i++) {
    const image = a.add(i * 8).readPointer().readPointer();
    const k = classFromName(image, Memory.allocUtf8String(ns), Memory.allocUtf8String(name));
    if (!k.isNull()) { classCache.set(full, k); return k; }
  }
  throw Error('Class unavailable: ' + full);
}
function wireType(t) {
  if (t === 'Void') return 'void';
  if (t === 'Boolean') return 'bool';
  if (t === 'Single') return 'float';
  if (t === 'Int64') return 'int64';
  if (t === 'Vector2') return 'uint64'; // MS x64 passes an 8-byte value type in one integer register.
  if (t === 'Vector3') return ['float', 'float', 'float'];
  if (t === 'Int32' || t === 'KeyCode' || PROFILE.classes['.'+t]?.parent === 'Enum') return 'int';
  return 'pointer';
}
function bind(full, name, argc = 0) {
  const key = full + ':' + name + ':' + argc;
  if (bindings.has(key)) return bindings.get(key);
  const spec = PROFILE.classes[full].methods.find(m => m.name === name && m.parameters.length === argc &&
    (name !== 'StartCoroutine' || m.parameters[0] === 'IEnumerator'));
  if (!spec) throw Error('Unsupported method: ' + key);
  const k = klass(full), it = Memory.alloc(8); it.writePointer(nil);
  let info = nil;
  for (let i = 0; i < 4000; i++) {
    const m = classMethods(k, it); if (m.isNull()) break;
    if (m.add(0x18).readPointer().readCString() === name && m.add(0x52).readU8() === argc &&
        m.readPointer().equals(base.add(parseInt(spec.rva)))) { info = m; break; }
  }
  if (info.isNull() || !info.readPointer().equals(base.add(parseInt(spec.rva)))) throw Error('Binding mismatch: ' + key);
  const args = spec.parameters.map(wireType), isStatic = !!(spec.flags & 16);
  if (!isStatic) args.unshift('pointer');
  args.push('pointer');
  const fn = native(info.readPointer(), wireType(spec.returns), args);
  const result = (self, ...values) => {
    const wired=values.map((value,i)=>spec.parameters[i]==='Boolean'?(value?1:0):spec.parameters[i]==='Vector2'?packVector2(value):value);
    const result=fn(...(isStatic?wired:[self,...wired]),info);
    return spec.returns==='Vector2'?unpackVector2(result):result;
  };
  bindings.set(key, result); return result;
}
function call(full, name, self, ...args) { return bind(full, name, args.length)(self, ...args); }
function packVector2(value) {
  const buffer=new ArrayBuffer(8),floats=new Float32Array(buffer),words=new Uint32Array(buffer);
  floats[0]=value[0];floats[1]=value[1];
  return uint64('0x'+words[1].toString(16).padStart(8,'0')+words[0].toString(16).padStart(8,'0'));
}
function unpackVector2(value) {
  const hex=value.toString(16).padStart(16,'0'),buffer=new ArrayBuffer(8),words=new Uint32Array(buffer);
  words[0]=parseInt(hex.slice(8),16);words[1]=parseInt(hex.slice(0,8),16);
  return Array.from(new Float32Array(buffer));
}
function pointerProjector(convert=screenToWorld) {
  const p=convert([0,0,0],nil),x=convert([100,0,0],nil),y=convert([0,100,0],nil);
  const a=(x[0]-p[0])/100,b=(y[0]-p[0])/100,c=(x[1]-p[1])/100,d=(y[1]-p[1])/100,det=a*d-b*c;
  if(!Number.isFinite(det)||Math.abs(det)<1e-12)throw Error('Native pointer projection unavailable during transition');
  return (worldX,worldY)=>[(d*(worldX-p[0])-b*(worldY-p[1]))/det,(-c*(worldX-p[0])+a*(worldY-p[1]))/det,0];
}
function boardPoint(b,x,y,toWorld=true) {
  const transform=call('UnityEngine.Component','get_transform',b);
  return call('UnityEngine.Transform',toWorld?'TransformPoint':'InverseTransformPoint',transform,[x,y,0]);
}
function reflectionType(full) {
  if (!types.has(full)) {
    const k = klass(full), assembly = k.readPointer().add(8).readPointer().readCString();
    const t = call('System.Type', 'GetType', nil, newString(full.slice(full[0] === '.' ? 1 : 0) + ', ' + assembly));
    if (t.isNull()) throw Error('Reflection type unavailable: ' + full);
    typeHandles.push(pinObject(t,1));
    types.set(full, t);
  }
  return types.get(full);
}
function objects(full) {
  const a = call('UnityEngine.Object', 'FindObjectsOfType', nil, reflectionType(full), 0);
  return array(a);
}
function enumMap(full) {
  if (!enums.has(full)) {
    const t = reflectionType(full), names = array(call('System.Enum', 'GetNames', nil, t));
    const values = call('System.Enum', 'GetValues', nil, t), result = {};
    for (let i = 0; i < names.length; i++) result[values.add(32 + i * 4).readS32()] = managedString(names[i]);
    enums.set(full, result);
  }
  return enums.get(full);
}
function enumName(full, value) { return enumMap(full)[value] || 'unknown:' + value; }
function array(a) {
  if (a.isNull()) return [];
  const n = a.add(24).readU32(); if (n > 100000) throw Error('Invalid native array');
  return Array.from({ length: n }, (_, i) => a.add(32 + i * 8).readPointer()).filter(p => !p.isNull());
}
function list(p) {
  if(p.isNull())return [];
  const a=p.add(16).readPointer(),n=p.add(24).readS32();
  if(a.isNull())return [];
  if(n<0||n>a.add(24).readU32())throw Error('Invalid native list size');
  return Array.from({length:n},(_,i)=>a.add(32+i*8).readPointer()).filter(p=>!p.isNull());
}
function singleton(full, offset = 0) {
  const storage=klass(full).add(0xb8).readPointer();
  return storage.isNull()?nil:storage.add(offset).readPointer();
}
function className(p) { return p.readPointer().add(0x98).readPointer().readCString(); }
function objectName(p) { return managedString(call('UnityEngine.Object', 'get_name', p)); }
function alive(p) { return !p.isNull()&&!p.add(16).readPointer().isNull(); }
function componentGameObject(p) { return call('UnityEngine.Component', 'get_gameObject', p); }
function active(p) { return alive(p)&&!!call('UnityEngine.GameObject', 'get_activeInHierarchy', componentGameObject(p)); }
function read(p, full, name) {
  const f = PROFILE.classes[full].fields.find(f => f.name === name);
  if (!f) throw Error('Unknown field ' + full + '.' + name);
  const q = p.add(f.offset);
  if (f.type === 'Boolean') return !!q.readU8();
  if (f.type === 'Single') return q.readFloat();
  if (f.type === 'Int32' || f.type === 'KeyCode' || PROFILE.classes['.'+f.type]?.parent === 'Enum') return q.readS32();
  if (f.type === 'String') return managedString(q.readPointer());
  return q.readPointer();
}
function getBoard() {
  let p = singleton('.Board'); if(!p.isNull()&&!alive(p))p=nil;
  const key = p.toString();
  if (key !== boardKey) { boardKey = key; epoch++; autoCollect = false; }
  return p;
}
function battleId() { return SESSION + ':' + epoch; }
function card(p) {
  return { card_id: p.toString(), name: objectName(p), plant_type: read(p, '.CardUI', 'thePlantType'),
    plant_name: enumName('.$xB', read(p, '.CardUI', 'thePlantType')),
    cost: read(p, '.CardUI', 'theSeedCost'), cooldown: Math.max(0,read(p, '.CardUI', 'fullCD')-read(p, '.CardUI', 'CD')),
    native_cooldown_elapsed: read(p, '.CardUI', 'CD'),
    full_cooldown: read(p, '.CardUI', 'fullCD'), selected: read(p, '.CardUI', 'isSelected'),
    available: read(p, '.CardUI', 'isAvailable'), disabled: read(p, '.CardUI', 'disabled'),
    on_bank: read(p, '.CardUI', 'onCardBank'), slot: read(p, '.CardUI', 'theNumberInCardSort') };
}
function entity(p, full) {
  if (className(p) === 'GameObject') p = call('UnityEngine.GameObject', 'GetComponent', p, reflectionType(full));
  if(!alive(p))return null;
  const transform=call('UnityEngine.Component','get_transform',p), position=call('UnityEngine.Transform','get_position',transform);
  const nativeColumn=read(p, '.BoardEntity', 'theColumn') + 1;
  const board=read(p,'.BoardEntity','board');
  const firstX=board.isNull()?0:board.add(240).readFloat()+board.add(224).readFloat();
  const columnWidth=board.isNull()?1:board.add(248).readFloat();
  const local=full==='.Zombie'&&!board.isNull()?boardPoint(board,position[0],position[1],false):position;
  return { entity_id: p.toString(), kind: className(p), row: read(p, '.BoardEntity', 'theRow') + 1,
    column: full === '.Zombie' ? Math.floor((local[0]-firstX)/columnWidth+0.5)+1 : nativeColumn,
    x:position[0],y:position[1],health: read(p, '.BoardEntity', 'theHealth'),
    max_health: read(p, '.BoardEntity', 'theMaxHealth'), dying: read(p, '.BoardEntity', 'dying'),
    content_type: read(p, full, 'theType'), preview: full === '.Zombie' && read(p,'.Zombie','isPreview'),
    ...(full==='.Plant'?{is_gray:read(p,'.Plant','isGray'),ability:plantAbility(p)}:{} ) };
}
// Same read-only plant predicate used by CoinSun.$RO for blood-sun damage.
// It accounts for native collider distance/eligibility without a guessed radius.
function sunThreats(p, plants) {
  return plants.filter(plant=>alive(plant)&&!read(plant,'.BoardEntity','dying')&&
    call('.CoinSun','$tO',p,plant));
}
function sunSnapshot(p, plants) {
  const position=call('UnityEngine.Transform','get_position',call('UnityEngine.Component','get_transform',p));
  const kind=enumName('.$TB',read(p,'.Item','theItemType'));
  return {sun_id:p.toString(),value:read(p,'.Item','value'),kind,x:position[0],y:position[1],
    ...(['BloodSun','SmallBloodSun'].includes(kind)?{threatened_plant_ids:sunThreats(p,plants).map(String)}:{})};
}
function observe() {
  const b = getBoard();
  const state = { game: 'PVZ-Scared', bridge_version: '0.2.2', battle_id: b.isNull() ? null : battleId(),
    controlled, player_locked: playerLocked, held_os_inputs: 0, native_selection: selection(),
    phase: 'menu', captured_at_unix_ms: Date.now(), auto_collect: autoCollect, native_pointer_reads:pointerState?pointerState.add(20).readU32():pointerReads };
  if (b.isNull()) return state;
  const waveManager=read(b,'.Board','zombieWavesMgr');
  const plants=list(read(b,'.Board','plantArray')).filter(alive);
  const status = read(b, '.Board', 'theBoardStatus'), statusName = enumName('.$QB', status);
  Object.assign(state, { phase: ({Moving:'moving', Selecting:'selection', Playing:'running', Pause:'paused', PauseWhenSelecting:'selection_paused', Lose:'defeat'})[statusName] || 'unknown',
    native_board_status: status, sun: read(b, '.Board', 'theSun'),
    wave:waveManager.isNull()?null:read(waveManager,'.ZombieWavesMgr','mCurrentWaves'),
    max_wave:waveManager.isNull()?null:read(waveManager,'.ZombieWavesMgr','mTotalWaves'),
    rows: read(b, '.Board', 'rowNum'), columns: read(b, '.Board', 'columnNum'),
    plants: plants.map(p => entity(p, '.Plant')).filter(Boolean),
    zombies: list(read(b, '.Board', 'zombieArray')).filter(alive).map(p => entity(p, '.Zombie')).filter(z=>z&&!z.preview),
    cards: objects('.CardUI').map(card),
    suns: collectibles().map(p => sunSnapshot(p,plants)) });
  const storage=klass('.GameAPP').add(0xb8).readPointer();
  state.allies=state.zombies.filter(z=>z.kind==='PaladinGargantuar');
  state.zombies=state.zombies.filter(z=>z.kind!=='PaladinGargantuar');
  state.menu_state=enumName('.$sB',read(storage,'.GameAPP','$sK'));
  if(state.menu_state==='Victory')state.phase='victory';
  if(diaryOpen(b))state.phase='diary';
  return state;
}
function diaryOpen(b) {
  if(b.isNull())return false;
  const diary=read(b,'.Board','diary');if(diary.isNull())return false;
  const panel=read(diary,'.DiaryController','$QJ');
  return !panel.isNull()&&call('UnityEngine.GameObject','get_activeInHierarchy',panel);
}
function selection() {
  const m = singleton('.Mouse');
  if (m.isNull()) return 0;
  const raw = read(m, '.Mouse', 'mouseItemType');
  return enumName('.$uB', raw) === 'Nothing' ? 0 : raw;
}
function releaseSelection() {
  if (!ownsSelection) return;
  const m = singleton('.Mouse');
  if (!m.isNull() && selection() !== 0) call('.Mouse', '$jP', m);
  if (selection() !== 0) throw Error('Native selection release not confirmed');
  ownsSelection = false;
}
function collectibles() {
  return objects('.CoinSun').filter(p => !read(p, '.Item', 'dying') && !read(p, '.Item', '$ol') && !read(p, '.CoinSun', '$jl'));
}
function menu() {
  menuTargets = new Map(); menuGeneration++;
  lastMenu = SESSION + ':menu:' + menuGeneration;
  const actions = [];
  function add(p, kind, label, extra = {}) {
    const id = String(actions.length + 1); menuTargets.set(id, { p, kind, ...extra });
    actions.push({ action_id: id, kind, label, ...extra });
  }
  for (const p of objects('.PreGameWarningController')) if(read(p,'.PreGameWarningController','$Kv')&&!read(p,'.PreGameWarningController','$Lv')) add(p, 'continue_notice', '继续游戏公告');
  const dialogs = objects('.Dialog');
  const profileDialog = dialogs.length === 1 && managedString(call('TMPro.TMP_Text', 'get_text', read(dialogs[0], '.Dialog', 'Header'))) === '新用户';
  const productButtons = new Set(present('.StoreProduct').map(p=>String(read(p,'.StoreProduct','$Ex'))));
  for (const p of objects('.UIButtonBase')) {
    const cls = className(p), enabled = read(p, '.UIButtonBase', 'interactable');
    const name = objectName(p);
    if (!enabled || /UserMgr/.test(cls) || /SaveManager|Delete|Buy|Purchase/.test(name) || excludedMode(name) || productButtons.has(String(p))) continue;
    if (dialogs.length && cls !== 'DialogBtn') continue;
    const detail={native_class:cls};
    if(cls==='LevelChooseButton')detail.level=read(p,'.LevelChooseButton','$sm');
    if(cls==='MapChooseButton')detail.chapter=read(p,'.MapChooseButton','$um');
    add(p, profileDialog ? 'create_profile' : 'game_button', name, detail);
  }
  if (!dialogs.length) {
    for (const p of objects('UnityEngine.UI.Button')) if (!/Buy|Purchase|Delete/.test(objectName(p))&&!excludedMode(objectName(p))&&!storeAncestor(p)&&call('UnityEngine.UI.Selectable','IsInteractable',p)) add(p, 'ui_button', objectName(p));
    if(!diaryOpen(getBoard()))for (const p of objects('.StartButton')) add(p, 'start_battle', objectName(p));
    for (const p of objects('.InGameBtn')) if (/menu/i.test(objectName(p))) add(p,'in_game_menu',objectName(p));
  }
  const texts = objects('TMPro.TMP_Text').map(p => ({ name: objectName(p), text: managedString(call('TMPro.TMP_Text', 'get_text', p)) }));
  return { menu_id: lastMenu, actions, texts, state: observe() };
}
function requireControl() { if (!controlled || playerLocked) throw Error('AI does not own control; F10 re-enables after player stop'); }
function clickNative(full, p) {
  if (full === '.UIButtonBase') {
    // These are the same virtual gate and click callback used by OnMouseUp.
    // Programmatic activation does not need hover/press visual state.
    const k=p.readPointer(), gate=k.add(0x1d8).readPointer(), gateInfo=k.add(0x1e0).readPointer();
    const callback=k.add(0x2b8).readPointer(), callbackInfo=k.add(0x2c0).readPointer();
    if (gateInfo.add(0x18).readPointer().readCString() !== '$kJA' || callbackInfo.add(0x18).readPointer().readCString() !== '$lJA') throw Error('Native button slot mismatch');
    if (!native(gate,'bool',['pointer','pointer'])(p,gateInfo)) throw Error('Native button gate refused');
    native(callback,'void',['pointer','pointer'])(p,callbackInfo);
    return;
  }
  call(full,'OnMouseEnter',p);
  try { call(full,'OnMouseDown',p); call(full,'OnMouseUp',p); }
  finally { call(full,'OnMouseExit',p); }
}
function requireBattle(r) {
  requireControl(); const b = getBoard();
  if (b.isNull() || r.battle_id !== battleId()) throw Error('Stale battle_id');
  return b;
}
function requirePhase(b, expected) {
  if (enumName('.$QB', read(b, '.Board', 'theBoardStatus')) !== expected) throw Error('Native battle phase does not allow this action');
}
function selectCard(r) {
  const b = requireBattle(r); requirePhase(b, 'Selecting');
  const p = objects('.CardUI').find(p => p.toString() === r.card_id);
  if (!p) throw Error('Card is no longer a selection candidate');
  const before = card(p), desired = r.selected !== false;
  if (before.selected !== desired) call('.CardUI', 'OnMouseDown', p);
  const after = card(p);
  return { status: after.selected === desired ? 'confirmed' : 'rejected_by_game', card: after };
}
function plant(r) {
  if (typeof r.card_id === 'string' && /^(drop|belt):/.test(r.card_id)) return plantSpecial(r);
  const b = requireBattle(r); requirePhase(b, 'Playing');
  if (!Number.isInteger(r.row) || !Number.isInteger(r.column) || r.row < 1 || r.column < 1 ||
      r.row > read(b,'.Board','rowNum') || r.column > read(b,'.Board','columnNum')) throw Error('Cell outside native board');
  const p = objects('.CardUI').find(p => p.toString() === r.card_id && read(p,'.CardUI','onCardBank'));
  if (!p) throw Error('Card is not in the current bank');
  const c = card(p), sun = read(b,'.Board','theSun');
  if (c.disabled || !c.available || c.cooldown > 0 || sun < c.cost) return { status: 'rejected', reason: 'native_card_not_ready', card: c, sun };
  if (selection() !== 0) throw Error('Native selection is already in use');
  const m = singleton('.Mouse'), oldGrid = m.add(32).readByteArray(16), oldPosition = m.add(108).readByteArray(16);
  const x = call('.Board','$DA',b,r.column-1), y = call('.Board','$eA',b,r.row-1);
  const world=boardPoint(b,x,y),point = pointerProjector()(world[0],world[1]);
  const before = new Set(list(read(b,'.Board','plantArray')).map(String));
  try {
    setPointer(point);
    ownsSelection = true;
    call('.Mouse','$GP',m,p);
    if (read(m,'.Mouse','theCardOnMouse').isNull() || !read(m,'.Mouse','theCardOnMouse').equals(p)) return {status:'rejected',reason:'native_selection_refused'};
    m.add(32).writeS32(r.row-1); m.add(36).writeS32(r.column-1);
    m.add(40).writeFloat(x); m.add(44).writeFloat(y);
    m.add(108).writeFloat(point[0]); m.add(112).writeFloat(point[1]);
    m.add(116).writeFloat(x); m.add(120).writeFloat(y);
    call('.Mouse','$kP',m);
    const created = list(read(b,'.Board','plantArray')).filter(p => alive(p)&&!before.has(p.toString())).map(p => entity(p,'.Plant')).filter(Boolean);
    const exact = created.filter(p => p.row === r.row && p.column === r.column && p.content_type === c.plant_type);
    return { status: exact.length ? 'Committed' : 'rejected_by_game', plants: created, sun_before: sun,
      sun_after: read(b,'.Board','theSun'), card: card(p), selection_released: true };
  } finally {
    clearPointer();
    try { m.add(32).writeByteArray(oldGrid); m.add(108).writeByteArray(oldPosition); }
    finally { releaseSelection(); }
  }
}
function dispatch(r) {
  switch (r.op) {
    case 'capabilities': return { game: 'PVZ-Scared', game_version: '1.0.1', bridge_version: '0.2.2',
      mode: 'realtime', engine: 'Unity IL2CPP', operations: ['observe', 'menu', 'attach', 'detach', 'stop', 'menu_action', 'choose_card', 'start_battle', 'plant', 'collect', 'auto_collect', ...STORY_OPERATIONS],
      supported_modes: ['story'], excluded_modes: ['survival','entertainment'],
      sun_hazards: 'world-position-native-plant-filter-v1',
      no_ocr: true, no_os_input: true, costs_and_cooldowns: 'native', emergency_keys: { F8: 'stop', F9: 'release', F10: 'allow control' } };
    case 'observe': return storyObservation(observe());
    case 'menu': return menu();
    case 'attach':
      if (playerLocked) throw Error('Player stop lock; press F10 in game');
      if (ownsSelection) throw Error('Previous native selection is not released; detach before taking control');
      controlled = true; return observe();
    case 'detach': case 'stop': {
      clearPointer();controlled = false; autoCollect = false; menuTargets.clear(); lastMenu = ''; releaseSelection();
      return { controlled, auto_collect: autoCollect, held_os_inputs: 0,
        native_selection: selection(), selection_released: !ownsSelection,native_click_active:false };
    }
    case 'choose_card': return selectCard(r);
    case 'plant': return plant(r);
    case 'start_battle': {
      const b = requireBattle(r); requirePhase(b,'Selecting');
      const targets = objects('.StartButton'); if (targets.length !== 1) throw Error('Native start target unavailable');
      clickNative('.StartButton',targets[0]);
      return {status:'start_requested'};
    }
    case 'collect': {
      const b = requireBattle(r); requirePhase(b,'Playing');
      if (!Array.isArray(r.sun_ids) || r.sun_ids.length > 128) throw Error('Invalid collectible IDs');
      const wanted = new Set(r.sun_ids), skipped=[];
      const items = collectibles().filter(p=>{
        if(!wanted.has(p.toString()))return false;
        const kind=enumName('.$TB',read(p,'.Item','theItemType'));
        if(!['BloodSun','SmallBloodSun'].includes(kind))return true;
        // Recheck the condition on the game thread: a glove move or transition
        // since observation must not turn a scoped request into a broad pickup.
        const allowed=r.red_sun_policy==='level40-near-plant'&&gameInfo().progress?.level===40&&
          sunThreats(p,list(read(b,'.Board','plantArray'))).length>0;
        if(!allowed)skipped.push(p.toString());
        return allowed;
      });
      for (const p of items) call('.CoinSun','$cJA',p,0);
      return { status:'collection_requested', count:items.length, skipped_sun_ids:skipped, sun_before_animation:read(b,'.Board','theSun') };
    }
    case 'auto_collect': { const b=requireBattle(r); requirePhase(b,'Playing'); autoCollect=r.enabled===true; return {enabled:autoCollect}; }
    case 'menu_action': {
      requireControl(); if (r.menu_id !== lastMenu) throw Error('Stale menu_id');
      const t = menuTargets.get(String(r.action_id)); if (!t || !active(t.p)) throw Error('Target no longer active');
      menuTargets.clear(); lastMenu = '';
      if (t.kind === 'continue_notice') {
        if (!read(t.p, '.PreGameWarningController', '$Kv') || read(t.p, '.PreGameWarningController', '$Lv')) throw Error('Notice transition not ready');
        const routine = call('.PreGameWarningController', '$GmA', t.p);
        call('UnityEngine.MonoBehaviour', 'StartCoroutine', t.p, routine);
      }
      else if (t.kind === 'game_button' || t.kind === 'create_profile') {
        if (t.kind === 'create_profile') {
          const inputs=objects('TMPro.TMP_InputField'), name=r.name || 'PvZ-AI-Horror';
          if (inputs.length !== 1 || !/^[A-Za-z0-9_-]{1,24}$/.test(name)) throw Error('Native new-profile input unavailable or invalid name');
          call('TMPro.TMP_InputField','set_text',inputs[0],newString(name));
        }
        clickNative('.UIButtonBase',t.p);
      }
      else if (t.kind === 'start_battle') clickNative('.StartButton',t.p);
      else if (t.kind === 'in_game_menu') {
        call('.InGameBtn','OnMouseEnter',t.p);
        try { call('.InGameBtn','OnMouseDown',t.p); call('.InGameBtn','OnMouseUpAsButton',t.p); }
        finally { call('.InGameBtn','OnMouseExit',t.p); }
      }
      else call('UnityEngine.UI.Button', 'Press', t.p);
      return { status: 'navigation_requested' };
    }
    default: return storyDispatch(r);
  }
}
function stopByPlayer() { playerLocked = true; controlled = false; autoCollect = false; releaseSelection(); }
// Scope native pointer position to the one action and game thread. Never sends OS input.
// A JS listener is suppressed on nested native calls from the Update listener.
// A native fast replacement keeps the override scoped without re-entering JS.
let pointerHook;
if(typeof CModule==='function') {
  pointerState=Memory.alloc(32);pointerState.writeByteArray(new Uint8Array(32));
  const originalSlot=Memory.alloc(8),buttonSlot=Memory.alloc(8);originalSlot.writePointer(nil);buttonSlot.writePointer(nil);
  const module=new CModule(`
    typedef struct {float x,y,z;} Vec3;
    typedef Vec3 *(*Getter)(Vec3 *,void *);
    extern unsigned int pointer_data[];
    extern void *original_entry;
    extern void *original_button;
    extern unsigned int thread_id(void);
    Vec3 *read_pointer(Vec3 *out,void *info) {
      if(pointer_data[0] && pointer_data[1]==thread_id()) {
        float *values=(float *)(pointer_data+2);
        out->x=values[0];out->y=values[1];out->z=values[2];pointer_data[5]++;
        return out;
      }
      Getter original=(Getter)original_entry;
      if(original)return original(out,info);
      out->x=out->y=out->z=0;return out;
    }
    unsigned char read_button(int button,void *info) {
      if(pointer_data[0] && pointer_data[1]==thread_id() && pointer_data[6])return button==0;
      if(original_button)return ((unsigned char (*)(int,void *))original_button)(button,info);
      return 0;
    }
  `,{pointer_data:pointerState,original_entry:originalSlot,original_button:buttonSlot,
    thread_id:Process.getModuleByName('kernel32.dll').getExportByName('GetCurrentThreadId')});
  const address=base.add(0x1db3240);
  originalSlot.writePointer(Interceptor.replaceFast(address,module.read_pointer));
  const buttonAddress=base.add(0x1db2f90);
  buttonSlot.writePointer(Interceptor.replaceFast(buttonAddress,module.read_button));
  Interceptor.flush();
  pointerHook={module,detach(){clearPointer();Interceptor.revert(address);Interceptor.revert(buttonAddress);Interceptor.flush();}};
} else pointerHook=Interceptor.attach(base.add(0x1db3240),{
  onEnter(args){this.output=args[0];this.override=pointerOverride&&pointerThread===Process.getCurrentThreadId()?pointerOverride:null;},
  onLeave(){if(this.override){pointerReads++;for(let i=0;i<3;i++)this.output.add(i*4).writeFloat(this.override[i]);}}
});
const boardAwake=Interceptor.attach(base.add(0x3a3a30),{onEnter(args){
  epoch++;boardKey=args[0].toString();autoCollect=false;menuTargets.clear();lastMenu='';
}});
const boardDestroy=Interceptor.attach(base.add(0x3a3ea0),{onEnter(){
  epoch++;boardKey='';autoCollect=false;menuTargets.clear();lastMenu='';ownsSelection=false;
}});
const update = Interceptor.attach(base.add(0x41e520), { onEnter() {
  if (stopping) return;

  try {
    if (call('UnityEngine.Input', 'GetKeyDown', nil, 289) || call('UnityEngine.Input', 'GetKeyDown', nil, 290)) stopByPlayer();
    if (call('UnityEngine.Input', 'GetKeyDown', nil, 291)) playerLocked = false;
    if (autoCollect && controlled && Date.now() >= collectAt) {
      collectAt=Date.now()+100;const b=getBoard();
      if(!b.isNull()&&enumName('.$QB',read(b,'.Board','theBoardStatus'))==='Playing') {
        for(const p of collectibles()) if(/sun/i.test(enumName('.$TB',read(p,'.Item','theItemType')))) call('.CoinSun','$cJA',p,0);
      }
    }
    const job = queue.shift(); if (!job) return;
    if (job.cancelled) return;
    try { job.resolve({ ok: true, result: dispatch(job.request) }); }
    catch (e) { send({type:'action_error',op:job.request.op,error:String(e.stack),native_pointer_reads:pointerReads});job.resolve({ ok: false, error: String(e.message || e) }); }
  } catch (e) { send({ type: 'bridge_error', error: String(e.stack) }); }

} });
function enqueue(request, complete = result => result) {
  return new Promise(resolve => {
    let timer;
    const job = { request, cancelled: false, resolve(result) {
      clearTimeout(timer);
      try { resolve(complete(result)); }
      catch(e) { resolve({ok:false,error:String(e.message || e)}); }
    } };
    queue.push(job);
    timer = setTimeout(() => {
      const index = queue.indexOf(job);
      if (index !== -1) {
        job.cancelled = true; queue.splice(index, 1);
        resolve({ok:false,error:'Main thread unavailable; request cancelled before execution'});
      }
    }, 8000);
  });
}
rpc.exports = {
  request(request) { return enqueue(request); },
  dispose() { return enqueue({op:'detach'}, result => {
    if (!result.ok || result.result.selection_released !== true) return result;
    stopping = true;
    for(const h of typeHandles) freeHandle(h);
    typeHandles.length = 0;
    update.detach(); pointerHook.detach(); boardAwake.detach(); boardDestroy.detach();
    return result;
  }); }
};
