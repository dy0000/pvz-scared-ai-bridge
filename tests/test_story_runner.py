"""Decisions for the demonstrated late-story boss failure, without live input."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from play_story import decide_plant


class BossDecisions(unittest.TestCase):
    def state(self, ordinary_column):
        return {'rows':5,'columns':9,'sun':0,'plants':[],
                'cards':[{'card_id':'drop:blast','source':'falling','plant_name':'VisceraBomb'}],
                'zombies':[{'kind':'EyesZombie','row':2,'column':ordinary_column,'dying':False,'health':270},
                           {'kind':'DaveLevel1','row':4,'column':7,'dying':False,'health':17000}]}

    def test_blast_targets_live_boss_when_lawn_has_no_immediate_breach(self):
        card,row,column=decide_plant(self.state(5))
        self.assertEqual((row,column),(4,7))

    def test_immediate_lawn_breach_takes_precedence(self):
        card,row,column=decide_plant(self.state(1))
        self.assertEqual(row,2)

    def test_pumpkin_protects_an_existing_shooter(self):
        state=self.state(100);state['zombies']=[]
        state['plants']=[{'kind':'SuperMagicShooter','row':3,'column':1,'health':200,'dying':False}]
        state['cards']=[{'card_id':'drop:cover','source':'falling','plant_name':'ScripturePumpkin'}]
        card,row,column=decide_plant(state)
        self.assertEqual((row,column),(3,1))

    def test_second_form_blast_uses_native_overlap_rows(self):
        state=self.state(100);state['zombies']=[]
        state['bosses']=[{'parts':[{'health':9000,'dying':False,'position':[-2,3,0],'splash_rows':[1,2,3]},
                                   {'health':9000,'dying':False,'position':[1,3,0],'splash_rows':[3,4,5]}]}]
        card,row,column=decide_plant(state)
        self.assertEqual(row,3)


if __name__=='__main__':unittest.main()
