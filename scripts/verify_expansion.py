"""Live acceptance of unlocked story features through the maintained bridge."""
from pathlib import Path
import argparse
import json
import time
import uuid
import subprocess
import sys
import re
from client import HorrorClient
from play_story import decide_plant, PREFERENCES

ROOT=Path(__file__).resolve().parents[1]


class McpClient:
    """Exercise the same MCP envelopes and tool names used by an AI client."""
    def __init__(self,directory):
        self.process=subprocess.Popen([sys.executable,'-u','-X','utf8',str(ROOT/'scripts/run_mcp.py')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf8',bufsize=1)
        self.wire=(directory/'mcp-wire.jsonl').open('a',encoding='utf8',buffering=1)
        self.exchange('initialize',{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'horror-acceptance','version':'1'}})
        tools=self.exchange('tools/list',{})
        (directory/'mcp-tools.json').write_text(json.dumps(tools,ensure_ascii=False,indent=2),encoding='utf8')

    def exchange(self,method,params):
        envelope={'jsonrpc':'2.0','id':uuid.uuid4().hex,'method':method,'params':params}
        self.process.stdin.write(json.dumps(envelope,ensure_ascii=False)+'\n');self.process.stdin.flush()
        line=self.process.stdout.readline()
        if not line:raise RuntimeError('MCP transport closed; action result unknown')
        response=json.loads(line)
        self.wire.write(json.dumps({'request':envelope,'response':response},ensure_ascii=False)+'\n')
        if 'error' in response:raise RuntimeError(response['error'])
        return response['result']

    def request(self,op,**args):
        name={'attach':'take_control','detach':'release_control'}.get(op,op)
        response=self.exchange('tools/call',{'name':'pvzh_'+name,'arguments':args})
        return json.loads(response['content'][0]['text'])

    def __enter__(self):return self
    def __exit__(self,*_):
        self.process.stdin.close();self.process.wait(timeout=20);self.wire.close()


class Acceptance:
    def __init__(self, game, directory):
        self.game=game;self.directory=directory
        self.log=(directory/'actions.jsonl').open('a',encoding='utf8',buffering=1)
        self.results={}

    def request(self, op, **args):
        response=self.game.request(op,**args)
        if op!='observe':
            self.log.write(json.dumps({'time':time.time(),'op':op,'args':args,'response':response},ensure_ascii=False)+'\n')
        if not response.get('ok'):raise RuntimeError(response)
        result=response['result']
        if op=='observe':self.save('state',result)
        return result

    def save(self, name, value):
        (self.directory/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')

    def click(self, menu, action):
        return self.request('menu_action',menu_id=menu['menu_id'],action_id=action['action_id'])

    def wait_menu(self, predicate, seconds=20):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            menu=self.request('menu');self.save('menu',menu)
            if predicate(menu):return menu
            notice=next((a for a in menu['actions'] if a['kind']=='continue_notice'),None)
            if notice:self.click(menu,notice)
            time.sleep(.25)
        raise RuntimeError('Native menu did not reach expected page; see menu.json')

    def home(self):
        state=self.request('observe')
        if state['phase'] in ('running','selection'):
            self.request('set_paused',battle_id=state['battle_id'],paused=True)
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            menu=self.request('menu');self.save('menu',menu)
            if self.archive_step(menu):time.sleep(.2);continue
            if menu['state']['phase'] in ('running','selection'):
                self.request('set_paused',battle_id=menu['state']['battle_id'],paused=True);continue
            close=next((a for a in menu['actions'] if a.get('native_class')!='MainMenuBtn' and a['label'] in ('Close','CloseButton','ReturnButton')),None)
            if close:
                self.click(menu,close);time.sleep(.3);continue
            if any(a['label']=='StoryMode' for a in menu['actions']) and not any(a.get('native_class')=='DialogBtn' for a in menu['actions']):
                return menu
            action=next((a for a in menu['actions'] if a['kind']=='continue_notice' or a['label'] in ('ReturnMainMenu','ReturnMenu','MainMenu','ReturnButton','CloseButton','Close','Yesbtn')),None)
            if not action:action=next((a for a in menu['actions'] if a.get('native_class')=='PauseMenuBtn' and a['label']=='Quit'),None)
            if action:self.click(menu,action)
            time.sleep(.3)
        raise RuntimeError('Cannot return to home; see menu.json')

    def archive_step(self,menu):
        if not any(t['name']=='Title' and 'Z公司档案' in t.get('text','') for t in menu['texts']):return False
        text=next((t['text'] for t in menu['texts'] if t['name']=='PageCounter'),'')
        match=re.search(r'(\d+)\s*/\s*(\d+)',text)
        page,total=map(int,match.groups()) if match else (0,0)
        self.save('archive-page-'+str(page),menu)
        label='NextButton' if page<total else 'FinishButton'
        self.click(menu,next(a for a in menu['actions'] if a['label']==label))
        self.results.setdefault('archive_pages',[]).append({'page':page,'total':total})
        print('ARCHIVE',page,total,label,flush=True)
        return True

    def catalog(self):
        entries=[]
        for level in range(1,42):
            info=self.request('game_info',level=level)['requested_level'];entries.append(info)
            print(json.dumps(info,ensure_ascii=False),flush=True)
        self.save('catalog',entries);self.results['catalog_levels']=len(entries)

    def schema(self,names):
        for name in names.split(','):
            data=self.request('game_info',inspect_class='.'+name)['native_schema']
            self.save('schema-'+name,data);print(json.dumps(data,ensure_ascii=False),flush=True)

    def shop(self, product_name=None, inspect_only=False):
        menu=self.home();self.click(menu,next(a for a in menu['actions'] if a['label']=='Store'))
        deadline=time.monotonic()+15
        opened_category=False
        while time.monotonic()<deadline:
            store=self.request('store')
            if store['products']:break
            if not opened_category:
                menu=self.request('menu')
                category=next((a for a in menu['actions'] if a.get('native_class')=='StoreButton' and a['label']=='btn1'),None)
                if category:
                    try:self.click(menu,category);opened_category=True
                    except RuntimeError as exc:
                        if 'gate refused' not in str(exc):raise
            time.sleep(.25)
        else:raise RuntimeError('Unlocked native store has no products')
        self.save('store-before',store)
        if inspect_only:
            print(json.dumps(store,ensure_ascii=False),flush=True);self.home();return
        products=[p for p in store['products'] if p['price'] is not None and 0<p['price']<=store['money']]
        product=next(p for p in products if p['name']==product_name) if product_name else min(products,key=lambda p:p['price'])
        purchase=self.request('buy',product_id=product['product_id']);self.results['purchase']=purchase
        if purchase['status']!='Committed':raise RuntimeError('Native purchase refused: '+str(product))
        receipt=self.request('purchase_receipt',purchase_id=purchase['purchase_id']);self.save('purchase-receipt',receipt)
        self.save('store-after',self.request('store'))
        print('PURCHASE',json.dumps(purchase,ensure_ascii=False),flush=True)
        self.home()

    def nightmare(self):
        self.open_difficulty()
        result=self.request('set_difficulty',preset='nightmare');self.results['nightmare']=result
        if result['settings']['difficulty']!='nightmare':raise RuntimeError('Unlocked nightmare was refused')
        self.save('nightmare-menu',self.request('menu'))
        self.request('set_difficulty',preset='easy')
        print('NIGHTMARE',json.dumps(result,ensure_ascii=False),flush=True)
        self.home()

    def open_difficulty(self):
        menu=self.home();self.click(menu,next(a for a in menu['actions'] if a['label']=='Setting'))
        menu=self.wait_menu(lambda m:any(a.get('native_class')=='SettingControlEnterButton' for a in m['actions']))
        self.click(menu,next(a for a in menu['actions'] if a.get('native_class')=='SettingControlEnterButton'))
        time.sleep(.3)
    def controls(self):
        self.open_difficulty()
        controls=self.request('ui_controls');self.save('controls',controls)
        print(json.dumps(controls,ensure_ascii=False),flush=True)

    def almanac(self, names):
        menu=self.home();self.click(menu,next(a for a in menu['actions'] if a['label']=='Almanac'))
        time.sleep(.3)
        entries=self.request('almanac')['entries']
        for name in names.split(','):
            entry=next(e for e in entries if e['name']==name)
            self.request('almanac_select',entry_id=entry['entry_id'],kind=entry['kind']);time.sleep(.2)
            data=self.request('almanac');self.save('almanac-'+name,data)
            print(name,json.dumps(data['texts'],ensure_ascii=False),flush=True)
        self.home()

    def events(self):
        menu=self.home();self.click(menu,next(a for a in menu['actions'] if a['label']=='Event'))
        time.sleep(.4)
        menu=self.request('menu');self.save('event-menu',menu)
        reward=self.request('rewards');self.save('events',reward)
        self.results['event_entry_status']='native_unavailable' if any('暂未解锁' in t.get('text','') for t in menu['texts']) else 'opened'
        print(json.dumps({'menu':menu,'rewards':reward},ensure_ascii=False),flush=True)

    def enter_level(self, level):
        state=self.request('observe')
        if state['battle_id'] and state['game_info']['progress']['level']==level:
            if state['phase']=='defeat':
                menu=self.request('menu')
                retry=next(a for a in menu['actions'] if a.get('native_class')=='DialogBtn')
                self.click(menu,retry)
                deadline=time.monotonic()+20
                while time.monotonic()<deadline:
                    current=self.request('observe')
                    if current['battle_id']!=state['battle_id'] and current['battle_id']:return current
                    time.sleep(.25)
                raise RuntimeError('Native retry did not load the next battle')
            if state['phase'] in ('paused','selection_paused'):
                self.request('set_paused',battle_id=state['battle_id'],paused=False)
            return state
        menu=self.home();self.click(menu,next(a for a in menu['actions'] if a['label']=='StoryMode'))
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            state=self.request('observe')
            if state['battle_id'] and state['game_info']['progress']['level']==level:
                return state
            menu=self.request('menu');self.save('menu',menu)
            target=next((a for a in menu['actions'] if a.get('level')==level),None)
            if target:self.click(menu,target)
            else:
                confirm=next((a for a in menu['actions'] if a.get('native_class')=='LevelChooseConfirmButton'),None)
                maps=[a for a in menu['actions'] if a.get('native_class')=='MapChooseButton']
                if confirm:
                    try:self.click(menu,confirm)
                    except RuntimeError as exc:
                        if 'gate refused' not in str(exc):raise
                        if maps:self.click(self.request('menu'),maps[0])
                elif maps:self.click(menu,maps[0])
            time.sleep(.3)
        raise RuntimeError('Cannot enter unlocked native level '+str(level))

    def battle(self, level, seconds, resume_current=False, cheat=False,resume_result=None):
        prior=None
        if resume_result:
            prior=json.loads(resume_result.read_text(encoding='utf8'))['results']
            if not prior.get('reward_collected'):raise RuntimeError('Resume result has no committed reward')
        elif resume_current:
            state=self.request('observe')
            if not state['battle_id'] or state['game_info']['progress']['level']!=level:
                raise RuntimeError('Requested live story battle is not present')
            if state['phase'] in ('paused','selection_paused'):
                self.request('set_paused',battle_id=state['battle_id'],paused=False)
        else:self.enter_level(level)
        deadline=time.monotonic()+seconds;selected=None;last_status=0;last_snapshot=0
        seen_rewards=set();seen_specials=set();interacted=False;ability_retry={};next_assist=0;stage_key=None;stage_since=0
        observations=(self.directory/'observations.jsonl').open('a',encoding='utf8',buffering=1)
        self.results.update(level=level,special_plants=[],boss_seen=False,events=[])
        if prior:
            self.results.update(prior)
            self.results.pop('stop_requested',None)
            self.results['resumed_result']=str(resume_result)
        try:
            while time.monotonic()<deadline:
                state=self.request('observe');phase=state['phase'];now=time.monotonic()
                if (self.directory/'stop.request').exists():self.results['stop_requested']=True;break
                if now-last_snapshot>2:
                    observations.write(json.dumps(state,ensure_ascii=False)+'\n');last_snapshot=now
                if now-last_status>12:
                    print(json.dumps({'level':state['game_info']['progress']['level'],'phase':phase,'wave':state.get('wave'),
                         'plants':len(state.get('plants',[])),'zombies':len(state.get('zombies',[])),
                         'mechanics':state.get('mechanics'),'bosses':state.get('bosses')},ensure_ascii=False),flush=True);last_status=now
                if any(b.get('active') for b in state.get('bosses',[])):
                    self.results['boss_seen']=True;self.save('boss',state['bosses'])
                if phase=='running':
                    if cheat and now>=next_assist:
                        current=','.join(b.get('kind') or '' for b in state.get('bosses',[]) if b.get('active'))
                        special=sorted({z['kind'] for z in state.get('zombies',[]) if z['kind'] in ('DaveBone','DaveEye','DaveHeart') and z['health']>0 and not z['dying']})
                        if special:current+='-'+','.join(special)
                        if current!=stage_key:
                            stage_key=current;stage_since=now;self.save('stage-'+(current or 'waves'),state)
                            self.results.setdefault('assisted_stages',[]).append(current or 'waves')
                        scope='mobs' if current and now-stage_since<3 else 'all'
                        result=self.request('test_assist',battle_id=state['battle_id'],scope=scope,advance_waves=True)
                        self.results['assisted']=True;next_assist=now+1
                        time.sleep(.1);continue
                    if not state['auto_collect']:self.request('auto_collect',battle_id=state['battle_id'],enabled=True)
                    coins=[p['sun_id'] for p in state['suns'] if 'sun' not in p['kind'].lower()]
                    if coins:self.request('collect',battle_id=state['battle_id'],sun_ids=coins)
                    if not interacted and state['plants']:
                        self.results['interaction']=self.request('interact',battle_id=state['battle_id'],entity_id=state['plants'][0]['entity_id']);interacted=True
                    actor=next((p for p in state['plants'] if p.get('ability',{} ) and p['ability']['kind']=='pastor' and
                                not p['ability']['spent'] and p['ability'].get('restore',0)<=0 and
                                (p['ability']['crosses']>=3 or state['sun']>=150) and
                                now>=ability_retry.get(p['entity_id'],0)),None)
                    if actor:
                        result=self.request('interact',battle_id=state['battle_id'],entity_id=actor['entity_id'])
                        before=result.get('ability_before');after=result.get('ability_after')
                        changed=bool(before and after and (before['crosses']!=after['crosses'] or before['spent']!=after['spent']))
                        ability_retry[actor['entity_id']]=now+(.1 if changed else 2)
                        if changed:
                            self.results['ability_commits']=self.results.get('ability_commits',0)+1
                            print('ABILITY',json.dumps(result,ensure_ascii=False),flush=True)
                    move=decide_plant(state)
                    if move:
                        card,row,column=move
                        result=self.request('plant',battle_id=state['battle_id'],card_id=card['card_id'],row=row,column=column)
                        if result.get('status')=='Committed' and card.get('source') in ('conveyor','falling'):
                            key=card['source']+':'+card['plant_name']
                            if key not in seen_specials:
                                seen_specials.add(key);self.results['special_plants'].append({'card':card,'result':result});print('SPECIAL',key,row,column,flush=True)
                elif phase=='selection' and selected!=state['battle_id']:
                    chosen=sum(c.get('selected',False) for c in state['cards']);slots=state['game_info']['progress']['seed_slots']
                    for name in PREFERENCES:
                        if chosen>=slots:break
                        card=next((c for c in state['cards'] if c['plant_name']==name and not c.get('selected')),None)
                        if card:
                            result=self.request('choose_card',battle_id=state['battle_id'],card_id=card['card_id'],selected=True)
                            if result['card']['selected']:chosen+=1
                    selected=state['battle_id'];self.request('start_battle',battle_id=selected)
                elif phase=='defeat':self.results['battle_outcome']='defeated';break
                enemies=[z for z in state.get('zombies',[]) if z['kind']!='PaladinGargantuar' and not z['dying'] and z['health']>0]
                reward=self.request('rewards') if phase in ('victory','menu') or phase=='running' and state.get('wave',0)>=state.get('max_wave',1) and not enemies else None
                if reward:
                    item=next((p for p in reward['items'] if p['reward_id'] not in seen_rewards),None)
                    if item:
                        seen_rewards.add(item['reward_id']);self.request('collect_reward',battle_id=state['battle_id'],reward_id=item['reward_id']);self.results['reward_collected']=True
                    events=reward['events']
                    if events:
                        event=next((e for e in events if e['revealed']),events[0]);self.results['events'].append(event)
                        if not event.get('animating'):self.request('choose_event',event_id=event['event_id'])
                    elif phase=='menu' and self.results.get('reward_collected'):
                        menu=self.request('menu');self.save('menu',menu)
                        if self.archive_step(menu):time.sleep(.2);continue
                        close=next((a for a in menu['actions'] if a.get('native_class')=='LevelChooseCloseButton'),None)
                        if close:self.click(menu,close);time.sleep(.2);continue
                        if any(a['label']=='StoryMode' for a in menu['actions']):
                            self.results['battle_outcome']='won';self.results['final_menu']='main';break
                if phase in ('diary','moving','selection_paused','victory','menu'):
                    menu=self.request('menu');self.save('menu',menu)
                    action=next((a for a in menu['actions'] if a['kind']=='continue_notice' or a['label']=='Skip' or a.get('native_class')=='NewEnemyHintCloseButton'),None)
                    if action:self.click(menu,action)
                time.sleep(.2)
            else:self.results['battle_outcome']='time_limit'
        finally:observations.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario',choices=['catalog','schema','shop','nightmare','controls','events','almanac','battle','inspect'],required=True)
    parser.add_argument('--parent',type=Path)
    parser.add_argument('--level',type=int,default=41)
    parser.add_argument('--seconds',type=int,default=240)
    parser.add_argument('--resume-current',action='store_true',help='Continue the current native battle without returning to menus')
    parser.add_argument('--cheat',action='store_true',help='User-authorized assisted acceptance; preserve native stage/death/result transitions')
    parser.add_argument('--transport',choices=['tcp','mcp'],default='tcp')
    parser.add_argument('--resume-result',type=Path,help='Continue ending navigation from a persisted collected-reward result')
    parser.add_argument('--product-name')
    parser.add_argument('--inspect-only',action='store_true')
    parser.add_argument('--plant-names',default='SuperMagicShooter,ScripturePumpkin,PastorGarlic,TaoistGlutinousRice')
    parser.add_argument('--class-names',default='PastorGarlic,Stove,MeatGrinder,SuperMagicShooter')
    args=parser.parse_args()
    parent=args.parent or ROOT/'evidence'
    directory=parent/(args.scenario+'-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]);directory.mkdir(parents=True)
    print('EVIDENCE',directory,flush=True)
    summary={'scenario':args.scenario,'outcome':'running','transport':args.transport}
    with (McpClient(directory) if args.transport=='mcp' else HorrorClient()) as game:
        task=Acceptance(game,directory)
        try:
            caps=task.request('capabilities')
            if caps['game']!='PVZ-Scared':raise RuntimeError('Unexpected game')
            task.request('attach')
            if args.scenario=='inspect':
                task.save('state',task.request('observe'));menu=task.request('menu');task.save('menu',menu)
                print(json.dumps(menu,ensure_ascii=False),flush=True)
            elif args.scenario=='battle':task.battle(args.level,args.seconds,args.resume_current,args.cheat,args.resume_result)
            elif args.scenario=='shop':task.shop(args.product_name,args.inspect_only)
            elif args.scenario=='almanac':task.almanac(args.plant_names)
            elif args.scenario=='schema':task.schema(args.class_names)
            else:getattr(task,args.scenario)()
            summary.update(outcome='completed',results=task.results)
        except Exception as exc:
            summary.update(outcome='interrupted',error=str(exc));print('INTERRUPTED',str(exc),flush=True)
        finally:
            try:summary['release']=game.request('detach')
            except Exception as exc:summary['release']={'ok':False,'error':str(exc)}
            task.save('summary',summary);task.log.close()
    print('FINISHED',summary['outcome'],flush=True)
    return 0 if summary['outcome']=='completed' else 1


if __name__=='__main__':raise SystemExit(main())
