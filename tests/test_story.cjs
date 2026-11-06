const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
function environment() {
  const pointer=n=>({add:v=>pointer(n+v),isNull:()=>n===0,toString:()=>String(n)});
  const context=vm.createContext({PROFILE:{classes:{}},SESSION:'story-test',Process:{getModuleByName:()=>({base:pointer(100)}),getCurrentThreadId:()=>1},
    NativeFunction:function(){return ()=>{};},ptr:pointer,Interceptor:{attach:()=>({detach(){}})},rpc:{},send(){},setTimeout(){},clearTimeout(){}});
  vm.runInContext(['bridge.js','story.js'].map(name=>fs.readFileSync(path.join(__dirname,'../src',name),'utf8')).join('\n'),context);
  return code=>vm.runInContext(code,context);
}
const run=environment();
const projection=run('pointerProjector(p=>[5+0.02*p[0]+0.005*p[1],-3+0.002*p[0]+0.01*p[1],0])');
const screen=projection(12,4);
assert.ok(Math.abs((5+0.02*screen[0]+0.005*screen[1])-12)<1e-6);
assert.ok(Math.abs((-3+0.002*screen[0]+0.01*screen[1])-4)<1e-6);
assert.throws(()=>run('pointerProjector(()=>[0,0,0])'),/projection unavailable/);
// Native list capacity can retain stale entries after scene changes. Count must
// be applied before null slots are removed.
const listRun=environment();
listRun(`
  const entry=n=>({isNull:()=>n===0,toString:()=>String(n)});
  const slots=[entry(7),entry(0),entry(99)];
  const backing={isNull:()=>false,add:offset=>({readU32:()=>3,readPointer:()=>slots[(offset-32)/8]})};
  const nativeList={isNull:()=>false,add:offset=>({readPointer:()=>backing,readS32:()=>2})};
`);
assert.equal(listRun('list(nativeList).map(String).join(",")'),'7');

