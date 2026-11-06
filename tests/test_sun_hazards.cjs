const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const pointer=n=>({add:v=>pointer(n+v),isNull:()=>n===0,toString:()=>String(n)});
const ctx=vm.createContext({PROFILE:{classes:{}},SESSION:'sun-test',
  Process:{getModuleByName:()=>({base:pointer(100)}),getCurrentThreadId:()=>1},NativeFunction:function(){return()=>{};},
  ptr:pointer,Interceptor:{attach:()=>({detach(){}})},rpc:{},send(){},setTimeout(){},clearTimeout(){}});
vm.runInContext(['bridge.js','story.js'].map(f=>fs.readFileSync(path.join(__dirname,'../src',f),'utf8')).join('\n'),ctx);
const run=code=>vm.runInContext(code,ctx);
run(`
  const red=ptr(1),small=ptr(2),yellow=ptr(3),livePlant=ptr(4),dead=ptr(5),gone=ptr(6);
  let level=40,near=true,pickups=[],predicateCalls=[];
  alive=p=>String(p)!=='6';
  read=(p,t,k)=>k==='dying'?String(p)==='5':k==='theItemType'?String(p):k==='value'?50:k==='theSun'?100:0;
  enumName=(t,k)=>({'1':'BloodSun','2':'SmallBloodSun','3':'NormalSun'})[k];
  call=(type,name,p,arg)=>{
    if(name==='get_transform')return p;
    if(name==='get_position')return [10,20,0];
    if(name==='$tO'){predicateCalls.push(String(arg));return near;}
    if(name==='$cJA')pickups.push(String(p));
  };
  requireBattle=()=>({});requirePhase=()=>{};collectibles=()=>[red,small,yellow];
  list=()=>[livePlant,dead,gone];gameInfo=()=>({progress:{level}});
`);
const snapshot=JSON.parse(run('JSON.stringify(sunSnapshot(red,[livePlant,dead,gone]))'));
assert.deepEqual(snapshot,{sun_id:'1',value:50,kind:'BloodSun',x:10,y:20,threatened_plant_ids:['4']});
assert.equal(run('predicateCalls.join(",")'),'4','Only living native plants enter the damage predicate');
assert.equal(run('pickups.length'),0,'Observation must not collect');
assert.equal(run('sunSnapshot(yellow,[livePlant]).threatened_plant_ids'),undefined);
const collect=policy=>JSON.parse(run(`JSON.stringify(dispatch({op:'collect',sun_ids:['1','2','3'],red_sun_policy:${JSON.stringify(policy)}}))`));
assert.equal(collect(undefined).count,1,'Default callers collect only ordinary light');
assert.deepEqual(JSON.parse(run('JSON.stringify(pickups)')),['3']);
run('pickups=[]');assert.equal(collect('level40-near-plant').count,3);
for(const level of [39,41]){run(`level=${level};pickups=[]`);assert.equal(collect('level40-near-plant').count,1);assert.equal(run('pickups.join(",")'),'3');}
run('level=40;near=false;pickups=[]');
assert.deepEqual(collect('level40-near-plant').skipped_sun_ids,['1','2'],'Recheck proximity on the game thread after observation');
assert.equal(run('pickups.join(",")'),'3');
console.log('Sun hazards passed: native position/predicate, observation purity, scoped pickup, stale proximity, default ordinary pickup.');
