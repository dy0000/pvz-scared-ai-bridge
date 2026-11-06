"""Bounded realtime story runner. Uses one maintained native client and never replays unknown actions."""
from pathlib import Path
import argparse
import json
import sys
import time
import uuid

from client import HorrorClient

ROOT=Path(__file__).resolve().parents[1]
PREFERENCES=['BloodSunFlower','SunFlower','TwinSunflower','ExperimentFlower','PeaShooter','Wallnut','PotatoMine','CherryBomb','Squash','DoublePeaShooter','SnowPea','Chomper','Tallnut','PumpkinShell']
ATTACKERS={'PeaShooter','DoublePeaShooter','SnowPea','BloodPeaShooter','AlienShooter','SuperMachineGunShooter','SuperMagicShooter','HypothermiaPeaShooter','PultShooter','LinCornpult','Lin_Cornpult','TaoistGlutinousRice'}
FARMERS={'SunFlower','TwinSunflower','BloodSunFlower','ExperimentFlower'}


def decide_plant(state):
    """Use native availability and the current field; no game values or unlocks are changed."""
    plants=[p for p in state['plants'] if not p['dying']]
    occupied={(p['row'],p['column']) for p in plants}
    ready=[c for c in state['cards'] if c.get('source') in ('conveyor','falling') or
           c.get('on_bank') and c['available'] and not c['disabled'] and c['cooldown']<=0 and c['cost']<=state['sun']]
    enemies=[z for z in state['zombies'] if z['kind']!='PaladinGargantuar' and not z['dying'] and z['health']>0]
    threats={row:min((z['column'] for z in enemies if z['row']==row),default=100) for row in range(1,state['rows']+1)}
    damage={row:sum(p['row']==row and p['kind'] in ATTACKERS for p in plants) for row in threats}
    rows=sorted(threats,key=lambda row:(threats[row],damage[row],abs(row-(state['rows']+1)/2)))
    def place(card,row,columns):
        for column in columns:
            if 1<=column<=state['columns'] and (row,column) not in occupied:
                return card,row,column
    # Final-story boss has a moving body. Save a ready blast for its actual
    # lane when the lawn has no immediate breach; do not waste every blast on
    # the earliest ordinary zombie in a different row.
    boss=next((z for z in state['zombies'] if z['kind'] in ('DaveLevel1','BossZombie') and not z['dying'] and z['health']>0),None)
    blast=next((c for c in ready if c['plant_name'] in ('VisceraBomb','CherryBomb')),None)
    if boss and blast and min(threats.values(),default=100)>2:
        move=place(blast,boss['row'],[boss['column'],boss['column']-1,boss['column']+1])
        if move:return move
    parts=[part for boss in state.get('bosses',[]) for part in boss.get('parts',[]) if part['health']>0 and not part['dying']]
    if parts and blast and any(p.get('splash_rows') for p in parts):
        target_rows=sorted(range(1,state['rows']+1),key=lambda row:(-sum(min(p['health'],1800) for p in parts if row in p.get('splash_rows',[])),threats[row]))
        for row in target_rows:
            if not any(row in p.get('splash_rows',[]) for p in parts):continue
            threat=max(1,min(state['columns'],threats[row]))
            move=place(blast,row,[threat,threat-1,threat+1,*range(state['columns'],0,-1)])
            if move:return move
    if parts and blast and min(threats.values(),default=100)>2:
        xpair=next(((a,b) for a in plants for b in plants if a['column']!=b['column']),None)
        ypair=next(((a,b) for a in plants for b in plants if a['row']!=b['row']),None)
        if xpair and ypair:
            a,b=xpair;dx=(b['x']-a['x'])/(b['column']-a['column']);x0=a['x']-dx*(a['column']-1)
            a,b=ypair;dy=(b['y']-a['y'])/(b['row']-a['row']);y0=a['y']-dy*(a['row']-1)
            if abs(dx)>.01 and abs(dy)>.01:
                part=min(parts,key=lambda p:p['health']);x,y,*_=part['position']
                column=max(1,min(state['columns'],round((x-x0)/dx)+1));row=max(1,min(state['rows'],round((y-y0)/dy)+1))
                for r,c in ((row,column),(row,column-1),(row,column+1),(row+1,column),(row-1,column)):
                    if 1<=r<=state['rows']:
                        move=place(blast,r,[c])
                        if move:return move
    # Explicitly targeted emergency cards retain their normal game mechanics.
    for row in rows:
        if threats[row]<=5:
            card=next((c for c in ready if c['plant_name'] in ('Squash','CherryBomb','VisceraBomb')),None)
            if card:
                move=place(card,row,[max(1,min(state['columns'],threats[row])),max(1,threats[row]-1)])
                if move:return move
        if threats[row]<100 and damage[row]==0:
            card=next((c for c in ready if c['plant_name'] in ATTACKERS),None)
            if card:
                move=place(card,row,[4,5,6,7] if state.get('mechanics',{}).get('conveyor') else [3,4,2])
                if move:return move
    specials=sorted((c for c in ready if c.get('source') in ('conveyor','falling')),
                    key=lambda c:(c['plant_name']!='SuperMagicShooter',c.get('source')!='falling'))
    cover=next((c for c in specials if c['plant_name'] in ('ScripturePumpkin','PumpkinShell')),None)
    if cover:
        covered={(p['row'],p['column']) for p in plants if p['kind'] in ('ScripturePumpkin','PumpkinShell')}
        priority=['SuperMagicShooter','TaoistGlutinousRice','PastorGarlic','LinCornpult','AlienShooter','HypothermiaPeaShooter','BloodPeaShooter']
        target=min((p for p in plants if p['kind'] in priority and (p['row'],p['column']) not in covered),
                   key=lambda p:(priority.index(p['kind']),p['health']),default=None)
        if target:return cover,target['row'],target['column']
    for card in specials:
        name=card['plant_name']
        if name in ('ScripturePumpkin','PumpkinShell'):continue
        target_rows=sorted(rows,key=lambda row:(damage[row],threats[row])) if name in ATTACKERS else rows
        if name=='PastorGarlic':target_rows=sorted(rows,key=lambda row:(min(abs(row-2),abs(row-4)),threats[row]))
        conveyor=state.get('mechanics',{}).get('conveyor')
        columns=([1,2] if name in FARMERS else ([4,5,6,7,3,2,1,8,9] if conveyor else [1,2,3,4,5,6,7,8,9]) if name in ATTACKERS else
                 [8,7,6] if name in ('SarcomaWallnut','Wallnut','Tallnut') and conveyor else [6,7,5] if name in ('SarcomaWallnut','Wallnut','Tallnut') else
                 [7,8,6,5] if name in ('MutatedChomper','Chomper','BloodCaltrop') else [4,5,6] if name=='PastorGarlic' and conveyor else [2,3,1,4] if name=='PastorGarlic' else [3,4,5,6,2,7,1,8,9])
        for row in target_rows:
            move=place(card,row,columns)
            if move:return move
    farmers=sum(p['kind'] in FARMERS for p in plants)
    farmer=next((c for c in ready if c['plant_name'] in FARMERS),None)
    if farmer and farmers<state['rows']*2:
        danger=any(threats[row]<8 and damage[row]==0 for row in rows)
        if not danger:
            for column in [1,2]:
                for row in sorted(rows,key=lambda row:abs(row-(state['rows']+1)/2)):
                    move=place(farmer,row,[column])
                    if move:return move
    attacker=next((c for c in ready if c['plant_name'] in ATTACKERS),None)
    if attacker:
        for row in sorted(rows,key=lambda row:(damage[row],threats[row])):
            move=place(attacker,row,[3,4,5])
            if move:return move
    wall=next((c for c in ready if c['plant_name'] in ('Wallnut','Tallnut','SarcomaWallnut')),None)
    if wall:
        for row in rows:
            if threats[row]<100:
                move=place(wall,row,[6])
                if move:return move
    return None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--levels',type=int,default=1)
    parser.add_argument('--seconds',type=int,default=900)
    parser.add_argument('--retries',type=int,default=3)
    parser.add_argument('--speed',type=float,default=3)
    parser.add_argument('--probe-tools',action='store_true',help='Exercise one native glove move and one shovel removal during play')
    parser.add_argument('--resume',type=Path,help='Prior state.json to continue from, writing fresh artifacts')
    args=parser.parse_args()
    directory=ROOT/'evidence'/('story-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    directory.mkdir()
    output=(directory/'actions.jsonl').open('a',encoding='utf8',buffering=1)
    progress={'outcome':'running','completed_levels':0,'retries':0,'resumed_from':str(args.resume) if args.resume else None}
    if args.resume:
        previous=json.loads(args.resume.read_text(encoding='utf8'))
        progress['prior_outcome']=previous.get('outcome')
    deadline=time.monotonic()+args.seconds;selected_battle=None;seen_rewards=set();last_nav=0;start_level=None;last_status=0;speed_applied=False
    print('EVIDENCE',directory,flush=True)
    with HorrorClient() as game:
        def request(op,**kw):
            response=game.request(op,**kw)
            if op!='observe':output.write(json.dumps({'time':time.time(),'op':op,'args':kw,'response':response},ensure_ascii=False)+'\n')
            if not response.get('ok'):raise RuntimeError(response)
            return response['result']
        def navigate(menu,action):
            return request('menu_action',menu_id=menu['menu_id'],action_id=action['action_id'])
        try:
            capabilities=request('capabilities')
            if capabilities['game']!='PVZ-Scared':raise RuntimeError('Wrong game target')
            request('attach')
            while time.monotonic()<deadline:
                state=request('observe');info=state['game_info'];level=info['progress']['level']
                if start_level is None:start_level=level
                progress['completed_levels']=max(0,level-start_level)
                progress.update(game_info=info,state=state,updated_at=time.time())
                (directory/'state.json').write_text(json.dumps(progress,ensure_ascii=False,indent=2),encoding='utf8')
                if state['player_locked']:
                    progress['outcome']='player_stopped';break
                if (directory/'stop.request').exists():
                    progress['outcome']='stopped';break
                if time.monotonic()-last_status>=12:
                    print(json.dumps({'level':level,'phase':state['phase'],'sun':state.get('sun'),'plants':len(state.get('plants',[])),'zombies':len(state.get('zombies',[])),'wave':state.get('wave'),'max_wave':state.get('max_wave')},ensure_ascii=False),flush=True)
                    last_status=time.monotonic()
                phase=state['phase']
                if progress['completed_levels']>=args.levels and phase in ('menu','selection'):
                    progress['outcome']='completed';break
                if phase=='running' and state.get('wave',0)>=state.get('max_wave',1) and not state['zombies']:
                    reward=request('rewards')
                    item=next((p for p in reward['items'] if (state['battle_id'],p['reward_id']) not in seen_rewards),None)
                    if item:
                        seen_rewards.add((state['battle_id'],item['reward_id']))
                        request('collect_reward',battle_id=state['battle_id'],reward_id=item['reward_id']);time.sleep(.3);continue
                if phase=='running':
                    if not state['auto_collect']:request('auto_collect',battle_id=state['battle_id'],enabled=True)
                    if not speed_applied:
                        if abs(info['settings']['game_speed']-args.speed)>.01:
                            configured=request('set_speed',speed=args.speed);print('NATIVE SPEED',configured,flush=True)
                        speed_applied=True
                        continue
                    if args.probe_tools:
                        if progress.get('glove_probe',{}).get('status')!='Committed' and progress.get('glove_probe_battle')!=state['battle_id']:
                            target=next((p for p in state['plants'] if p['kind'] in ATTACKERS and not p['dying']),None)
                            if target:
                                destination=4 if target['column']!=4 else 3
                                if not any(p['row']==target['row'] and p['column']==destination for p in state['plants']):
                                    progress['glove_probe']=request('move_plant',battle_id=state['battle_id'],entity_id=target['entity_id'],row=target['row'],column=destination)
                                    progress['glove_probe_battle']=state['battle_id']
                                    print('GLOVE PROBE',progress['glove_probe'],flush=True);continue
                        if progress.get('shovel_probe',{}).get('status')!='Committed' and progress.get('shovel_probe_battle')!=state['battle_id']:
                            target=next((p for p in state['plants'] if p['kind'] in FARMERS and not p['dying']),None)
                            if target:
                                progress['shovel_probe']=request('shovel',battle_id=state['battle_id'],entity_id=target['entity_id'])
                                progress['shovel_probe_battle']=state['battle_id']
                                print('SHOVEL PROBE',progress['shovel_probe'],flush=True);continue
                    coins=[p['sun_id'] for p in state['suns'] if 'sun' not in p['kind'].lower()]
                    if coins:request('collect',battle_id=state['battle_id'],sun_ids=coins)
                    move=decide_plant(state)
                    if move:
                        card,row,column=move
                        result=request('plant',battle_id=state['battle_id'],card_id=card['card_id'],row=row,column=column)
                        if result.get('status')=='Committed':print('PLANTED',card['plant_name'],row,column,flush=True)
                    time.sleep(.2);continue
                if phase=='selection':
                    if selected_battle!=state['battle_id']:
                        chosen=sum(c.get('selected',False) for c in state['cards'])
                        slots=info['progress']['seed_slots']
                        for name in PREFERENCES:
                            if chosen>=slots:break
                            card=next((c for c in state['cards'] if c['plant_name']==name and not c.get('selected')),None)
                            if card:
                                result=request('choose_card',battle_id=state['battle_id'],card_id=card['card_id'],selected=True)
                                if result['card']['selected']:chosen+=1
                        selected_battle=state['battle_id']
                    request('start_battle',battle_id=state['battle_id']);time.sleep(.3);continue
                if phase in ('victory','diary','menu'):
                    reward=request('rewards')
                    item=next((p for p in reward['items'] if (state['battle_id'],p['reward_id']) not in seen_rewards),None)
                    if item:
                        seen_rewards.add((state['battle_id'],item['reward_id']))
                        request('collect_reward',battle_id=state['battle_id'],reward_id=item['reward_id']);time.sleep(.3);continue
                    if reward['events']:
                        event=next((e for e in reward['events'] if e['revealed']),reward['events'][0])
                        if event.get('animating'):time.sleep(.2);continue
                        request('choose_event',event_id=event['event_id']);time.sleep(.6);continue
                if time.monotonic()-last_nav<.4:time.sleep(.15);continue
                last_nav=time.monotonic();menu=request('menu');actions=menu['actions']
                if not actions:time.sleep(.2);continue
                if phase=='defeat':
                    progress['retries']+=1
                    if progress['retries']>args.retries:progress['outcome']='defeated';break
                    action=next((a for a in actions if a.get('native_class')=='DialogBtn'),None)
                else:
                    action=next((a for a in actions if a['kind']=='continue_notice' or a['label']=='Skip' or a.get('native_class')=='NewEnemyHintCloseButton'),None)
                    if not action and phase in ('paused','selection_paused'):
                        action=next((a for a in actions if a['label'] in ('ReturnGame','Yesbtn')),None)
                    if not action and phase=='menu':
                        if progress['completed_levels']>=args.levels:progress['outcome']='completed';break
                        request('next_level');time.sleep(.4);continue
                if action:navigate(menu,action)
                time.sleep(.2)
            else:progress['outcome']='time_limit'
        except Exception as exc:
            progress.update(outcome='interrupted',error=str(exc));print('INTERRUPTED',str(exc),flush=True)
        finally:
            try:progress['release']=game.request('detach')
            except Exception as exc:progress['release']={'ok':False,'error':str(exc),'held_os_inputs':0}
            progress['updated_at']=time.time()
            (directory/'state.json').write_text(json.dumps(progress,ensure_ascii=False,indent=2),encoding='utf8')
            (directory/'summary.json').write_text(json.dumps({k:v for k,v in progress.items() if k!='state'},ensure_ascii=False,indent=2),encoding='utf8')
            output.close();print('FINISHED',progress['outcome'],flush=True)
    return 0 if progress['outcome'] in ('completed','stopped','player_stopped') else 1


if __name__=='__main__':sys.exit(main())