// Board coordinates are local; a translated board must still target the
// intended world cell while retaining local grid fields for native placement.
const cellRun=environment();
cellRun(`
  const fakeCard={toString:()=> 'card'},fakeBoard={},fakeTransform={};
  const values=new Map();let clicked=null;
  const fakeMouse={add:offset=>({readByteArray:()=>[],writeByteArray(){},writeS32:v=>values.set(offset,v),writeFloat:v=>values.set(offset,v)})};
  requireBattle=()=>fakeBoard;requirePhase=()=>{};selection=()=>0;releaseSelection=()=>{ownsSelection=false;};
  singleton=()=>fakeMouse;objects=()=>[fakeCard];list=()=>[];
  pointerProjector=()=> (x,y)=>[x,y,0];
  card=()=>({cost:0,cooldown:0,available:true,disabled:false,plant_type:0});
  read=(p,full,name)=>name==='rowNum'||name==='columnNum'?9:name==='onCardBank'?true:
    name==='theCardOnMouse'?{isNull:()=>false,equals:q=>q===fakeCard}:0;
  call=(full,name,self,...args)=>{
    if(name==='get_transform')return fakeTransform;
    if(name==='TransformPoint')return [args[0][0]+3,args[0][1]+4,0];
    if(name==='InverseTransformPoint')return [args[0][0]-3,args[0][1]-4,0];
    if(name==='$DA')return -8;
    if(name==='$eA')return -1;
    if(name==='$kP')clicked=[...pointerOverride];
  };
  plant({battle_id:'battle',card_id:'card',row:1,column:1});
`);
assert.equal(cellRun('clicked.join(",")'),'-5,3,0');
assert.equal(cellRun('values.get(40)'),-8);
assert.equal(cellRun('values.get(44)'),-1);
assert.equal(cellRun('pointerOverride'),null);
assert.equal(cellRun('boardPoint(fakeBoard,-5,3,false).join(",")'),'-8,-1,0');
const rewardRun=environment();
rewardRun(`
  controlled=true;
  const reward={toString:()=> 'reward'},collectedReward={toString:()=> 'collected'},event={toString:()=> 'event',add:()=>({readS32:()=>0})};
  const eventButton={isNull:()=>false};let presses=0;
  getBoard=()=>({isNull:()=>true});gameInfo=()=>({});requireBattle=()=>({});
  present=full=>full==='.WinItem'?[reward,collectedReward]:full==='.EventCard'?[event]:[];
  read=(p,full,name)=>name==='$ol'?p===collectedReward:name==='$WM'?true:name==='dying'?true:0;
  className=()=> 'MoneyBag';enumName=()=> 'Native';uiText=()=> 'Event';componentGameObject=()=>({});reflectionType=()=>({});
  call=(full,name,self)=>{
    if(name==='GetComponent')return eventButton;
    if(name==='Press'){assertButton=self;presses++;return;}
    throw Error('Unexpected private event callback '+name);
  };
  let assertButton=null;
`);
assert.equal(rewardRun('rewards().items.map(i=>i.reward_id).join(",")'),'reward','A dying but uncollected native win item remains collectible');
assert.equal(rewardRun('rewards().events[0].revealed'),false,'Animation lock is not the reveal state');
assert.equal(rewardRun('rewards().events[0].animating'),true);
rewardRun("chooseEvent({battle_id:'battle',event_id:'event'})");
assert.equal(rewardRun('presses'),1);
assert.equal(rewardRun('assertButton===eventButton'),true);
const bossRun=environment();
bossRun(`
  const controller={},dead={},arena={toString:()=> 'arena'},head={toString:()=> 'head'},hand={toString:()=> 'hand'};
  let liveArena=true;
  alive=p=>p===head||p===hand||p===arena&&liveArena;
  className=p=>p===head?'DaveHead':'DaveHand';positionOf=()=>[1,2,0];
  read=(p,full,name)=>{
    if(p===controller)return name==='$Yh'?dead:arena;
    if(p===arena)return name==='$ke'?head:name==='$Ke'?hand:2.5;
    if(name==='theHealth')return p===head?1200:-1;
    if(name==='theMaxHealth')return 2000;
    if(name==='dying')return p===hand;
  };
`);
assert.equal(bossRun('bossInfo(controller).active'),true,'A live second form remains visible after the first form is destroyed');
assert.equal(bossRun('bossInfo(controller).health'),1200);
assert.equal(bossRun('bossInfo(controller).parts.length'),2);
assert.equal(bossRun('bossInfo(controller).arena.head_attack_countdown'),2.5);
bossRun('liveArena=false');
assert.equal(bossRun('bossInfo(controller).active'),false);
const clickRun=environment();
clickRun(`
  const clickValues=new Map();
  pointerState={add:offset=>({writeU32:v=>clickValues.set(offset,v)})};
  const clickable={readPointer:()=>({toString:()=> 'clickable'})};
  plantUpdates.set('clickable',()=>{if(clickValues.get(24)!==1)throw Error('missing native down');throw Error('native callback failed');});
`);
assert.throws(()=>clickRun('clickPlantUpdate(clickable)'),/native callback failed/);
assert.equal(clickRun('clickValues.get(24)'),0,'A thrown plant callback releases the scoped native mouse-down');
assert.equal(run("excludedMode('HappyMode')"),true);
assert.equal(run("excludedMode('SurvivalMode')"),true);
assert.equal(run("excludedMode('StoryMode')"),false);
run(`
  controlled=true;
  const product={toString:()=> 'product'},manager={},difficultyMenu={},sliderManager={};
  let money=300,preset='easy',speed=1,nativeBuys=0,throwPurchase=false,nightmareCalls=0;
  present=full=>({'.StoreProduct':[product],'.StoreMgr':[manager],'.DifficultyControlMenu':[difficultyMenu],'.SliderMgr':[sliderManager],'.Dialog':[{}],'UnityEngine.UI.Slider':[{}]})[full]||[];
  gameInfo=()=>({progress:{money,level:1},settings:{difficulty:preset,game_speed:speed,nightmare_unlocked:false}});
  uiText=p=>p==='speed-header'?'速度调节':'Native product';read=(p,full,name)=>name==='Header'?'speed-header':{};objectName=()=> 'Speed';
  matchingButton=()=>({});clickNative=()=>{};
  controlPath=()=> 'Canvas/SpeedDialog/Slider';
  call=(full,name,p,...args)=>{
    if(name==='$vX'){nativeBuys++;if(throwPurchase)throw Error('lost native result');if(money<100)return false;money-=100;return true;}
    if(name==='$ilA'){nightmareCalls++;return;}
    if(name==='$Ow')preset='normal';
    if(name==='set_value')speed=[0.5,1,1.5,2,3][Math.max(0,Math.min(4,args[0]))];
  };
`);
assert.equal(run("buyProduct({id:'buy-1',product_id:'product'}).status"),'Committed');
assert.equal(run('money'),200);
assert.equal(run("buyProduct({id:'buy-1',product_id:'product'}).spent"),100);
assert.equal(run('nativeBuys'),1,'A purchase receipt must prevent a repeated native commit');
run('throwPurchase=true');
assert.throws(()=>run("buyProduct({id:'buy-2',product_id:'product'})"),/lost native result/);
assert.equal(run("buyProduct({id:'buy-2',product_id:'product'}).status"),'unknown');
assert.equal(run('nativeBuys'),2);
assert.equal(run("setDifficulty({preset:'nightmare'}).settings.difficulty"),'easy');
assert.equal(run('nightmareCalls'),1,'Native unlock logic decides difficulty availability');
assert.equal(run("setDifficulty({preset:'normal'}).settings.difficulty"),'normal');
assert.equal(run('setSpeed({speed:100}).game_speed'),3,'Native slider clamps speed, without a second software limit');
assert.throws(()=>run("buyProduct({id:'missing',product_id:'stale'})"),/no longer displayed/);
run('controlled=false');
assert.throws(()=>run("buyProduct({id:'unowned',product_id:'product'})"),/own control/);
console.log('Story tests passed: excluded modes, native shopping, receipt non-replay, native difficulty and speed rules.');
