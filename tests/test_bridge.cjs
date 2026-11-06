// Exercise the actual Frida script in a mocked native environment; no injection.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = ['bridge.js','story.js'].map(file=>fs.readFileSync(path.join(__dirname,'../src',file),'utf8')).join('\n');

function bridge() {
  const hooks = [], timers = new Map();
  let timerId = 0;
  const pointer = value => ({add: n => pointer(value+n), isNull: () => value === 0, toString: () => String(value)});
  const context = vm.createContext({
    PROFILE: {}, SESSION: 'isolated',
    Process: {getModuleByName: () => ({base:pointer(100)}), getCurrentThreadId: () => 1},
    ptr: pointer,
    NativeFunction: function() { return () => {}; },
    Interceptor: {attach(address, handlers) {
      const hook = {handlers, detached:false, detach() { this.detached = true; }};
      hooks.push(hook); return hook;
    }},
    rpc: {}, send() {},
    setTimeout(callback) { timers.set(++timerId, callback); return timerId; },
    clearTimeout(id) { timers.delete(id); }
  });
  vm.runInContext(source, context);
  vm.runInContext(`
    let fakeSelection=1, allowRelease=false, releaseCalls=0;
    singleton=()=>({isNull:()=>false});
    read=()=>fakeSelection;
    enumName=(type,value)=>value===0?'Nothing':'Card';
    call=(type,name)=>{
      if(name==='GetKeyDown')return false;
      if(name==='$jP'){releaseCalls++;if(allowRelease)fakeSelection=0;}
    };
    observe=()=>({controlled});
    ownsSelection=true; controlled=true;
  `, context);
  return {context, hooks, timers, evaluate: code => vm.runInContext(code, context),
    pump: () => hooks[3].handlers.onEnter()};
}

(async () => {
  const failed = bridge();
  let promise = failed.context.rpc.exports.dispose();
  failed.pump();
  assert.equal((await promise).ok, false);
  assert.equal(failed.hooks.some(h=>h.detached), false, 'Failed release must retain every hook');
  assert.equal(failed.evaluate('stopping'), false);
  assert.equal(failed.timers.size, 0);
  assert.throws(()=>failed.evaluate("dispatch({op:'attach'})"), /not released/);
  failed.evaluate('allowRelease=true');
  promise = failed.context.rpc.exports.dispose();
  failed.pump();
  const released = await promise;
  assert.equal(released.ok, true);
  assert.equal(released.result.selection_released, true);
  assert.equal(released.result.native_selection, 0);
  assert.equal(failed.hooks.every(h=>h.detached), true);

  const stalled = bridge();
  promise = stalled.context.rpc.exports.dispose();
  [...stalled.timers.values()][0]();
  assert.equal((await promise).ok, false);
  assert.equal(stalled.evaluate('queue.length'), 0);
  stalled.pump();
  assert.equal(stalled.evaluate('releaseCalls'), 0, 'Timed-out dispose must not execute later');
  assert.equal(stalled.hooks.some(h=>h.detached), false);

  const player = bridge();
  player.evaluate('ownsSelection=false');
  promise = player.context.rpc.exports.request({op:'detach'});
  player.pump();
  const playerRelease = await promise;
  assert.equal(playerRelease.ok, true);
  assert.equal(playerRelease.result.selection_released, true);
  assert.equal(playerRelease.result.native_selection, 1);
  assert.equal(player.evaluate('releaseCalls'), 0, 'Do not cancel the player\'s selection');

  const restore = bridge();
  restore.evaluate(`
    let cleanupCalls=0;
    const fakeCard={toString:()=> 'card'};
    const fakeMouse={add:()=>({readByteArray:()=>[],writeS32(){},writeFloat(){},
      writeByteArray(){throw Error('restore failed');}})};
    requireBattle=()=>({});requirePhase=()=>{};
    pointerProjector=()=>()=>[0,0,0];
    singleton=()=>fakeMouse;selection=()=>0;
    objects=()=>[fakeCard];
    card=()=>({cost:0,cooldown:0,available:true,disabled:false});
    read=(p,type,name)=>name==='rowNum'||name==='columnNum'?5:
      name==='onCardBank'?true:name==='theCardOnMouse'?{isNull:()=>false,equals:()=>true}:0;
    list=()=>[];
    call=(type,name)=>{if(name==='$kP')throw Error('native action failed');return [0,0,0];};
    releaseSelection=()=>{cleanupCalls++;};
  `);
  assert.throws(()=>restore.evaluate("plant({battle_id:'test',card_id:'card',row:1,column:1})"), /restore failed/);
  assert.equal(restore.evaluate('cleanupCalls'), 1, 'Restoration failure must still attempt selection release');
  assert.equal(restore.evaluate('pointerOverride'), null);
  console.log('Bridge regressions passed: failed release, recovery, timed-out disposal, player selection, restoration failure.');
})().catch(error=>{console.error(error);process.exitCode=1;});
